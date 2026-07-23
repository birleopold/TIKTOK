from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from unified_app.config import EXPORT_DIR, ROOT, VIDEO_EXTS
from unified_app.services.automations import clean_rename_folder, duplicate_report, video_files_under
from unified_app.services.jobs import add_job
from unified_app.services.ready_package import ReadyPackage, make_ready_package
from unified_app.services.settings import brand_settings
from unified_app.services.upload_queue import add_to_queue


@dataclass
class BatchCampaignResult:
    folder: Path
    scanned: int
    processed: int
    queued: int
    failed: int
    report_path: Path
    lines: list[str]


def _resolve_folder(value: str) -> Path:
    folder = Path(value.strip().strip('"'))
    if not folder.is_absolute():
        folder = ROOT / folder
    return folder


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_batch_campaign(folder_value: str, limit: int = 5, queue: bool = False, account: str = "", rename: bool = True) -> tuple[bool, BatchCampaignResult | None, str]:
    folder = _resolve_folder(folder_value)
    if not folder.exists() or not folder.is_dir():
        return False, None, f"Missing folder: {folder}"
    settings = brand_settings()
    if not limit:
        limit = settings.batch_limit
    if not account:
        account = settings.default_account
    limit = max(1, min(50, int(limit or settings.batch_limit)))
    lines: list[str] = []
    if rename:
        renamed, notes = clean_rename_folder(str(folder))
        lines.append(f"Clean rename: {renamed} files")
        lines.extend("  " + note for note in notes[:20])
    dup_path, dup_groups, dup_files = duplicate_report(str(folder))
    lines.append(f"Duplicate report: {_rel(dup_path)} ({dup_groups} groups, {dup_files} files)")
    videos = video_files_under(folder)
    skipped = [p for p in videos if p.stat().st_size < 1024]
    valid_videos = [p for p in videos if p.stat().st_size >= 1024]
    if skipped:
        lines.append(f"Skipped tiny/broken-looking files: {len(skipped)}")
        lines.extend("  skipped " + _rel(p) for p in skipped[:20])
    selected = valid_videos[:limit]
    EXPORT_DIR.mkdir(exist_ok=True)
    report = EXPORT_DIR / f"batch-campaign-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    processed = 0
    queued = 0
    failed = 0
    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "status", "ready_video", "draft_key", "asset_key", "queued", "message"])
        for video in selected:
            ok, package, msg = make_ready_package(str(video))
            if not ok or package is None:
                failed += 1
                writer.writerow([_rel(video), "failed", "", "", "", "no", msg])
                lines.append(f"FAILED {_rel(video)}: {msg[:180]}")
                continue
            processed += 1
            queued_msg = "no"
            if queue and package.ready_video:
                q_ok, q_msg = add_to_queue(str(package.ready_video), title=package.title, caption=package.caption, account=account, library_key=package.draft_key)
                queued_msg = q_msg
                if q_ok:
                    queued += 1
            writer.writerow([_rel(video), "ready", _rel(package.ready_video) if package.ready_video else "", package.draft_key, package.asset_key, queued_msg, msg.replace("\n", " | ")[:500]])
            lines.append(f"READY {_rel(video)} -> {_rel(package.ready_video) if package.ready_video else 'none'}")
    result = BatchCampaignResult(folder, len(valid_videos), processed, queued, failed, report, lines)
    add_job("batch_campaign", str(folder), "done" if failed == 0 else "partial", f"Processed {processed}, queued {queued}, failed {failed}")
    return True, result, format_batch_campaign(result)


def format_batch_campaign(result: BatchCampaignResult) -> str:
    lines = [
        "Batch Campaign Builder",
        f"Folder: {result.folder}",
        f"Videos scanned: {result.scanned}",
        f"Processed: {result.processed}",
        f"Queued: {result.queued}",
        f"Failed: {result.failed}",
        f"Report: {result.report_path}",
        "",
        "Details:",
    ]
    lines += result.lines or ["  No videos processed."]
    return "\n".join(lines)
