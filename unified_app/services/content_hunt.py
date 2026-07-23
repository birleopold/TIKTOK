from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from unified_app.config import Candidate, IMAGE_EXTS, USER_AGENT, VIDEO_EXTS
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job


def normalize_url(v: str) -> str:
    v = v.strip()
    if v and not re.match(r"https?://", v, re.I):
        v = "https://" + v
    return v


def classify_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "tiktok.com" in host:
        return "tiktok"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if path.endswith((".rss", ".xml")) or "feed" in path:
        return "feed"
    return "web"


def fetch_url(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(2_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def extract_attr(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.I | re.S)
    return html.unescape(m.group(1).strip()) if m else ""


def extract_links(page: str, base: str) -> list[str]:
    raw = re.findall(r'''(?:href|src)=["']([^"']+)["']''', page, re.I)
    raw += re.findall(r'''https?://[^\s"'<>]+''', page, re.I)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        item = html.unescape(item).strip()
        if item.startswith(("mailto:", "javascript:", "data:")):
            continue
        link = urllib.parse.urljoin(base, item)
        if link.startswith(("http://", "https://")) and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def analyze_url(url: str) -> Candidate:
    page = fetch_url(url)
    title = extract_attr(page, r"<title[^>]*>(.*?)</title>") or urllib.parse.urlparse(url).netloc
    desc = extract_attr(page, r'''<meta[^>]+(?:name|property)=["'](?:description|og:description)["'][^>]+content=["']([^"']*)["']''')
    if not desc:
        desc = extract_attr(page, r'''<meta[^>]+content=["']([^"']*)["'][^>]+(?:name|property)=["'](?:description|og:description)["']''')
    links = extract_links(page, url)
    media = [x for x in links if Path(urllib.parse.urlparse(x).path).suffix.lower() in (VIDEO_EXTS | IMAGE_EXTS)]
    return Candidate(url, title, desc, classify_url(url), media, "Review rights before reposting; use for owned, permitted, public-domain, or inspiration workflows.")


def save_candidate(c: Candidate) -> None:
    init_db()
    with connect() as db:
        db.execute(
            """insert into content_candidates(url,title,description,source_type,media_urls,notes,created_at)
            values (?,?,?,?,?,?,?) on conflict(url) do update set title=excluded.title,
            description=excluded.description, source_type=excluded.source_type,
            media_urls=excluded.media_urls, notes=excluded.notes""",
            (c.url, c.title[:500], c.description[:1200], c.source_type, json.dumps(c.media_urls[:80]), c.notes, now_iso()),
        )
        db.commit()


def hunt_urls(values: list[str]) -> tuple[list[Candidate], list[str]]:
    found: list[Candidate] = []
    errors: list[str] = []
    for raw in values:
        url = normalize_url(raw)
        if not url:
            continue
        try:
            c = analyze_url(url)
            save_candidate(c)
            found.append(c)
            add_job("hunt", url, "done", c.title)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            add_job("hunt", url, "failed", str(exc))
    return found, errors


def save_source(url: str, label: str = "") -> tuple[bool, str]:
    init_db()
    url = normalize_url(url)
    if not url:
        return False, "Empty source URL"
    label = label.strip() or urllib.parse.urlparse(url).netloc or url
    with connect() as db:
        db.execute(
            """insert into content_sources(url,label,source_type,created_at) values (?,?,?,?)
            on conflict(url) do update set label=excluded.label, source_type=excluded.source_type, status='active'""",
            (url, label[:160], classify_url(url), now_iso()),
        )
        db.commit()
    add_job("source", url, "saved", label)
    return True, f"Saved source: {label}"


def recent_sources(limit: int = 100) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,source_type,label,url,status,last_checked_at from content_sources order by id desc limit ?",
            (limit,),
        ).fetchall()


def refresh_sources() -> tuple[int, int]:
    init_db()
    ok = 0
    failed = 0
    with connect() as db:
        rows = db.execute("select id,url from content_sources where status='active' order by id desc").fetchall()
    for source_id, url in rows:
        cands, errs = hunt_urls([url])
        if cands:
            ok += 1
            with connect() as db:
                db.execute("update content_sources set last_checked_at=? where id=?", (now_iso(), source_id))
                db.commit()
        if errs:
            failed += 1
    add_job("refresh", "sources", "done", f"{ok} refreshed, {failed} failed")
    return ok, failed
