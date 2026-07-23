from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from unified_app.config import EXPORT_DIR, ROOT
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack, make_drafts
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets
from unified_app.services.settings import brand_settings

VALID_STATUSES = {"candidate", "draft", "edited", "ready", "scheduled", "uploaded", "archived"}
ITEM_TABLES = {"draft": "drafts", "asset": "local_assets", "candidate": "content_candidates"}


@dataclass
class ProductionItem:
    key: str
    item_type: str
    title: str
    status: str
    scheduled_for: str
    account: str
    source: str
    notes: str
    created_at: str


def _safe_status(status: str) -> str:
    cleaned = status.strip().lower().replace(" ", "_")
    if cleaned not in VALID_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    return cleaned


def rebuild_library() -> tuple[int, int]:
    assets = scan_local_assets()
    drafts = make_drafts()
    add_job("library", "production", "done", f"Rebuilt library with {assets} assets and {drafts} drafts")
    return assets, drafts


def production_rows(limit: int = 300) -> list[ProductionItem]:
    init_db()
    rows: list[ProductionItem] = []
    with connect() as db:
        for row in db.execute(
            """select id, source_type, title, status, coalesce(scheduled_for,''), account,
                      source_ref, notes, created_at from drafts order by id desc limit ?""",
            (limit,),
        ):
            item_id, source_type, title, status, scheduled, account, source_ref, notes, created = row
            rows.append(ProductionItem(f"draft:{item_id}", f"draft/{source_type}", title, status, scheduled or "", account or "", source_ref, notes or "", created))
        for row in db.execute(
            """select id, path, status, coalesce(scheduled_for,''), account, source_project, notes, created_at
                 from local_assets order by id desc limit ?""",
            (limit,),
        ):
            item_id, path, status, scheduled, account, source_project, notes, created = row
            title = Path(path).stem
            source = path
            if source_project:
                source = f"{source_project}: {path}"
            rows.append(ProductionItem(f"asset:{item_id}", "local_video", title, status, scheduled or "", account or "", source, notes or "", created))
        for row in db.execute(
            """select id, source_type, title, status, coalesce(scheduled_for,''), account, url, notes, created_at
                 from content_candidates order by id desc limit ?""",
            (limit,),
        ):
            item_id, source_type, title, status, scheduled, account, url, notes, created = row
            rows.append(ProductionItem(f"candidate:{item_id}", f"candidate/{source_type}", title, status, scheduled or "", account or "", url, notes or "", created))
    return sorted(rows, key=lambda x: x.created_at, reverse=True)[:limit]


def update_item_status(key: str, status: str, account: str = "", scheduled_for: str = "", notes: str = "") -> tuple[bool, str]:
    init_db()
    item_type, _, raw_id = key.partition(":")
    if item_type not in ITEM_TABLES or not raw_id.isdigit():
        return False, "Use keys like draft:1, asset:2, or candidate:3"
    try:
        clean_status = _safe_status(status)
    except ValueError as exc:
        return False, str(exc)
    table = ITEM_TABLES[item_type]
    assignments = ["status=?"]
    params: list[str] = [clean_status]
    if account:
        assignments.append("account=?")
        params.append(account.strip())
    if scheduled_for:
        assignments.append("scheduled_for=?")
        params.append(scheduled_for.strip())
    if notes:
        assignments.append("notes=?")
        params.append(notes.strip())
    params.append(raw_id)
    with connect() as db:
        db.execute(f"update {table} set {', '.join(assignments)} where id=?", params)
        db.commit()
    add_job("library", key, "done", f"Set status to {clean_status}")
    return True, f"Updated {key} to {clean_status}"


def mark_uploaded(key: str, account: str = "") -> tuple[bool, str]:
    init_db()
    item_type, _, raw_id = key.partition(":")
    if item_type not in ITEM_TABLES or not raw_id.isdigit():
        return False, "Use keys like draft:1, asset:2, or candidate:3"
    table = ITEM_TABLES[item_type]
    timestamp = now_iso()
    with connect() as db:
        if account:
            db.execute(f"update {table} set status='uploaded', uploaded_at=?, account=? where id=?", (timestamp, account.strip(), raw_id))
        else:
            db.execute(f"update {table} set status='uploaded', uploaded_at=? where id=?", (timestamp, raw_id))
        db.commit()
    add_job("library", key, "done", "Marked uploaded")
    return True, f"Marked {key} uploaded"


def schedule_next_drafts(count: int = 7, account: str = "", start_hour: int | None = None) -> tuple[int, str]:
    init_db()
    settings = brand_settings()
    account = account or settings.default_account
    if start_hour is None:
        start_hour = settings.posting_hour
    count = max(1, min(90, count))
    start = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0)
    with connect() as db:
        rows = db.execute(
            "select id from drafts where status in ('draft','edited','ready') and scheduled_for is null order by id desc limit ?",
            (count,),
        ).fetchall()
        if not rows:
            make_drafts(count)
            rows = db.execute(
                "select id from drafts where status in ('draft','edited','ready') and scheduled_for is null order by id desc limit ?",
                (count,),
            ).fetchall()
        for i, (draft_id,) in enumerate(rows):
            scheduled = (start + timedelta(days=i)).isoformat()
            if account:
                db.execute("update drafts set status='scheduled', scheduled_for=?, account=? where id=?", (scheduled, account.strip(), draft_id))
            else:
                db.execute("update drafts set status='scheduled', scheduled_for=? where id=?", (scheduled, draft_id))
        db.commit()
    add_job("schedule", "drafts", "done", f"Scheduled {len(rows)} drafts")
    return len(rows), f"Scheduled {len(rows)} drafts"


def export_library_csv(limit: int = 500) -> Path:
    init_db()
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"production-library-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    rows = production_rows(limit)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "type", "title", "status", "scheduled_for", "account", "source", "notes", "created_at"])
        for row in rows:
            writer.writerow([row.key, row.item_type, row.title, row.status, row.scheduled_for, row.account, row.source, row.notes, row.created_at])
    add_job("export", str(out), "done", "production library exported")
    return out


def library_summary_lines() -> list[str]:
    init_db()
    lines: list[str] = []
    with connect() as db:
        for status, count in db.execute("select status,count(*) from drafts group by status order by status"):
            lines.append(f"drafts.{status}: {count}")
        for status, count in db.execute("select status,count(*) from local_assets group by status order by status"):
            lines.append(f"assets.{status}: {count}")
        for status, count in db.execute("select status,count(*) from content_candidates group by status order by status"):
            lines.append(f"candidates.{status}: {count}")
    return lines


def draft_from_item(key: str) -> tuple[bool, str]:
    init_db()
    item_type, _, raw_id = key.partition(":")
    if not raw_id.isdigit():
        return False, "Use keys like asset:2 or candidate:3"
    with connect() as db:
        if item_type == "asset":
            row = db.execute("select path from local_assets where id=?", (raw_id,)).fetchone()
            if not row:
                return False, "Asset not found"
            source_ref = row[0]
            title = Path(source_ref).stem
            source_type = "local"
            desc = source_ref
        elif item_type == "candidate":
            row = db.execute("select source_type,title,description,url from content_candidates where id=?", (raw_id,)).fetchone()
            if not row:
                return False, "Candidate not found"
            source_type, title, desc, source_ref = row
        else:
            return False, "Draft creation is for asset or candidate rows"
        pack = content_pack(title, desc)
        db.execute(
            """insert into drafts(source_type,source_ref,title,hook,caption,hashtags,status,created_at)
               values (?,?,?,?,?,?,?,?) on conflict(source_ref) do update set
               title=excluded.title, hook=excluded.hook, caption=excluded.caption, hashtags=excluded.hashtags""",
            (source_type, source_ref, title[:220], pack["hooks"][0], pack["captions"][0], " ".join(pack["hashtags"]), "draft", now_iso()),
        )
        db.commit()
    add_job("draft", key, "done", "Created draft from library item")
    return True, f"Created draft from {key}"
