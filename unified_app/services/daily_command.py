from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

from unified_app.config import EXPORT_DIR
from unified_app.services.analytics import next_actions, pipeline_metrics
from unified_app.services.db import connect, init_db
from unified_app.services.jobs import add_job
from unified_app.services.production_library import production_rows
from unified_app.services.upload_queue import account_rows, queue_rows, queue_summary_lines


@dataclass
class DailyPlan:
    day: str
    metrics: dict[str, dict[str, int]]
    actions: list[str]
    ready: list[tuple[str, str, str, str]]
    scheduled_today: list[tuple[str, str, str, str]]
    queued: list[tuple[int, str, str, str, str]]
    blocked: list[str]


def _today_prefix() -> str:
    return date.today().isoformat()


def _ready_items(limit: int = 10) -> list[tuple[str, str, str, str]]:
    rows = []
    for item in production_rows(300):
        if item.status == "ready":
            rows.append((item.key, item.item_type, item.title, item.source))
    return rows[:limit]


def _scheduled_today(limit: int = 10) -> list[tuple[str, str, str, str]]:
    today = _today_prefix()
    rows = []
    for item in production_rows(300):
        if item.scheduled_for.startswith(today):
            rows.append((item.key, item.item_type, item.title, item.scheduled_for))
    return rows[:limit]


def _queued_items(limit: int = 10) -> list[tuple[int, str, str, str, str]]:
    rows = []
    for item in queue_rows(limit):
        if item.status == "cancelled":
            continue
        rows.append((item.id, item.status, item.account or "no account", item.title, item.source_ref))
    return rows


def _blocked_items() -> list[str]:
    blocked: list[str] = []
    accounts = account_rows()
    healthy = [row for row in accounts if row[2] == "healthy"]
    if not healthy:
        blocked.append("No healthy TikTok account session. Import cookies or run Login / Re-login.")
    for item in queue_rows(50):
        if item.status == "queued" and not item.account:
            blocked.append(f"Queue #{item.id} needs an account: {item.title}")
        elif item.status == "failed":
            blocked.append(f"Queue #{item.id} failed and needs retry/review: {item.last_message[:120]}")
    if not _ready_items(1):
        blocked.append("No ready library item. Run Full Ready Package or Brand Video on a local clip.")
    return blocked[:12]


def build_daily_plan() -> DailyPlan:
    init_db()
    metrics = pipeline_metrics()
    actions = next_actions(metrics)
    ready = _ready_items()
    scheduled = _scheduled_today()
    queued = _queued_items()
    blocked = _blocked_items()
    if scheduled:
        actions.insert(0, "Review today's scheduled posts and queue/upload the highest priority item.")
    if ready and not queued:
        actions.insert(0, "Queue ready videos for upload.")
    add_job("daily", _today_prefix(), "done", "Daily command plan built")
    return DailyPlan(_today_prefix(), metrics, actions[:8], ready, scheduled, queued, blocked)


def format_daily_plan(plan: DailyPlan | None = None) -> str:
    plan = plan or build_daily_plan()
    lines = [f"Daily Command Center - {plan.day}", ""]
    lines.append("Pipeline snapshot:")
    for section in ("drafts", "assets", "candidates", "queue", "accounts"):
        values = plan.metrics.get(section, {})
        text = ", ".join(f"{k}={v}" for k, v in sorted(values.items())) if values else "none=0"
        lines.append(f"  - {section}: {text}")
    lines += ["", "Today's focus:"]
    lines += ["  - " + action for action in plan.actions]
    lines += ["", "Scheduled today:"]
    lines += [f"  - {key} [{typ}] {title} at {when}" for key, typ, title, when in plan.scheduled_today] or ["  - none"]
    lines += ["", "Ready to queue/upload:"]
    lines += [f"  - {key} [{typ}] {title} -> {source}" for key, typ, title, source in plan.ready] or ["  - none"]
    lines += ["", "Upload queue:"]
    lines += [f"  - #{qid} {status} account={account} {title} -> {source}" for qid, status, account, title, source in plan.queued] or ["  - none"]
    lines += ["", "Blocked / needs attention:"]
    lines += ["  - " + item for item in plan.blocked] or ["  - none"]
    return "\n".join(lines)


def export_daily_plan() -> Path:
    EXPORT_DIR.mkdir(exist_ok=True)
    plan = build_daily_plan()
    out = EXPORT_DIR / f"daily-command-{plan.day}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["section", "item_1", "item_2", "item_3", "item_4", "item_5"])
        for action in plan.actions:
            writer.writerow(["focus", action, "", "", "", ""])
        for row in plan.scheduled_today:
            writer.writerow(["scheduled_today", *row, ""])
        for row in plan.ready:
            writer.writerow(["ready", *row, ""])
        for row in plan.queued:
            writer.writerow(["queue", *row])
        for item in plan.blocked:
            writer.writerow(["blocked", item, "", "", "", ""])
    add_job("export", str(out), "done", "daily command plan exported")
    return out


def queue_health_text() -> str:
    lines = ["Upload Queue Health"]
    summary = queue_summary_lines()
    lines += ["  - " + line for line in summary] or ["  - empty"]
    return "\n".join(lines)
