from __future__ import annotations

from pathlib import Path

from unified_app.config import READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job


def library_counts() -> dict[str, int]:
    init_db()
    out: dict[str, int] = {}
    with connect() as db:
        for kind, count in db.execute("select source_type,count(*) from content_candidates group by source_type"):
            out[kind] = count
        out["local_assets"] = db.execute("select count(*) from local_assets").fetchone()[0]
        out["sources"] = db.execute("select count(*) from content_sources").fetchone()[0]
        out["drafts"] = db.execute("select count(*) from drafts").fetchone()[0]
        out["jobs"] = db.execute("select count(*) from jobs").fetchone()[0]
    return out


def recent_candidates(limit: int = 100) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,source_type,title,url,status,created_at from content_candidates order by id desc limit ?",
            (limit,),
        ).fetchall()


def scan_local_assets() -> int:
    init_db()
    roots = [READY_DIR, ROOT / "ShortGPT-stable" / "videos", ROOT]
    seen: set[Path] = set()
    indexed_paths: set[str] = set()
    count = 0
    with connect() as db:
        for base in roots:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
                    continue
                try:
                    st = path.stat()
                except OSError:
                    continue
                if st.st_size <= 0:
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                rel = str(path.relative_to(ROOT))
                indexed_paths.add(rel)
                db.execute(
                    "insert into local_assets(path,size_bytes,created_at) values (?,?,?) on conflict(path) do update set size_bytes=excluded.size_bytes",
                    (rel, st.st_size, now_iso()),
                )
                count += 1
        for (asset_path,) in db.execute("select path from local_assets").fetchall():
            candidate = ROOT / asset_path
            if not candidate.exists() or candidate.stat().st_size <= 0:
                db.execute("delete from local_assets where path=?", (asset_path,))
        db.commit()
    add_job("scan", "local videos", "done", f"Indexed {count} video assets")
    return count


def recent_assets(limit: int = 100) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,path,size_bytes,status,created_at from local_assets order by id desc limit ?",
            (limit,),
        ).fetchall()
