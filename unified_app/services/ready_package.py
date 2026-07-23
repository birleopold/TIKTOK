from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from unified_app.config import ROOT, VIDEO_EXTS
from unified_app.services.automations import extract_audio, make_thumbnail, make_tiktok_ready
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack, save_draft
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets
from unified_app.services.production_library import production_rows, update_item_status


@dataclass
class ReadyPackage:
    source: Path
    ready_video: Path | None
    thumbnail: Path | None
    audio: Path | None
    title: str
    caption: str
    hashtags: str
    draft_key: str
    asset_key: str
    notes: list[str]


def _resolve_video(value: str) -> Path:
    source = Path(value.strip().strip('"'))
    if not source.is_absolute():
        source = ROOT / source
    return source


def _relative_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _latest_key(item_type: str, source: str) -> str:
    for row in production_rows(500):
        if row.key.startswith(item_type + ":") and row.source == source:
            return row.key
    return ""


def _set_asset_metadata(ready_video: Path, caption: str, hashtags: str, status: str = "ready") -> str:
    init_db()
    rel = _relative_or_abs(ready_video)
    with connect() as db:
        row = db.execute("select id from local_assets where path=?", (rel,)).fetchone()
        if not row:
            return ""
        db.execute(
            """update local_assets set status=?, caption=?, hashtags=?, source_project=?, notes=? where id=?""",
            (status, caption, hashtags, "ready_package", "Created by Make It TikTok Ready package", row[0]),
        )
        db.commit()
        return f"asset:{row[0]}"


def _set_draft_ready(source_ref: str, caption: str, hashtags: str) -> str:
    init_db()
    with connect() as db:
        row = db.execute("select id from drafts where source_ref=?", (source_ref,)).fetchone()
        if not row:
            return ""
        db.execute(
            "update drafts set status='ready', caption=?, hashtags=?, notes=? where id=?",
            (caption, hashtags, "Created by Make It TikTok Ready package", row[0]),
        )
        db.commit()
        return f"draft:{row[0]}"


def make_ready_package(video_value: str, max_seconds: int = 60) -> tuple[bool, ReadyPackage | None, str]:
    source = _resolve_video(video_value)
    if not source.exists() or source.suffix.lower() not in VIDEO_EXTS:
        return False, None, f"Not a supported local video: {source}"
    notes: list[str] = []
    title = source.stem.replace("-", " ").replace("_", " ").strip() or "TikTok ready video"
    pack = content_pack(title, str(source))
    caption = pack["captions"][0]
    hashtags = " ".join(pack["hashtags"])

    ok, ready_msg = make_tiktok_ready(str(source), max_seconds=max_seconds)
    if not ok:
        add_job("ready_package", str(source), "failed", ready_msg)
        return False, None, ready_msg
    ready_video = Path(ready_msg)
    if not ready_video.is_absolute():
        ready_video = ROOT / ready_video

    thumb_path: Path | None = None
    audio_path: Path | None = None
    thumb_ok, thumb_msg = make_thumbnail(str(ready_video))
    if thumb_ok:
        thumb_path = Path(thumb_msg)
    else:
        notes.append("Thumbnail failed: " + thumb_msg)
    audio_ok, audio_msg = extract_audio(str(ready_video))
    if audio_ok:
        audio_path = Path(audio_msg)
    else:
        notes.append("Audio extraction failed: " + audio_msg)

    scan_local_assets()
    ready_ref = _relative_or_abs(ready_video)
    save_draft("local", ready_ref, title, ready_ref)
    draft_key = _set_draft_ready(ready_ref, caption, hashtags)
    asset_key = _set_asset_metadata(ready_video, caption, hashtags)
    if asset_key:
        update_item_status(asset_key, "ready", notes="Ready package generated")
    package = ReadyPackage(
        source=source,
        ready_video=ready_video,
        thumbnail=thumb_path,
        audio=audio_path,
        title=title,
        caption=caption,
        hashtags=hashtags,
        draft_key=draft_key,
        asset_key=asset_key,
        notes=notes,
    )
    add_job("ready_package", str(source), "done", f"Created ready package {ready_ref}")
    return True, package, format_ready_package(package)


def format_ready_package(package: ReadyPackage) -> str:
    lines = [
        "Make It TikTok Ready Package",
        f"Source: {package.source}",
        f"Ready video: {package.ready_video}",
    ]
    if package.thumbnail:
        lines.append(f"Thumbnail: {package.thumbnail}")
    if package.audio:
        lines.append(f"Audio: {package.audio}")
    lines += [
        f"Draft key: {package.draft_key or 'not found'}",
        f"Asset key: {package.asset_key or 'not found'}",
        "",
        "Caption:",
        package.caption,
        "",
        "Hashtags:",
        package.hashtags,
    ]
    if package.notes:
        lines += ["", "Notes:"] + ["  - " + note for note in package.notes]
    return "\n".join(lines)
