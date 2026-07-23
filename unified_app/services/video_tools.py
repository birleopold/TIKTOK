from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from unified_app.config import READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets


def safe_slug(text: str, limit: int = 70) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip()).strip("-").lower()
    return (slug or "untitled")[:limit]


def prepare_video_for_upload(path_value: str) -> tuple[bool, str]:
    source = Path(path_value)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists() or source.suffix.lower() not in VIDEO_EXTS:
        return False, f"Not a supported local video: {source}"
    READY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = READY_DIR / f"{stamp}-{safe_slug(source.stem)}{source.suffix.lower()}"
    try:
        shutil.copy2(source, target)
    except Exception as exc:
        add_job("prepare", str(source), "failed", str(exc))
        return False, f"Copy failed: {exc}"
    add_job("prepare", str(source), "done", f"Copied to {target.relative_to(ROOT)}")
    scan_local_assets()
    return True, f"Ready for upload: {target.relative_to(ROOT)}"
