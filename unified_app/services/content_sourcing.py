from __future__ import annotations

import csv
import html
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from unified_app.config import EXPORT_DIR
from unified_app.services.content_hunt import analyze_url, fetch_url, hunt_urls, normalize_url
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack, save_draft
from unified_app.services.jobs import add_job


@dataclass
class SourceDigestItem:
    id: int
    score: int
    source_type: str
    title: str
    url: str
    rights_note: str
    idea_prompt: str
    created_at: str


def _text_score(title: str, description: str) -> int:
    text = f"{title} {description}".lower()
    score = 20
    for word in ("how", "why", "before", "after", "tips", "guide", "mistake", "best", "new", "watch", "review", "story"):
        if word in text:
            score += 6
    if re.search(r"\d", text):
        score += 5
    if len(description) > 80:
        score += 8
    if len(title) > 15:
        score += 6
    return min(score, 100)


def rights_note_for(source_type: str, url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if source_type in {"tiktok", "youtube"}:
        return "Use as inspiration or repost only if you own it or have permission. Credit is not the same as permission."
    if "wikipedia.org" in host or "wikimedia.org" in host:
        return "Check the page license and attribution requirements before reuse."
    if source_type == "feed":
        return "Use headlines as research prompts; open the original page and verify rights before reposting media."
    return "Research/inspiration candidate. Verify ownership, license, and permission before reposting third-party media."


def idea_prompt_for(title: str, description: str) -> str:
    pack = content_pack(title, description)
    return " | ".join([pack["hooks"][0], pack["captions"][0], " ".join(pack["hashtags"][:5])])


def score_all_candidates() -> int:
    init_db()
    updated = 0
    with connect() as db:
        rows = db.execute("select id,source_type,title,description,url,media_urls from content_candidates").fetchall()
        for item_id, source_type, title, desc, url, media_json in rows:
            try:
                media = json.loads(media_json or "[]")
            except json.JSONDecodeError:
                media = []
            score = _text_score(title or "", desc or "") + min(len(media), 5) * 4
            score = min(score, 100)
            rights = rights_note_for(source_type, url)
            prompt = idea_prompt_for(title or url, desc or "")
            db.execute("update content_candidates set score=?, rights_note=?, idea_prompt=? where id=?", (score, rights, prompt, item_id))
            updated += 1
        db.commit()
    add_job("source_score", "candidates", "done", f"Scored {updated} candidates")
    return updated


def _feed_links(page: str, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"<link>(.*?)</link>", page, re.I | re.S):
        url = html.unescape(raw.strip())
        if url.startswith("http") and url not in seen:
            seen.add(url); links.append(url)
    for raw in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', page, re.I):
        url = urllib.parse.urljoin(base_url, html.unescape(raw.strip()))
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme in {"http", "https"} and url not in seen:
            seen.add(url); links.append(url)
    return links[:40]


def expand_source(url: str, limit: int = 12) -> tuple[int, list[str]]:
    url = normalize_url(url)
    try:
        page = fetch_url(url)
    except Exception as exc:
        add_job("source_expand", url, "failed", str(exc))
        return 0, [f"{url}: {exc}"]
    links = _feed_links(page, url)[:limit]
    if not links:
        links = [url]
    cands, errs = hunt_urls(links)
    score_all_candidates()
    add_job("source_expand", url, "done", f"Expanded {len(cands)} candidates")
    return len(cands), errs


def refresh_saved_sources_deep(limit_per_source: int = 8) -> tuple[int, int]:
    init_db()
    ok = 0
    failed = 0
    with connect() as db:
        rows = db.execute("select id,url from content_sources where status='active' order by id desc").fetchall()
    for _source_id, url in rows:
        count, errs = expand_source(url, limit_per_source)
        ok += count
        failed += len(errs)
        with connect() as db:
            db.execute("update content_sources set last_checked_at=? where url=?", (now_iso(), url))
            db.commit()
    add_job("source_deep_refresh", "sources", "done", f"{ok} candidates, {failed} errors")
    return ok, failed


def digest_items(limit: int = 25) -> list[SourceDigestItem]:
    score_all_candidates()
    with connect() as db:
        rows = db.execute(
            """select id,score,source_type,title,url,rights_note,idea_prompt,created_at
               from content_candidates order by score desc,id desc limit ?""",
            (limit,),
        ).fetchall()
    return [SourceDigestItem(*row) for row in rows]


def format_source_digest(limit: int = 15) -> str:
    items = digest_items(limit)
    lines = ["No-Key Content Sourcing Digest", ""]
    if not items:
        return "No-Key Content Sourcing Digest\n\nNo candidates yet. Paste sources or run Content Hunt."
    for item in items:
        lines += [
            f"#{item.id} score {item.score} [{item.source_type}] {item.title[:120]}",
            f"  URL: {item.url}",
            f"  Idea: {item.idea_prompt}",
            f"  Rights: {item.rights_note}",
            "",
        ]
    return "\n".join(lines).rstrip()


def export_source_digest(limit: int = 50) -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"content-sourcing-digest-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    items = digest_items(limit)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "score", "source_type", "title", "url", "idea_prompt", "rights_note", "created_at"])
        for item in items:
            writer.writerow([item.id, item.score, item.source_type, item.title, item.url, item.idea_prompt, item.rights_note, item.created_at])
    add_job("export", str(out), "done", "content sourcing digest exported")
    return out


def draft_top_candidates(limit: int = 5) -> int:
    made = 0
    for item in digest_items(limit):
        save_draft(item.source_type, item.url, item.title, item.idea_prompt)
        made += 1
    add_job("draft", "top_candidates", "done", f"Created {made} drafts from top candidates")
    return made
