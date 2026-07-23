from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from unified_app.config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, timeout=30)


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
        db.execute("""create table if not exists profile_snapshots (
            id integer primary key autoincrement, profile_url text not null, username text not null,
            nickname text not null, bio text not null, follower_count text not null,
            following_count text not null, heart_count text not null, video_count text not null,
            recent_videos text not null, hashtags text not null, content_gaps text not null,
            notes text not null, created_at text not null)""")
        _ensure_column(db, "local_assets", "duration_seconds", "real")
        _ensure_column(db, "local_assets", "resolution", "text not null default ''")
        _ensure_column(db, "local_assets", "caption", "text not null default ''")
        _ensure_column(db, "local_assets", "hashtags", "text not null default ''")
        _ensure_column(db, "local_assets", "account", "text not null default ''")
        _ensure_column(db, "local_assets", "scheduled_for", "text")
        _ensure_column(db, "local_assets", "uploaded_at", "text")
        _ensure_column(db, "local_assets", "source_project", "text not null default ''")
        _ensure_column(db, "local_assets", "notes", "text not null default ''")
        _ensure_column(db, "content_candidates", "account", "text not null default ''")
        _ensure_column(db, "content_candidates", "scheduled_for", "text")
        _ensure_column(db, "content_candidates", "uploaded_at", "text")
        _ensure_column(db, "content_candidates", "score", "integer not null default 0")
        _ensure_column(db, "content_candidates", "rights_note", "text not null default ''")
        _ensure_column(db, "content_candidates", "idea_prompt", "text not null default ''")
        _ensure_column(db, "drafts", "account", "text not null default ''")
        _ensure_column(db, "drafts", "uploaded_at", "text")
        _ensure_column(db, "drafts", "notes", "text not null default ''")
        db.execute("""create table if not exists tiktok_accounts (
            id integer primary key autoincrement, username text unique not null,
            cookie_path text not null, status text not null default 'unknown',
            last_checked_at text, notes text not null default '', created_at text not null)""")
        db.execute("""create table if not exists upload_queue (
            id integer primary key autoincrement, source_ref text not null, title text not null,
            caption text not null, account text not null default '', status text not null default 'queued',
            scheduled_for text, library_key text not null default '', uploader_command text not null default '',
            last_message text not null default '', created_at text not null, updated_at text not null)""")
        db.execute("""create table if not exists app_settings (
            key text primary key not null, value text not null, updated_at text not null)""")

        db.execute("""create table if not exists caption_styles (
            id integer primary key autoincrement, name text unique not null,
            template text not null, notes text not null default '', created_at text not null)""")
        db.execute("""create table if not exists hashtag_sets (
            id integer primary key autoincrement, name text unique not null,
            hashtags text not null, notes text not null default '', created_at text not null)""")
        db.execute("""create table if not exists content_templates (
            id integer primary key autoincrement, name text unique not null,
            hook_template text not null, caption_template text not null,
            hashtags text not null, notes text not null default '', created_at text not null)""")
        db.execute("""create table if not exists upload_results (
            id integer primary key autoincrement, queue_id integer, library_key text not null default '',
            source_ref text not null default '', tiktok_url text not null, account text not null default '',
            caption text not null default '', uploaded_at text not null, views integer not null default 0,
            likes integer not null default 0, comments integer not null default 0, shares integer not null default 0,
            notes text not null default '', created_at text not null)""")
        db.execute("""create table if not exists series (
            id integer primary key autoincrement, name text unique not null,
            topic text not null default '', status text not null default 'planning', created_at text not null)""")
        db.execute("""create table if not exists series_posts (
            id integer primary key autoincrement, series_id integer not null, part_no integer not null,
            title text not null, source_ref text not null default '', draft_id integer,
            status text not null default 'draft', created_at text not null,
            unique(series_id, part_no))""")
        db.execute("""create table if not exists thumbnail_choices (
            id integer primary key autoincrement, source_ref text not null,
            image_path text not null, second integer not null, selected integer not null default 0,
            created_at text not null)""")
        db.commit()


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in db.execute(f"pragma table_info({table})")}
    if column not in columns:
        db.execute(f"alter table {table} add column {column} {definition}")
