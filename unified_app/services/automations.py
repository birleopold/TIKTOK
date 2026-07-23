from __future__ import annotations

import csv
import hashlib
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from unified_app.config import EXPORT_DIR, READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.db import connect, init_db
from unified_app.services.drafts import export_draft_plan, make_drafts, recent_drafts
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets
from unified_app.services.video_tools import safe_slug


def find_ffmpeg() -> Path | str | None:
    from shutil import which
    found = which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return exe
    except Exception:
        pass
    base = Path.home() / "AppData" / "Local" / "ms-playwright"
    if base.exists():
        for candidate in base.glob("ffmpeg-*/*ffmpeg*.exe"):
            if candidate.exists():
                return candidate
    return None


def run_ffmpeg(args: list[str], job_kind: str, target: str) -> tuple[bool, str]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "FFmpeg not found"
    cmd = [str(ffmpeg), "-y", *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:
        add_job(job_kind, target, "failed", str(exc))
        return False, str(exc)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()[-1000:]
        add_job(job_kind, target, "failed", msg)
        return False, msg
    add_job(job_kind, target, "done", "FFmpeg task complete")
    return True, "Done"


def video_files_under(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


def file_fingerprint(path: Path, sample_bytes: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    h.update(str(path.stat().st_size).encode())
    with path.open("rb") as f:
        h.update(f.read(sample_bytes))
    return h.hexdigest()


def duplicate_report(folder_value: str = ".") -> tuple[Path, int, int]:
    folder = Path(folder_value)
    if not folder.is_absolute():
        folder = ROOT / folder
    EXPORT_DIR.mkdir(exist_ok=True)
    groups: dict[str, list[Path]] = {}
    for video in video_files_under(folder):
        try:
            groups.setdefault(file_fingerprint(video), []).append(video)
        except OSError:
            continue
    duplicates = {fp: paths for fp, paths in groups.items() if len(paths) > 1}
    out = EXPORT_DIR / f"duplicate-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fingerprint", "path", "size_bytes"])
        for fp, paths in duplicates.items():
            for path in paths:
                writer.writerow([fp, str(path.relative_to(ROOT)), path.stat().st_size])
    add_job("duplicates", str(folder), "done", f"{len(duplicates)} duplicate groups")
    return out, len(duplicates), sum(len(paths) for paths in duplicates.values())


def clean_rename_folder(folder_value: str = ".") -> tuple[int, list[str]]:
    folder = Path(folder_value)
    if not folder.is_absolute():
        folder = ROOT / folder
    renamed = 0
    notes: list[str] = []
    for video in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS):
        target = video.with_name(safe_slug(video.stem) + video.suffix.lower())
        if target == video:
            continue
        counter = 2
        while target.exists():
            target = video.with_name(f"{safe_slug(video.stem)}-{counter}{video.suffix.lower()}")
            counter += 1
        try:
            video.rename(target)
            renamed += 1
            notes.append(f"{video.name} -> {target.name}")
        except OSError as exc:
            notes.append(f"{video.name}: {exc}")
    scan_local_assets()
    add_job("rename", str(folder), "done", f"Renamed {renamed} videos")
    return renamed, notes


def what_to_post_today(limit: int = 5) -> list[tuple]:
    init_db()
    make_drafts(limit)
    with connect() as db:
        rows = db.execute(
            "select id,source_type,title,caption,hashtags,source_ref from drafts where status='draft' order by id desc limit ?",
            (limit,),
        ).fetchall()
    add_job("today", "drafts", "done", f"Selected {len(rows)} drafts")
    return rows


def export_today_list(limit: int = 5) -> Path:
    rows = what_to_post_today(limit)
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"what-to-post-today-{datetime.now().strftime('%Y%m%d')}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["priority", "source_type", "title", "caption", "hashtags", "source"])
        for idx, row in enumerate(rows, start=1):
            _id, source_type, title, caption, hashtags, source_ref = row
            writer.writerow([idx, source_type, title, caption, hashtags, source_ref])
    add_job("export", str(out), "done", "today list exported")
    return out


def export_calendar(days: int = 14) -> Path:
    return export_draft_plan(days)


def make_thumbnail(video_value: str, second: int = 1) -> tuple[bool, str]:
    source = Path(video_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Missing video: {source}"
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"thumb-{safe_slug(source.stem)}.jpg"
    ok, msg = run_ffmpeg(["-ss", str(second), "-i", str(source), "-frames:v", "1", "-q:v", "2", str(out)], "thumbnail", str(source))
    return (ok, str(out) if ok else msg)


def extract_audio(video_value: str) -> tuple[bool, str]:
    source = Path(video_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Missing video: {source}"
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"audio-{safe_slug(source.stem)}.mp3"
    ok, msg = run_ffmpeg(["-i", str(source), "-vn", "-acodec", "libmp3lame", "-q:a", "3", str(out)], "audio", str(source))
    return (ok, str(out) if ok else msg)


def make_tiktok_ready(video_value: str, max_seconds: int = 60) -> tuple[bool, str]:
    source = Path(video_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Missing video: {source}"
    READY_DIR.mkdir(parents=True, exist_ok=True)
    out = READY_DIR / f"ready-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(source.stem)}.mp4"
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    args = ["-i", str(source), "-t", str(max_seconds), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm", str(out)]
    ok, msg = run_ffmpeg(args, "tiktok_ready", str(source))
    if ok:
        scan_local_assets()
    return (ok, str(out) if ok else msg)
