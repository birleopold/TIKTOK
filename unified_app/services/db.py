from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from unified_app.config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with connect() as db:
        db.execute("""create table if not exists content_candidates (
            id integer primary key autoincrement, url text unique not null,
            title text not null, description text not null, source_type text not null,
            media_urls text not null, notes text not null,
            status text not null default 'candidate', created_at text not null)""")
        db.execute("""create table if not exists local_assets (
            id integer primary key autoincrement, path text unique not null,
            size_bytes integer not null, status text not null default 'local', created_at text not null)""")
        db.execute("""create table if not exists jobs (
            id integer primary key autoincrement, kind text not null, target text not null,
            status text not null, message text not null, created_at text not null)""")
        db.execute("""create table if not exists content_sources (
            id integer primary key autoincrement, url text unique not null,
            label text not null, source_type text not null, status text not null default 'active',
            last_checked_at text, created_at text not null)""")
        db.execute("""create table if not exists drafts (
            id integer primary key autoincrement, source_type text not null, source_ref text unique not null,
            title text not null, hook text not null, caption text not null, hashtags text not null,
            status text not null default 'draft', scheduled_for text, created_at text not null)""")
        db.commit()
