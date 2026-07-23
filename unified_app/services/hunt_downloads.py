from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from unified_app.config import ROOT, VIDEO_EXTS
from unified_app.services.content_hunt import _validate_public_url, classify_url
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets


DOWNLOAD_ROOT = ROOT / "downloads" / "hunt"
DOWNLOAD_ARCHIVE = DOWNLOAD_ROOT / ".downloaded.txt"
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class HuntDownloadCandidate:
    id: int
    source_type: str
    title: str
    url: str
    description: str
    status: str
    created_at: str


@dataclass(frozen=True)
class DownloadedVideo:
    candidate_id: int
    title: str
    source_url: str
    local_path: Path
    metadata_path: Path
    platform: str
    uploader: str
    duration_seconds: int | None


def ensure_download_root() -> Path:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_ROOT


def slugify(value: str, fallback: str = "hunt") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return (cleaned[:80] or fallback).strip("-") or fallback


def recent_download_candidates(
    limit: int = 250,
    source_type: str = "all",
    query: str = "",
) -> list[HuntDownloadCandidate]:
    init_db()
    limit = max(1, min(int(limit or 250), 1000))
    selected_type = (source_type or "all").strip().lower()
    needle = f"%{(query or '').strip()}%"
    clauses: list[str] = []
    params: list[object] = []

    if selected_type != "all":
        clauses.append("lower(source_type)=?")
        params.append(selected_type)
    if (query or "").strip():
        clauses.append("(title like ? or description like ? or url like ?)")
        params.extend([needle, needle, needle])

    where = " where " + " and ".join(clauses) if clauses else ""
    sql = (
        "select id,source_type,title,url,description,status,created_at "
        f"from content_candidates{where} order by id desc limit ?"
    )
    params.append(limit)
    with connect() as db:
        rows = db.execute(sql, tuple(params)).fetchall()
    return [HuntDownloadCandidate(*row) for row in rows]


def _load_yt_dlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is not installed. Run: py -3 -m pip install -U yt-dlp"
        ) from exc
    return yt_dlp


def _duration_text(seconds: int | float | None) -> str:
    if seconds is None:
        return "unknown"
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _resolution_text(info: dict) -> str:
    width = info.get("width")
    height = info.get("height")
    if width and height:
        return f"{width}x{height}"
    resolution = info.get("resolution")
    return str(resolution or "unknown")


def probe_candidate(candidate: HuntDownloadCandidate) -> dict[str, str]:
    url = _validate_public_url(candidate.url)
    yt_dlp = _load_yt_dlp()
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": 25,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)

    if not isinstance(info, dict):
        raise RuntimeError("The source did not return downloadable video information.")
    if info.get("_type") == "playlist" or info.get("entries"):
        raise RuntimeError("Playlists are not downloaded. Select an individual video page.")

    return {
        "title": str(info.get("title") or candidate.title),
        "platform": str(info.get("extractor_key") or info.get("extractor") or candidate.source_type),
        "uploader": str(info.get("uploader") or info.get("channel") or "unknown"),
        "duration": _duration_text(info.get("duration")),
        "resolution": _resolution_text(info),
        "webpage_url": str(info.get("webpage_url") or candidate.url),
        "availability": str(info.get("availability") or "public/unknown"),
    }


def _video_files(folder: Path) -> set[Path]:
    if not folder.exists():
        return set()
    return {
        path.resolve()
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTS
    }


def _pick_downloaded_file(folder: Path, before: set[Path], info: dict) -> Path:
    after = _video_files(folder)
    created = sorted(
        after - before,
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    if created:
        return created[0]

    requested = info.get("requested_downloads") or []
    for item in requested:
        if not isinstance(item, dict):
            continue
        filepath = item.get("filepath")
        if filepath:
            candidate = Path(filepath)
            if candidate.exists() and candidate.suffix.lower() in VIDEO_EXTS:
                return candidate.resolve()

    filename = info.get("_filename")
    if filename:
        candidate = Path(filename)
        if candidate.exists() and candidate.suffix.lower() in VIDEO_EXTS:
            return candidate.resolve()

    raise RuntimeError(
        "The downloader finished but no local video file was found. "
        "The source may be unsupported or require FFmpeg."
    )


def _metadata_path(video_path: Path) -> Path:
    return video_path.with_suffix(video_path.suffix + ".source.json")


def _write_metadata(
    candidate: HuntDownloadCandidate,
    video_path: Path,
    search_label: str,
    info: dict,
) -> Path:
    metadata_path = _metadata_path(video_path)
    payload = {
        "candidate_id": candidate.id,
        "candidate_title": candidate.title,
        "candidate_description": candidate.description,
        "source_url": candidate.url,
        "source_type": candidate.source_type,
        "search_label": search_label,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "local_path": str(video_path),
        "video_id": info.get("id"),
        "video_title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "duration_seconds": info.get("duration"),
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "webpage_url": info.get("webpage_url") or candidate.url,
        "rights_confirmation": (
            "The user confirmed that they own the content, have permission, "
            "or are otherwise legally allowed to download and reuse it."
        ),
    }
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return metadata_path


def _mark_candidate_downloaded(candidate_id: int, local_path: Path) -> None:
    init_db()
    note = f"Downloaded locally: {local_path}"
    with connect() as db:
        row = db.execute(
            "select notes from content_candidates where id=?",
            (candidate_id,),
        ).fetchone()
        previous = (row[0] if row else "") or ""
        notes = f"{previous}\n{note}".strip()
        db.execute(
            "update content_candidates set status='downloaded', notes=? where id=?",
            (notes[:4000], candidate_id),
        )
        db.commit()


def download_candidate(
    candidate: HuntDownloadCandidate,
    search_label: str = "",
    progress: ProgressCallback | None = None,
) -> DownloadedVideo:
    url = _validate_public_url(candidate.url)
    yt_dlp = _load_yt_dlp()
    folder = ensure_download_root() / slugify(search_label or candidate.title)
    folder.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)

    def report(message: str) -> None:
        if progress:
            progress(message)

    def hook(event: dict) -> None:
        status = event.get("status")
        if status == "downloading":
            percent = str(event.get("_percent_str") or "").strip()
            speed = str(event.get("_speed_str") or "").strip()
            eta = str(event.get("_eta_str") or "").strip()
            report(
                f"Downloading {candidate.title[:60]} — "
                f"{percent or 'working'} {speed} ETA {eta}".strip()
            )
        elif status == "finished":
            report(f"Finishing {candidate.title[:60]}...")

    before = _video_files(folder)
    output_template = str(folder / "%(title).180B [%(id)s].%(ext)s")
    video_format = (
        "bv*[height<=1080]+ba/b[height<=1080]/best"
        if shutil.which("ffmpeg")
        else "b[ext=mp4][height<=1080]/b[height<=1080]/best"
    )
    options = {
        "format": video_format,
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "continuedl": True,
        "nooverwrites": True,
        "windowsfilenames": True,
        "restrictfilenames": False,
        "writeinfojson": True,
        "download_archive": str(DOWNLOAD_ARCHIVE),
        "progress_hooks": [hook],
        "socket_timeout": 30,
    }

    report(f"Starting: {candidate.title}")
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    if not isinstance(info, dict):
        raise RuntimeError("The source did not return video information.")

    video_path = _pick_downloaded_file(folder, before, info)
    metadata_path = _write_metadata(candidate, video_path, search_label, info)
    _mark_candidate_downloaded(candidate.id, video_path)
    add_job(
        "hunt_download",
        candidate.url,
        "done",
        str(video_path.relative_to(ROOT)),
    )
    report(f"Saved: {video_path.name}")

    duration = info.get("duration")
    return DownloadedVideo(
        candidate_id=candidate.id,
        title=str(info.get("title") or candidate.title),
        source_url=candidate.url,
        local_path=video_path,
        metadata_path=metadata_path,
        platform=str(info.get("extractor_key") or info.get("extractor") or classify_url(url)),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        duration_seconds=int(duration) if isinstance(duration, (int, float)) else None,
    )


def download_selected_candidates(
    candidates: Iterable[HuntDownloadCandidate],
    search_label: str = "",
    progress: ProgressCallback | None = None,
) -> tuple[list[DownloadedVideo], list[str]]:
    selected = list(candidates)
    successes: list[DownloadedVideo] = []
    errors: list[str] = []

    for index, candidate in enumerate(selected, start=1):
        if progress:
            progress(f"[{index}/{len(selected)}] Checking {candidate.title[:70]}")
        try:
            successes.append(
                download_candidate(
                    candidate,
                    search_label=search_label,
                    progress=progress,
                )
            )
        except Exception as exc:
            message = f"{candidate.title}: {exc}"
            errors.append(message)
            add_job("hunt_download", candidate.url, "failed", str(exc))

    if successes:
        indexed = scan_local_assets()
        if progress:
            progress(f"Library refreshed: {indexed} local video files indexed.")
    return successes, errors


def dependency_status() -> tuple[bool, str]:
    try:
        yt_dlp = _load_yt_dlp()
    except RuntimeError as exc:
        return False, str(exc)
    version = getattr(getattr(yt_dlp, "version", None), "__version__", "installed")
    return True, f"yt-dlp {version}"
