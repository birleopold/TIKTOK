from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DB_PATH = ROOT / "creator_library.db"
EXPORT_DIR = ROOT / "exports"
READY_DIR = ROOT / "TiktokAutoUploader-main" / "VideosDirPath"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CreatorResearch/1.0"
STOPWORDS = set("a an and are as at be but by for from has have how i in into is it its me my of on or our the their this to was we with you your tiktok video viral official new best top full more most just about after before day days".split())

DEPENDENCY_GROUPS = {
    "Unified app": ("tkinter",),
    "TikTok Auto Uploader": ("bs4", "fake_useragent", "moviepy", "PIL", "requests", "selenium", "sqlmodel", "yt_dlp", "undetected_chromedriver"),
    "ShortGPT": ("edge_tts", "gradio", "moviepy", "openai", "tinydb", "yt_dlp"),
    "Compilation Generator": ("PyQt5", "cv2", "mysql", "pydub", "pyftpdlib", "requests"),
    "tiktok-uploader Library": ("playwright", "pydantic", "pytz", "toml"),
    "tiktokpy": ("requests",),
}

PIP_HINTS = (
    "python -m pip install -r TiktokAutoUploader-main\\requirements.txt",
    "python -m pip install -r ShortGPT-stable\\requirements.txt",
    "python -m pip install -r TikTok-Compilation-Video-Generator-master\\requirements.txt",
)

@dataclass(frozen=True)
class Action:
    label: str
    description: str
    runner: Callable[[], tuple[bool, str]]
    folder: str | None = None
    script: str | None = None

@dataclass(frozen=True)
class Project:
    name: str
    folder: str
    category: str
    status: str
    summary: str
    features: tuple[str, ...]
    actions: tuple[Action, ...] = field(default_factory=tuple)

    @property
    def path(self) -> Path:
        return ROOT / self.folder

@dataclass
class Candidate:
    url: str
    title: str
    description: str
    source_type: str
    media_urls: list[str]
    notes: str = ""
