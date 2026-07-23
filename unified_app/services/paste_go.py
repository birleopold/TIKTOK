from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from unified_app.config import READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.content_hunt import analyze_url, hunt_urls, save_candidate, save_source
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack, save_draft
from unified_app.services.input_detector import DetectionResult, detect_input, format_detection
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets
from unified_app.services.tiktok_profile import analyze_tiktok_profile_url, format_profile_report
from unified_app.services.video_tools import prepare_video_for_upload, safe_slug

@dataclass
class PasteGoResult:
    detection: DetectionResult
    report: str
    primary_action: str
    created: list[str]


def file_fingerprint(path: Path, sample_bytes: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    h.update(str(path.stat().st_size).encode())
    with path.open("rb") as f:
        h.update(f.read(sample_bytes))
    return h.hexdigest()


def folder_video_inventory(folder: Path) -> tuple[list[Path], dict[str, list[Path]]]:
    videos = sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS])
    groups: dict[str, list[Path]] = {}
    for video in videos:
        try:
            fp = file_fingerprint(video)
        except OSError:
            continue
        groups.setdefault(fp, []).append(video)
    duplicates = {fp: paths for fp, paths in groups.items() if len(paths) > 1}
    return videos, duplicates


def clean_rename_folder(folder: Path) -> tuple[int, list[str]]:
    renamed = 0
    notes: list[str] = []
    for video in sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]):
        clean = safe_slug(video.stem)
        target = video.with_name(clean + video.suffix.lower())
        if target == video:
            continue
        counter = 2
        while target.exists():
            target = video.with_name(f"{clean}-{counter}{video.suffix.lower()}")
            counter += 1
        try:
            video.rename(target)
            renamed += 1
            notes.append(f"{video.name} -> {target.name}")
        except OSError as exc:
            notes.append(f"Could not rename {video.name}: {exc}")
    add_job("organize", str(folder), "done", f"Renamed {renamed} videos")
    return renamed, notes


def extract_tiktok_video_links(candidate_url: str) -> list[str]:
    try:
        page = analyze_url(candidate_url)
    except Exception:
        return []
    # analyze_url extracts href/src links, but TikTok often embeds URLs in scripts.
    links = set(page.media_urls)
    try:
        from unified_app.services.content_hunt import fetch_url
        text = fetch_url(candidate_url)
        for match in re.findall(r"https://www\.tiktok\.com/@[^\"'\\< ]+/video/\d+", text):
            links.add(match)
    except Exception:
        pass
    return sorted([x for x in links if "tiktok.com" in x and "/video/" in x])[:50]


def analyze_tiktok_profile(result: DetectionResult) -> PasteGoResult:
    profile = analyze_tiktok_profile_url(result.value)
    report = format_detection(result) + "\n\n" + format_profile_report(profile)
    add_job("paste_go", result.value, "done", "Analyzed TikTok profile")
    return PasteGoResult(result, report, "saved_profile_snapshot", ["saved source", "saved profile snapshot"])


def analyze_link(result: DetectionResult) -> PasteGoResult:
    cands, errs = hunt_urls([result.value])
    if cands:
        c = cands[0]
        pack = content_pack(c.title, c.description)
        save_draft(c.source_type, c.url, c.title, c.description)
        created = ["saved candidate", "created draft"]
        report = [format_detection(result), "", f"Metadata title: {c.title}"]
        if c.description:
            report.append(f"Description: {c.description[:600]}")
        report += [f"Media/page links found: {len(c.media_urls)}", "", "Caption pack:", "Hashtags: " + " ".join(pack["hashtags"]), "Hooks:"]
        report += ["  - " + x for x in pack["hooks"]]
        report += ["Captions:"] + ["  - " + x for x in pack["captions"]]
        if result.kind == "youtube":
            report += ["", "YouTube prep:", "  - Draft created", "  - Use Upload Video workflow or uploader CLI with the YouTube URL", "  - The uploader can download via yt-dlp when available"]
    else:
        created = []
        report = [format_detection(result), "", "Metadata fetch failed."] + ["  - " + e for e in errs]
    add_job("paste_go", result.value, "done" if cands else "failed", result.kind)
    return PasteGoResult(result, "\n".join(report), "created_draft" if cands else "none", created)


def analyze_local_video(result: DetectionResult) -> PasteGoResult:
    path = Path(result.value)
    pack = content_pack(path.stem, str(path))
    save_draft("local", str(path), path.stem, str(path))
    report = [format_detection(result), "", "Local video draft created.", f"File: {path}", f"Size: {path.stat().st_size:,} bytes", "", "Caption pack:", "Hashtags: " + " ".join(pack["hashtags"]), "Captions:"]
    report += ["  - " + x for x in pack["captions"]]
    add_job("paste_go", str(path), "done", "Analyzed local video")
    return PasteGoResult(result, "\n".join(report), "prepare_video", ["created draft"])


def analyze_local_folder(result: DetectionResult) -> PasteGoResult:
    folder = Path(result.value)
    videos, duplicates = folder_video_inventory(folder)
    scan_local_assets()
    report = [format_detection(result), "", "Folder inventory:", f"  Videos found: {len(videos)}", f"  Duplicate groups: {len(duplicates)}"]
    if videos:
        report += ["", "First videos:"] + ["  - " + str(v.relative_to(folder)) for v in videos[:12]]
    if duplicates:
        report += ["", "Duplicate groups:"]
        for paths in list(duplicates.values())[:5]:
            report.append("  - " + " | ".join(p.name for p in paths))
    add_job("paste_go", str(folder), "done", f"Folder inventory {len(videos)} videos")
    return PasteGoResult(result, "\n".join(report), "batch_prepare", ["indexed local assets"])


def analyze_text(result: DetectionResult) -> PasteGoResult:
    pack = content_pack(result.value, "")
    save_draft("idea", result.value, result.value[:120], result.value)
    report = [format_detection(result), "", "Idea draft created.", "Hashtags: " + " ".join(pack["hashtags"]), "Hooks:"]
    report += ["  - " + x for x in pack["hooks"]]
    report += ["Captions:"] + ["  - " + x for x in pack["captions"]]
    add_job("paste_go", result.value, "done", "Text idea draft")
    return PasteGoResult(result, "\n".join(report), "created_draft", ["created draft"])


def analyze_value(value: str) -> PasteGoResult:
    result = detect_input(value)
    if result.kind == "tiktok_profile":
        return analyze_tiktok_profile(result)
    if result.kind in {"tiktok_video", "youtube", "web"}:
        return analyze_link(result)
    if result.kind == "local_video":
        return analyze_local_video(result)
    if result.kind == "local_folder":
        return analyze_local_folder(result)
    return analyze_text(result)


def run_primary_action(result: DetectionResult) -> tuple[bool, str]:
    if result.kind == "local_video":
        return prepare_video_for_upload(result.value)
    if result.kind == "local_folder":
        folder = Path(result.value)
        renamed, notes = clean_rename_folder(folder)
        scan_local_assets()
        return True, f"Organized folder. Renamed {renamed} videos."
    if result.kind in {"tiktok_profile", "web"}:
        ok, msg = save_source(result.value, result.label)
        return ok, msg
    if result.kind in {"tiktok_video", "youtube"}:
        cands, errs = hunt_urls([result.value])
        if cands:
            c = cands[0]
            save_draft(c.source_type, c.url, c.title, c.description)
            return True, "Saved candidate and created draft"
        return False, "; ".join(errs) if errs else "No metadata fetched"
    if result.kind == "text":
        save_draft("idea", result.value, result.value[:120], result.value)
        return True, "Created idea draft"
    return False, "No primary action for this input"
