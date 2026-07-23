from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

from unified_app.config import EXPORT_DIR, STOPWORDS
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job
from unified_app.services.library import recent_candidates


def keywords_from_text(text: str, limit: int = 8) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text)]
    counts: dict[str, int] = {}
    for w in words:
        if w in STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def content_pack(title: str, description: str = "") -> dict[str, list[str]]:
    base = " ".join([title, description]).strip() or "new video"
    keys = keywords_from_text(base)
    hashtags = ["#" + re.sub(r"[^A-Za-z0-9]", "", k.title()) for k in keys[:6]]
    if "#TikTok" not in hashtags:
        hashtags.append("#TikTok")
    captions = [
        f"{title.strip()[:120]} {' '.join(hashtags[:4])}".strip(),
        f"What would you do next? {' '.join(hashtags[:4])}",
        f"Watch this before you scroll. {' '.join(hashtags[:4])}",
    ]
    hooks = [
        f"Nobody talks about {keys[0]} like this." if keys else "Nobody talks about this enough.",
        "The ending is the part people will replay.",
        "Here is the quick version.",
    ]
    return {"keywords": keys, "hashtags": hashtags, "captions": captions, "hooks": hooks}


def save_draft(source_type: str, source_ref: str, title: str, description: str = "") -> None:
    pack = content_pack(title, description)
    with connect() as db:
        db.execute(
            """insert into drafts(source_type,source_ref,title,hook,caption,hashtags,created_at)
            values (?,?,?,?,?,?,?) on conflict(source_ref) do update set
            title=excluded.title, hook=excluded.hook, caption=excluded.caption, hashtags=excluded.hashtags""",
            (source_type, source_ref, title[:220], pack["hooks"][0], pack["captions"][0], " ".join(pack["hashtags"]), now_iso()),
        )
        db.commit()


def make_drafts(limit: int = 50) -> int:
    init_db()
    made = 0
    with connect() as db:
        candidates = db.execute("select source_type,title,description,url from content_candidates order by id desc limit ?", (limit,)).fetchall()
        assets = db.execute("select path from local_assets order by id desc limit ?", (limit,)).fetchall()
    for source_type, title, desc, url in candidates:
        save_draft(source_type, url, title, desc)
        made += 1
    for (path,) in assets:
        save_draft("local", path, Path(path).stem, path)
        made += 1
    add_job("draft", "library", "done", f"Created or updated {made} drafts")
    return made


def recent_drafts(limit: int = 120) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,source_type,title,caption,hashtags,status,created_at from drafts order by id desc limit ?",
            (limit,),
        ).fetchall()


def export_draft_plan(days: int = 7) -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    init_db()
    with connect() as db:
        rows = db.execute(
            "select source_type,title,caption,hashtags,source_ref,status from drafts order by id desc limit ?",
            (days,),
        ).fetchall()
    if not rows:
        make_drafts(days)
        with connect() as db:
            rows = db.execute(
                "select source_type,title,caption,hashtags,source_ref,status from drafts order by id desc limit ?",
                (days,),
            ).fetchall()
    out = EXPORT_DIR / f"draft-posting-plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    start = datetime.now().replace(minute=0, second=0, microsecond=0)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "source_type", "title", "caption", "hashtags", "source", "status"])
        for i, row in enumerate(rows[:days]):
            source_type, title, caption, hashtags, source_ref, status = row
            writer.writerow([(start + timedelta(days=i, hours=18)).isoformat(), source_type, title, caption, hashtags, source_ref, status])
    add_job("export", str(out), "done", "draft posting plan created")
    return out


def export_posting_plan(days: int = 7) -> Path:
    init_db()
    with connect() as db:
        draft_count = db.execute("select count(*) from drafts").fetchone()[0]
    if draft_count:
        return export_draft_plan(days)
    EXPORT_DIR.mkdir(exist_ok=True)
    rows = recent_candidates(200)
    out = EXPORT_DIR / f"posting-plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    start = datetime.now().replace(minute=0, second=0, microsecond=0)
    slots = [start + timedelta(days=i, hours=18) for i in range(max(1, days))]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "source_type", "title", "caption", "hashtags", "url", "status"])
        for i, row in enumerate(rows[:days]):
            _id, source_type, title, url, status, _created = row
            pack = content_pack(title, url)
            writer.writerow([slots[i % len(slots)].isoformat(), source_type, title, pack["captions"][0], " ".join(pack["hashtags"]), url, "draft"])
    add_job("export", str(out), "done", "posting plan created")
    return out
