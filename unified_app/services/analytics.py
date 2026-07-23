from __future__ import annotations

from datetime import datetime
from pathlib import Path

from unified_app.config import EXPORT_DIR
from unified_app.services.db import connect, init_db
from unified_app.services.jobs import add_job


def _counts(table: str, field: str = "status") -> dict[str, int]:
    init_db()
    with connect() as db:
        return {str(k): int(v) for k, v in db.execute(f"select {field},count(*) from {table} group by {field}")}


def pipeline_metrics() -> dict[str, dict[str, int]]:
    init_db()
    metrics = {
        "drafts": _counts("drafts"),
        "assets": _counts("local_assets"),
        "candidates": _counts("content_candidates"),
        "queue": _counts("upload_queue"),
        "accounts": _counts("tiktok_accounts"),
    }
    with connect() as db:
        metrics["totals"] = {
            "sources": db.execute("select count(*) from content_sources").fetchone()[0],
            "profile_snapshots": db.execute("select count(*) from profile_snapshots").fetchone()[0],
            "jobs": db.execute("select count(*) from jobs").fetchone()[0],
        }
    return metrics


def next_actions(metrics: dict[str, dict[str, int]]) -> list[str]:
    actions: list[str] = []
    if metrics["accounts"].get("healthy", 0) == 0:
        actions.append("Import TikTok cookies or run Login / Re-login before real uploads.")
    if metrics["drafts"].get("ready", 0) == 0 and metrics["assets"].get("ready", 0) == 0:
        actions.append("Run Full Ready Package on at least one local video.")
    if metrics["queue"].get("queued", 0) == 0 and (metrics["drafts"].get("ready", 0) or metrics["assets"].get("ready", 0)):
        actions.append("Queue ready videos for upload.")
    if metrics["drafts"].get("draft", 0) > metrics["drafts"].get("scheduled", 0) + 5:
        actions.append("Schedule the next 7 draft posts so the calendar stays moving.")
    if metrics["candidates"].get("candidate", 0) < 5:
        actions.append("Add more owned/permitted sources through Content Hunt or Paste & Go.")
    if not actions:
        actions.append("Pipeline is in good shape: keep creating, queueing, uploading, and marking uploads done.")
    return actions


def format_analytics_report() -> str:
    metrics = pipeline_metrics()
    lines = ["Creator Pipeline Analytics", ""]
    for section in ("drafts", "assets", "candidates", "queue", "accounts", "totals"):
        lines.append(section.title() + ":")
        data = metrics.get(section, {})
        if data:
            lines += [f"  - {k}: {v}" for k, v in sorted(data.items())]
        else:
            lines.append("  - none: 0")
        lines.append("")
    lines.append("Recommended next actions:")
    lines += ["  - " + action for action in next_actions(metrics)]
    return "\n".join(lines).rstrip()


def export_analytics_report() -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    out = EXPORT_DIR / f"creator-pipeline-analytics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    out.write_text(format_analytics_report(), encoding="utf-8")
    add_job("analytics", str(out), "done", "creator pipeline analytics exported")
    return out
