from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

from unified_app.config import EXPORT_DIR, READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.automations import run_ffmpeg
from unified_app.services.jobs import add_job
from unified_app.services.settings import brand_settings
from unified_app.services.library import scan_local_assets
from unified_app.services.video_tools import safe_slug


def _resolve_video(value: str) -> Path:
    source = Path(value.strip().strip('"'))
    if not source.is_absolute():
        source = ROOT / source
    return source


def _validate_video(source: Path) -> tuple[bool, str]:
    if not source.exists() or source.suffix.lower() not in VIDEO_EXTS:
        return False, f"Missing supported video: {source}"
    return True, ""


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("%", "\\%")
    return text


def _wrapped_lines(text: str, width: int = 28, max_lines: int = 4) -> list[str]:
    clean = " ".join(text.strip().split()) or "New video"
    lines = textwrap.wrap(clean, width=width)[:max_lines]
    return lines or [clean[:width]]


def _caption_filter(text: str, y_start: str = "h-430", font_size: int = 58) -> str:
    lines = _wrapped_lines(text)
    filters = ["drawbox=x=70:y=ih-470:w=iw-140:h=260:color=black@0.55:t=fill"]
    for index, line in enumerate(lines):
        y = f"{y_start}+{index * (font_size + 12)}"
        filters.append(
            "drawtext=text='" + _escape_drawtext(line) +
            f"':fontcolor=white:fontsize={font_size}:borderw=3:bordercolor=black:x=(w-text_w)/2:y={y}"
        )
    return ",".join(filters)


def _watermark_filter(text: str, font_size: int = 38) -> str:
    clean = text.strip() or brand_settings().watermark or "@yourpage"
    return "drawtext=text='" + _escape_drawtext(clean) + f"':fontcolor=white@0.9:fontsize={font_size}:borderw=2:bordercolor=black@0.6:x=w-text_w-48:y=48"


def burn_caption(video_value: str, caption: str, max_seconds: int = 60) -> tuple[bool, str]:
    source = _resolve_video(video_value)
    ok, msg = _validate_video(source)
    if not ok:
        return ok, msg
    READY_DIR.mkdir(parents=True, exist_ok=True)
    out = READY_DIR / f"captioned-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(source.stem)}.mp4"
    vf = _caption_filter(caption)
    args = ["-i", str(source), "-t", str(max_seconds), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy", str(out)]
    ok, msg = run_ffmpeg(args, "caption_burn", str(source))
    if ok:
        scan_local_assets()
        add_job("caption_burn", str(out), "done", "Captioned video created")
        return True, str(out)
    return False, msg


def add_watermark(video_value: str, watermark: str, max_seconds: int = 60) -> tuple[bool, str]:
    source = _resolve_video(video_value)
    ok, msg = _validate_video(source)
    if not ok:
        return ok, msg
    READY_DIR.mkdir(parents=True, exist_ok=True)
    out = READY_DIR / f"watermarked-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(source.stem)}.mp4"
    args = ["-i", str(source), "-t", str(max_seconds), "-vf", _watermark_filter(watermark), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy", str(out)]
    ok, msg = run_ffmpeg(args, "watermark", str(source))
    if ok:
        scan_local_assets()
        add_job("watermark", str(out), "done", "Watermarked video created")
        return True, str(out)
    return False, msg


def brand_video(video_value: str, caption: str, watermark: str = "", max_seconds: int = 60) -> tuple[bool, str]:
    source = _resolve_video(video_value)
    ok, msg = _validate_video(source)
    if not ok:
        return ok, msg
    READY_DIR.mkdir(parents=True, exist_ok=True)
    out = READY_DIR / f"branded-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(source.stem)}.mp4"
    vf = _caption_filter(caption) + "," + _watermark_filter(watermark)
    args = ["-i", str(source), "-t", str(max_seconds), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy", str(out)]
    ok, msg = run_ffmpeg(args, "brand_video", str(source))
    if ok:
        scan_local_assets()
        add_job("brand_video", str(out), "done", "Branded video created")
        return True, str(out)
    return False, msg


def _srt_timestamp(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02},000"


def create_srt(video_value: str, text: str, seconds_per_card: int = 3) -> tuple[bool, str]:
    source = _resolve_video(video_value)
    ok, msg = _validate_video(source)
    if not ok:
        return ok, msg
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"captions-{safe_slug(source.stem)}.srt"
    chunks = textwrap.wrap(" ".join(text.strip().split()) or source.stem, width=42) or [source.stem]
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        start = (index - 1) * seconds_per_card
        end = start + seconds_per_card
        lines += [str(index), f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}", chunk, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    add_job("srt", str(out), "done", "Caption SRT created")
    return True, str(out)
