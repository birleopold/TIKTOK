from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from unified_app.config import ROOT, VIDEO_EXTS
from unified_app.services.content_hunt import normalize_url

@dataclass
class DetectionResult:
    kind: str
    value: str
    label: str
    confidence: str
    actions: list[str]
    notes: list[str]


def resolve_local(value: str) -> Path | None:
    raw = value.strip().strip('"')
    if not raw:
        return None
    path = Path(raw)
    if path.exists():
        return path
    rel = ROOT / path
    if rel.exists():
        return rel
    return None


def is_tiktok_profile(url: str) -> bool:
    parsed = urlparse(url)
    return "tiktok.com" in parsed.netloc.lower() and re.search(r"/@[^/]+/?$", parsed.path)


def is_tiktok_video(url: str) -> bool:
    parsed = urlparse(url)
    return "tiktok.com" in parsed.netloc.lower() and ("/video/" in parsed.path or "/t/" in parsed.path)


def is_youtube(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def detect_input(value: str) -> DetectionResult:
    value = value.strip()
    local = resolve_local(value)
    if local:
        if local.is_dir():
            return DetectionResult(
                "local_folder",
                str(local),
                "Local folder",
                "high",
                ["Scan videos", "Detect duplicates", "Batch rename", "Make drafts", "Export posting plan"],
                ["Folder workflows stay local and do not need API keys."],
            )
        if local.suffix.lower() in VIDEO_EXTS:
            return DetectionResult(
                "local_video",
                str(local),
                "Local video",
                "high",
                ["Generate caption ideas", "Copy to upload folder", "Make TikTok-ready version", "Create draft"],
                ["Video preparation can later add resize, trim, captions, and audio normalization."],
            )
        return DetectionResult("local_file", str(local), "Local file", "medium", ["Open folder", "Save note"], ["This file is not a known video format."])

    looks_like_url = bool(re.match(r"^https?://", value, re.I) or re.match(r"^(www\.)?[^\s/]+\.[A-Za-z]{2,}(/.*)?$", value))
    if not looks_like_url:
        return DetectionResult(
            "text",
            value,
            "Plain text idea",
            "medium",
            ["Generate hooks", "Generate captions", "Generate hashtags", "Create draft note"],
            ["No network needed for text idea generation."],
        )

    url = normalize_url(value)
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        if is_tiktok_profile(url):
            username = parsed.path.strip("/").lstrip("@")
            return DetectionResult(
                "tiktok_profile",
                url,
                f"TikTok profile @{username}",
                "high",
                ["Analyze public profile", "List recent public videos", "Save as source", "Generate content gaps", "Make draft ideas"],
                ["Uses public/browser-readable page data where possible; TikTok page changes can break scraping."],
            )
        if is_tiktok_video(url):
            return DetectionResult(
                "tiktok_video",
                url,
                "TikTok video link",
                "high",
                ["Download metadata", "Generate title ideas", "Generate captions", "Create repost plan", "Save candidate"],
                ["Review reuse rights before reposting third-party media."],
            )
        if is_youtube(url):
            return DetectionResult(
                "youtube",
                url,
                "YouTube/Shorts link",
                "high",
                ["Prepare for TikTok upload", "Generate caption/hashtags", "Create draft", "Save candidate"],
                ["Uploader can import YouTube links through yt-dlp when available."],
            )
        return DetectionResult(
            "web",
            url,
            "Public web/source link",
            "medium",
            ["Hunt metadata", "Save as source", "Generate captions", "Make draft"],
            ["Best for research, inspiration, owned or permitted sources."],
        )

    return DetectionResult(
        "text",
        value,
        "Plain text idea",
        "medium",
        ["Generate hooks", "Generate captions", "Generate hashtags", "Create draft note"],
        ["No network needed for text idea generation."],
    )


def format_detection(result: DetectionResult) -> str:
    lines = [
        f"Detected: {result.label}",
        f"Type: {result.kind}",
        f"Confidence: {result.confidence}",
        f"Value: {result.value}",
        "",
        "Recommended actions:",
    ]
    lines.extend("  - " + action for action in result.actions)
    if result.notes:
        lines.append("")
        lines.append("Notes:")
        lines.extend("  - " + note for note in result.notes)
    return "\n".join(lines)
