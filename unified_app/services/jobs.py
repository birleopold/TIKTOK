from __future__ import annotations

from unified_app.services.db import connect, init_db, now_iso


def add_job(kind: str, target: str, status: str, message: str) -> None:
    init_db()
    with connect() as db:
        db.execute(
            "insert into jobs(kind,target,status,message,created_at) values (?,?,?,?,?)",
            (kind, target, status, message, now_iso()),
        )
        db.commit()


def recent_jobs(limit: int = 80) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,kind,target,status,message,created_at from jobs order by id desc limit ?",
            (limit,),
        ).fetchall()
