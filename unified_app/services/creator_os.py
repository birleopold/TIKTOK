from __future__ import annotations

import csv
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from unified_app.config import DB_PATH, EXPORT_DIR, READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.automations import make_thumbnail, run_ffmpeg
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack, save_draft
from unified_app.services.jobs import add_job
from unified_app.services.production_library import mark_uploaded, production_rows, update_item_status
from unified_app.services.upload_queue import QueueItem, account_rows, queue_rows, run_queue_item
from unified_app.services.video_tools import safe_slug

CAPTION_DEFAULTS = [
    ("Sales caption", "{hook} {title}. Message us today. {hashtags}", "Direct offer style for products and services"),
    ("Educational caption", "{hook} Here is what to know: {title}. {hashtags}", "Useful, teaching-first caption"),
    ("Repair/tech caption", "{hook} This is how we handled {title}. {hashtags}", "Good for LEOSOFT repair and tech clips"),
    ("Funny caption", "POV: {title}. {hashtags}", "Light caption for relatable posts"),
    ("Storytelling caption", "{hook} The quick story: {title}. {hashtags}", "Mini-story format"),
    ("Call-to-action caption", "{title}. Comment what you want us to show next. {hashtags}", "Engagement prompt"),
]

HASHTAG_DEFAULTS = [
    ("LEOSOFT repair", "#LEOSOFT #PhoneRepair #TechRepair #UgandaBusiness #TikTok", "Default repair brand pack"),
    ("Uganda tech", "#UgandaTech #Kampala #TechTips #DigitalSkills #TikTok", "Local tech audience"),
    ("Phone repair", "#PhoneRepair #ScreenRepair #BatteryReplacement #RepairShop #TikTok", "Phone service pack"),
    ("Business promo", "#SmallBusiness #BusinessTips #Promo #CustomerCare #TikTok", "Promotion and sales pack"),
    ("Tutorial", "#Tutorial #HowTo #TipsAndTricks #LearnOnTikTok #TikTok", "Teaching content pack"),
]

TEMPLATE_DEFAULTS = [
    ("Before/after repair", "Look at the difference in this repair.", "Before and after: {topic}. Clean result, real process, simple explanation. {hashtags}", "#BeforeAfter #Repair #LEOSOFT #TikTok", "Repair transformation"),
    ("Product showcase", "Here is why this is useful.", "Product spotlight: {topic}. What it does, who needs it, and why it matters. {hashtags}", "#ProductShowcase #Tech #Business #TikTok", "Product demo"),
    ("Customer question", "A customer asked this today.", "Customer question: {topic}. Here is the simple answer. {hashtags}", "#CustomerQuestion #TechTips #LearnOnTikTok #TikTok", "FAQ post"),
    ("3 tips", "Save this before you forget.", "3 tips about {topic}: quick, useful, and easy to try. {hashtags}", "#3Tips #HowTo #Tutorial #TikTok", "List format"),
    ("Mistake to avoid", "This mistake costs people money.", "Mistake to avoid: {topic}. Do this instead. {hashtags}", "#MistakesToAvoid #TechTips #Repair #TikTok", "Warning format"),
    ("Promo offer", "Need this service?", "Promo: {topic}. Contact LEOSOFT and get it handled. {hashtags}", "#Promo #LEOSOFT #SmallBusiness #TikTok", "Offer format"),
    ("Behind the scenes", "Here is what happens behind the scenes.", "Behind the scenes: {topic}. A quick look at the work before the result. {hashtags}", "#BehindTheScenes #WorkFlow #TechRepair #TikTok", "Process clip"),
]

@dataclass
class BoardSection:
    name: str
    rows: list[tuple]


def seed_creator_os() -> None:
    init_db()
    with connect() as db:
        for name, template, notes in CAPTION_DEFAULTS:
            db.execute("insert or ignore into caption_styles(name,template,notes,created_at) values (?,?,?,?)", (name, template, notes, now_iso()))
        for name, hashtags, notes in HASHTAG_DEFAULTS:
            db.execute("insert or ignore into hashtag_sets(name,hashtags,notes,created_at) values (?,?,?,?)", (name, hashtags, notes, now_iso()))
        for name, hook, caption, hashtags, notes in TEMPLATE_DEFAULTS:
            db.execute("insert or ignore into content_templates(name,hook_template,caption_template,hashtags,notes,created_at) values (?,?,?,?,?,?)", (name, hook, caption, hashtags, notes, now_iso()))
        db.commit()


def caption_style_rows() -> list[tuple]:
    seed_creator_os()
    with connect() as db:
        return db.execute("select id,name,template,notes from caption_styles order by name").fetchall()


def hashtag_set_rows() -> list[tuple]:
    seed_creator_os()
    with connect() as db:
        return db.execute("select id,name,hashtags,notes from hashtag_sets order by name").fetchall()


def template_rows() -> list[tuple]:
    seed_creator_os()
    with connect() as db:
        return db.execute("select id,name,hook_template,caption_template,hashtags,notes from content_templates order by name").fetchall()


def add_caption_style(name: str, template: str, notes: str = "") -> tuple[bool, str]:
    seed_creator_os()
    with connect() as db:
        db.execute("insert into caption_styles(name,template,notes,created_at) values (?,?,?,?) on conflict(name) do update set template=excluded.template, notes=excluded.notes", (name.strip(), template.strip(), notes.strip(), now_iso()))
        db.commit()
    return True, f"Saved caption style: {name}"


def add_hashtag_set(name: str, hashtags: str, notes: str = "") -> tuple[bool, str]:
    seed_creator_os()
    tags = " ".join(tag if tag.startswith("#") else "#" + tag for tag in hashtags.split())
    with connect() as db:
        db.execute("insert into hashtag_sets(name,hashtags,notes,created_at) values (?,?,?,?) on conflict(name) do update set hashtags=excluded.hashtags, notes=excluded.notes", (name.strip(), tags, notes.strip(), now_iso()))
        db.commit()
    return True, f"Saved hashtag set: {name}"


def _draft_context(draft_id: int) -> tuple[str, str, str, str] | None:
    with connect() as db:
        row = db.execute("select title,hook,caption,hashtags from drafts where id=?", (draft_id,)).fetchone()
    return row


def apply_caption_style(draft_id: int, style_name: str) -> tuple[bool, str]:
    seed_creator_os()
    ctx = _draft_context(draft_id)
    if not ctx:
        return False, f"Draft not found: {draft_id}"
    with connect() as db:
        style = db.execute("select template from caption_styles where lower(name)=lower(?)", (style_name,)).fetchone()
        if not style:
            return False, f"Caption style not found: {style_name}"
        title, hook, _caption, hashtags = ctx
        caption = style[0].format(title=title, hook=hook, hashtags=hashtags).strip()
        db.execute("update drafts set caption=?, notes=trim(coalesce(notes,'') || ' Caption style: ' || ?) where id=?", (caption[:2200], style_name, draft_id))
        db.commit()
    return True, f"Applied caption style '{style_name}' to draft {draft_id}"


def apply_hashtag_set(draft_id: int, set_name: str) -> tuple[bool, str]:
    seed_creator_os()
    with connect() as db:
        tagset = db.execute("select hashtags from hashtag_sets where lower(name)=lower(?)", (set_name,)).fetchone()
        if not tagset:
            return False, f"Hashtag set not found: {set_name}"
        db.execute("update drafts set hashtags=?, notes=trim(coalesce(notes,'') || ' Hashtag set: ' || ?) where id=?", (tagset[0], set_name, draft_id))
        changed = db.total_changes
        db.commit()
    return (changed > 0, f"Applied hashtag set '{set_name}' to draft {draft_id}" if changed else f"Draft not found: {draft_id}")


def update_draft_field(draft_id: int, field: str, value: str) -> tuple[bool, str]:
    allowed = {"title", "hook", "caption", "hashtags", "notes", "account", "status", "scheduled_for"}
    if field not in allowed:
        return False, "Editable fields: " + ", ".join(sorted(allowed))
    init_db()
    with connect() as db:
        db.execute(f"update drafts set {field}=? where id=?", (value, draft_id))
        changed = db.total_changes
        db.commit()
    return (changed > 0, f"Updated draft {draft_id} {field}" if changed else f"Draft not found: {draft_id}")


def create_draft_from_template(template_name: str, topic: str) -> tuple[bool, str]:
    seed_creator_os()
    with connect() as db:
        row = db.execute("select hook_template,caption_template,hashtags from content_templates where lower(name)=lower(?)", (template_name,)).fetchone()
    if not row:
        return False, f"Template not found: {template_name}"
    hook, caption_template, hashtags = row
    title = f"{template_name}: {topic}"[:220]
    source_ref = f"template:{safe_slug(template_name)}:{safe_slug(topic)}"
    save_draft("template", source_ref, title, topic)
    caption = caption_template.format(topic=topic, hashtags=hashtags).strip()
    with connect() as db:
        db.execute("update drafts set hook=?, caption=?, hashtags=?, notes=? where source_ref=?", (hook, caption[:2200], hashtags, f"Created from template: {template_name}", source_ref))
        draft_id = db.execute("select id from drafts where source_ref=?", (source_ref,)).fetchone()[0]
        db.commit()
    add_job("template", template_name, "done", f"Created draft {draft_id}")
    return True, f"Created draft {draft_id} from template '{template_name}'"


def calendar_board(days: int = 7) -> list[BoardSection]:
    init_db()
    now = datetime.now()
    end = now + timedelta(days=days)
    sections = {name: [] for name in ["Today", "This week", "Scheduled", "Ready", "Uploaded", "Missed", "Needs account"]}
    for row in production_rows(500):
        item = (row.key, row.status, row.title, row.scheduled_for or "", row.account or "", row.source)
        if row.status == "uploaded":
            sections["Uploaded"].append(item)
        if row.status in {"ready", "scheduled"}:
            if row.status == "ready":
                sections["Ready"].append(item)
            if not row.account:
                sections["Needs account"].append(item)
        if row.scheduled_for:
            try:
                dt = datetime.fromisoformat(row.scheduled_for.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                dt = None
            if dt:
                if dt.date() == now.date():
                    sections["Today"].append(item)
                if now <= dt <= end:
                    sections["This week"].append(item)
                if dt < now and row.status != "uploaded":
                    sections["Missed"].append(item)
                sections["Scheduled"].append(item)
    for q in queue_rows(200):
        item = (f"queue:{q.id}", q.status, q.title, q.scheduled_for, q.account, q.source_ref)
        if q.status in {"queued", "failed"} and not q.account:
            sections["Needs account"].append(item)
    return [BoardSection(name, rows) for name, rows in sections.items()]


def format_calendar_board(days: int = 7) -> str:
    lines = [f"Content Calendar Board ({days} days)", ""]
    for section in calendar_board(days):
        lines.append(section.name)
        if not section.rows:
            lines.append("  - none")
        for row in section.rows[:25]:
            key, status, title, scheduled, account, source = row
            bits = [key, status, title]
            if scheduled:
                bits.append("scheduled=" + scheduled)
            if account:
                bits.append("account=" + account)
            lines.append("  - " + " | ".join(bits))
        lines.append("")
    return "\n".join(lines).strip()


def upload_assistant(item_id: int) -> str:
    rows = {item.id: item for item in queue_rows(500)}
    item = rows.get(item_id)
    if not item:
        return f"Queue item not found: {item_id}"
    health = {row[1]: row for row in account_rows()}
    account = health.get(item.account)
    ok, command = run_queue_item(item_id, dry_run=True)
    lines = [f"Upload Assistant: queue #{item.id}", f"Video: {item.source_ref}", f"Title: {item.title}", "", "Caption:", item.caption or item.title, ""]
    if item.account:
        lines.append(f"Account: {item.account}")
        lines.append(f"Session health: {account[2] if account else 'not registered'}")
        if account:
            lines.append(f"Session note: {account[5]}")
    else:
        lines.append("Account: missing")
        lines.append("Next: assign an account before upload")
    lines += ["", "Uploader command preview:", command if ok else "Blocked: " + command, "", "After posting, confirm with:", f"python -m unified_app.app --confirm-upload {item.id} <TikTok URL>"]
    return "\n".join(lines)


def record_upload_result(item_id: int, tiktok_url: str, views: int = 0, likes: int = 0, comments: int = 0, shares: int = 0, notes: str = "") -> tuple[bool, str]:
    rows = {item.id: item for item in queue_rows(500)}
    item = rows.get(item_id)
    if not item:
        return False, f"Queue item not found: {item_id}"
    uploaded_at = now_iso()
    with connect() as db:
        db.execute("""insert into upload_results(queue_id,library_key,source_ref,tiktok_url,account,caption,uploaded_at,views,likes,comments,shares,notes,created_at)
                      values (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (item.id, item.library_key, item.source_ref, tiktok_url.strip(), item.account, item.caption, uploaded_at, views, likes, comments, shares, notes, now_iso()))
        db.execute("update upload_queue set status='done', last_message=?, updated_at=? where id=?", ("Confirmed posted: " + tiktok_url.strip(), now_iso(), item.id))
        db.commit()
    if item.library_key:
        mark_uploaded(item.library_key, account=item.account)
    add_job("upload_confirm", str(item_id), "done", tiktok_url)
    return True, f"Recorded upload result for queue #{item_id}"


def upload_result_rows(limit: int = 100) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute("select id,queue_id,tiktok_url,account,uploaded_at,views,likes,comments,shares,notes from upload_results order by id desc limit ?", (limit,)).fetchall()


def performance_report() -> str:
    init_db()
    with connect() as db:
        counts = db.execute("select status,count(*) from drafts group by status order by status").fetchall()
        uploaded = db.execute("select count(*),sum(views),sum(likes),sum(comments),sum(shares) from upload_results").fetchone()
        top_captions = db.execute("select substr(caption,1,90),sum(views) v,count(*) c from upload_results group by caption order by v desc limit 5").fetchall()
        top_tags = db.execute("select hashtags,count(*) from drafts where hashtags<>'' group by hashtags order by count(*) desc limit 5").fetchall()
        days = db.execute("select substr(uploaded_at,1,10),count(*),sum(views) from upload_results group by substr(uploaded_at,1,10) order by substr(uploaded_at,1,10) desc limit 7").fetchall()
    total, views, likes, comments, shares = uploaded
    lines = ["Performance Analytics", "", "Draft pipeline:"]
    lines += [f"  - {status}: {count}" for status, count in counts] or ["  - no drafts yet"]
    lines += ["", f"Uploaded posts tracked: {total or 0}", f"Views: {views or 0} | Likes: {likes or 0} | Comments: {comments or 0} | Shares: {shares or 0}", "", "Best captions by views:"]
    lines += [f"  - {v or 0} views across {c}: {caption}" for caption, v, c in top_captions] or ["  - no upload results yet"]
    lines += ["", "Most-used hashtag sets:"]
    lines += [f"  - {count} drafts: {tags}" for tags, count in top_tags] or ["  - no hashtag data yet"]
    lines += ["", "Recent posting days:"]
    lines += [f"  - {day}: {count} posts, {views or 0} views" for day, count, views in days] or ["  - no upload dates yet"]
    return "\n".join(lines)


def generate_thumbnail_choices(video_value: str, count: int = 5) -> tuple[bool, str]:
    source = Path(video_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Missing video: {source}"
    seconds = [1, 3, 5, 8, 12, 20, 30][:max(1, min(count, 7))]
    made: list[tuple[str, int]] = []
    init_db()
    with connect() as db:
        db.execute("delete from thumbnail_choices where source_ref=?", (str(source),))
        db.commit()
    for second in seconds:
        ok, msg = make_thumbnail(str(source), second=second)
        if ok:
            thumb = Path(msg)
            target = thumb.with_name(f"thumb-{safe_slug(source.stem)}-{second}s.jpg")
            if thumb.exists() and thumb != target:
                try:
                    thumb.replace(target)
                except OSError:
                    target = thumb
            made.append((str(target), second))
    with connect() as db:
        for idx, (path, second) in enumerate(made):
            db.execute("insert into thumbnail_choices(source_ref,image_path,second,selected,created_at) values (?,?,?,?,?)", (str(source), path, second, 1 if idx == 0 else 0, now_iso()))
        db.commit()
    return (bool(made), "\n".join(path for path, _second in made) if made else "No thumbnails created")


def select_thumbnail(choice_id: int) -> tuple[bool, str]:
    init_db()
    with connect() as db:
        row = db.execute("select source_ref,image_path from thumbnail_choices where id=?", (choice_id,)).fetchone()
        if not row:
            return False, f"Thumbnail choice not found: {choice_id}"
        db.execute("update thumbnail_choices set selected=0 where source_ref=?", (row[0],))
        db.execute("update thumbnail_choices set selected=1 where id=?", (choice_id,))
        db.commit()
    return True, f"Selected thumbnail: {row[1]}"


def thumbnail_rows(source_ref: str = "") -> list[tuple]:
    init_db()
    with connect() as db:
        if source_ref:
            return db.execute("select id,source_ref,image_path,second,selected,created_at from thumbnail_choices where source_ref=? order by second", (source_ref,)).fetchall()
        return db.execute("select id,source_ref,image_path,second,selected,created_at from thumbnail_choices order by id desc limit 100").fetchall()


def repurpose_long_video(video_value: str, segment_seconds: int = 45, parts: int = 3) -> tuple[bool, str]:
    source = Path(video_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists() or source.suffix.lower() not in VIDEO_EXTS:
        return False, f"Missing supported video: {source}"
    READY_DIR.mkdir(parents=True, exist_ok=True)
    made: list[str] = []
    for part in range(1, max(1, parts) + 1):
        start = (part - 1) * max(5, segment_seconds)
        out = READY_DIR / f"clip-{safe_slug(source.stem)}-part-{part}.mp4"
        ok, msg = run_ffmpeg(["-ss", str(start), "-i", str(source), "-t", str(segment_seconds), "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", str(out)], "repurpose", str(source))
        if ok and out.exists() and out.stat().st_size > 0:
            title = f"{source.stem} part {part}"
            save_draft("repurposed_clip", str(out), title, f"Clip {part} from {source.name}")
            made.append(str(out))
    add_job("repurpose", str(source), "done" if made else "failed", f"Created {len(made)} clips")
    return (bool(made), "Created clips:\n" + "\n".join(made) if made else "No clips created")


def create_series(name: str, topic: str, parts: int = 3) -> tuple[bool, str]:
    seed_creator_os()
    with connect() as db:
        db.execute("insert into series(name,topic,status,created_at) values (?,?,?,?) on conflict(name) do update set topic=excluded.topic", (name.strip(), topic.strip(), "planning", now_iso()))
        series_id = db.execute("select id from series where name=?", (name.strip(),)).fetchone()[0]
        db.commit()
    created: list[tuple[int, str, str, int]] = []
    for part in range(1, max(1, parts) + 1):
        title = f"{topic} - Part {part}"
        source_ref = f"series:{safe_slug(name)}:part-{part}"
        save_draft("series", source_ref, title, topic)
        with connect() as db:
            draft_id = db.execute("select id from drafts where source_ref=?", (source_ref,)).fetchone()[0]
        created.append((part, title, source_ref, draft_id))
    with connect() as db:
        for part, title, source_ref, draft_id in created:
            db.execute("insert into series_posts(series_id,part_no,title,source_ref,draft_id,status,created_at) values (?,?,?,?,?,?,?) on conflict(series_id,part_no) do update set title=excluded.title,draft_id=excluded.draft_id", (series_id, part, title, source_ref, draft_id, "draft", now_iso()))
        db.commit()
    return True, f"Created series '{name}' with {parts} parts"


def series_rows() -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute("select s.id,s.name,s.topic,s.status,count(p.id) parts,s.created_at from series s left join series_posts p on p.series_id=s.id group by s.id order by s.id desc").fetchall()


def backup_app() -> tuple[bool, str]:
    init_db()
    EXPORT_DIR.mkdir(exist_ok=True)
    backup_dir = EXPORT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    out = backup_dir / f"creator-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        if DB_PATH.exists():
            z.write(DB_PATH, DB_PATH.name)
        for folder_name in ("exports", "TiktokAutoUploader-main/VideosDirPath"):
            folder = ROOT / folder_name
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if path.is_file() and path != out:
                    z.write(path, path.relative_to(ROOT))
        meta = {"created_at": now_iso(), "root": str(ROOT)}
        z.writestr("backup-manifest.json", json.dumps(meta, indent=2))
    add_job("backup", str(out), "done", "Backup created")
    return True, str(out)


def backup_rows() -> list[tuple]:
    backup_dir = EXPORT_DIR / "backups"
    if not backup_dir.exists():
        return []
    rows = []
    for path in sorted(backup_dir.glob("creator-backup-*.zip"), reverse=True):
        rows.append((path.name, path.stat().st_size, datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"), str(path)))
    return rows


def restore_backup(zip_value: str) -> tuple[bool, str]:
    source = Path(zip_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Backup not found: {source}"
    safety = EXPORT_DIR / "backups" / f"pre-restore-db-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    safety.parent.mkdir(exist_ok=True)
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, safety)
    with zipfile.ZipFile(source) as z:
        names = set(z.namelist())
        if DB_PATH.name not in names:
            return False, "Backup does not contain the app database"
        z.extract(DB_PATH.name, ROOT)
    add_job("restore", str(source), "done", f"Database restored; safety copy: {safety}")
    return True, f"Database restored. Safety copy saved: {safety}"


def export_calendar_board(days: int = 7) -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"calendar-board-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["section", "key", "status", "title", "scheduled_for", "account", "source"])
        for section in calendar_board(days):
            for row in section.rows:
                writer.writerow([section.name, *row])
    add_job("calendar_board", str(out), "done", "Calendar board exported")
    return out
