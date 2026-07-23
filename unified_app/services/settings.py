from __future__ import annotations

from dataclasses import dataclass

from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job

DEFAULT_SETTINGS = {
    "brand_name": "",
    "tiktok_handle": "",
    "default_account": "",
    "watermark": "@yourpage",
    "default_hashtags": "#TikTok",
    "caption_style": "clear, useful, direct",
    "posting_hour": "18",
    "batch_limit": "3",
}


@dataclass
class BrandSettings:
    brand_name: str
    tiktok_handle: str
    default_account: str
    watermark: str
    default_hashtags: str
    caption_style: str
    posting_hour: int
    batch_limit: int


def ensure_settings() -> None:
    init_db()
    with connect() as db:
        for key, value in DEFAULT_SETTINGS.items():
            db.execute("insert or ignore into app_settings(key,value,updated_at) values (?,?,?)", (key, value, now_iso()))
        db.commit()


def get_setting(key: str, default: str = "") -> str:
    ensure_settings()
    with connect() as db:
        row = db.execute("select value from app_settings where key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    ensure_settings()
    with connect() as db:
        db.execute(
            "insert into app_settings(key,value,updated_at) values (?,?,?) on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value), now_iso()),
        )
        db.commit()
    add_job("settings", key, "done", "Setting updated")


def all_settings() -> dict[str, str]:
    ensure_settings()
    with connect() as db:
        rows = db.execute("select key,value from app_settings order by key").fetchall()
    data = dict(rows)
    for key, value in DEFAULT_SETTINGS.items():
        data.setdefault(key, value)
    return data


def brand_settings() -> BrandSettings:
    data = all_settings()
    def as_int(key: str, default: int) -> int:
        try:
            return int(data.get(key, str(default)))
        except ValueError:
            return default
    return BrandSettings(
        brand_name=data.get("brand_name", ""),
        tiktok_handle=data.get("tiktok_handle", ""),
        default_account=data.get("default_account", ""),
        watermark=data.get("watermark", "@yourpage") or "@yourpage",
        default_hashtags=data.get("default_hashtags", "#TikTok"),
        caption_style=data.get("caption_style", "clear, useful, direct"),
        posting_hour=max(0, min(23, as_int("posting_hour", 18))),
        batch_limit=max(1, min(50, as_int("batch_limit", 3))),
    )


def format_settings() -> str:
    data = all_settings()
    lines = ["Brand Profile & Defaults"]
    for key in sorted(DEFAULT_SETTINGS):
        lines.append(f"  - {key}: {data.get(key, '')}")
    return "\n".join(lines)
