from __future__ import annotations

import json
import os
import pickle
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from unified_app.config import PYTHON, READY_DIR, ROOT, VIDEO_EXTS
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job
from unified_app.services.production_library import production_rows, update_item_status
from unified_app.services.settings import brand_settings
from unified_app.services.browser_cookies import format_browser_profiles, read_tiktok_cookies

UPLOADER_DIR = ROOT / "TiktokAutoUploader-main"
COOKIES_DIR = UPLOADER_DIR / "CookiesDir"
COOKIE_PREFIX = "tiktok_session-"


@dataclass
class AccountHealth:
    username: str
    cookie_path: str
    status: str
    has_sessionid: bool
    message: str


@dataclass
class QueueItem:
    id: int
    source_ref: str
    title: str
    caption: str
    account: str
    status: str
    scheduled_for: str
    library_key: str
    uploader_command: str
    last_message: str
    created_at: str


def _cookie_file(username: str) -> Path:
    return COOKIES_DIR / f"{COOKIE_PREFIX}{username}.cookie"


def _account_from_cookie(path: Path) -> str:
    name = path.name
    if name.startswith(COOKIE_PREFIX) and name.endswith(".cookie"):
        return name[len(COOKIE_PREFIX):-len(".cookie")]
    return path.stem


def _has_sessionid(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            cookies = pickle.load(f)
    except Exception:
        return False
    if isinstance(cookies, dict):
        cookies = list(cookies.values())
    return any(isinstance(c, dict) and c.get("name") == "sessionid" and c.get("value") for c in cookies or [])



def _normalize_cookie(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = raw.get("name") or raw.get("Name")
    value = raw.get("value") or raw.get("Value")
    if not name or value is None:
        return None
    domain = raw.get("domain") or raw.get("Domain") or ".tiktok.com"
    path = raw.get("path") or raw.get("Path") or "/"
    cookie = {
        "name": str(name),
        "value": str(value),
        "domain": str(domain),
        "path": str(path),
        "secure": bool(raw.get("secure", raw.get("Secure", True))),
        "httpOnly": bool(raw.get("httpOnly", raw.get("http_only", raw.get("HttpOnly", False)))),
    }
    expiry = raw.get("expiry", raw.get("expirationDate", raw.get("expires", raw.get("Expires"))))
    if expiry not in (None, "", 0):
        try:
            cookie["expiry"] = int(float(expiry))
        except (TypeError, ValueError):
            pass
    same_site = raw.get("sameSite") or raw.get("same_site")
    if same_site:
        cookie["sameSite"] = str(same_site)
    return cookie


def _cookies_from_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, dict):
        for key in ("cookies", "Cookies", "cookieStore", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if isinstance(data, dict):
        data = list(data.values())
    if not isinstance(data, list):
        raise ValueError("JSON cookie export must be a list or contain a cookies list")
    return [c for c in (_normalize_cookie(item) for item in data) if c]


def _cookies_from_netscape(path: Path) -> list[dict]:
    cookies: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            parts = line.split()
        if len(parts) < 7:
            continue
        domain, _include_subdomains, cookie_path, secure, expires, name, value = parts[:7]
        raw = {"domain": domain, "path": cookie_path, "secure": secure.upper() == "TRUE", "expiry": expires, "name": name, "value": value}
        normalized = _normalize_cookie(raw)
        if normalized:
            cookies.append(normalized)
    return cookies


def import_cookie_file(username: str, cookie_file: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Account name is required"
    source = Path(cookie_file)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        return False, f"Cookie file not found: {source}"
    try:
        if source.suffix.lower() == ".cookie":
            with source.open("rb") as f:
                loaded = pickle.load(f)
            cookies = [c for c in (_normalize_cookie(item) for item in (loaded.values() if isinstance(loaded, dict) else loaded)) if c]
        elif source.suffix.lower() == ".json":
            cookies = _cookies_from_json(source)
        else:
            cookies = _cookies_from_netscape(source)
    except Exception as exc:
        add_job("account_import", username, "failed", str(exc))
        return False, f"Could not read cookie file: {exc}"
    if not cookies:
        return False, "No usable cookies found in the selected file"
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    target = _cookie_file(username)
    with target.open("wb") as f:
        pickle.dump(cookies, f)
    accounts = sync_accounts()
    health = next((a for a in accounts if a.username == username), None)
    if health and health.has_sessionid:
        msg = f"Imported healthy TikTok session for {username}: {target}"
        add_job("account_import", username, "done", msg)
        return True, msg
    msg = f"Imported cookies for {username}, but no sessionid was found. Export TikTok cookies while logged in or use Login / Re-login."
    add_job("account_import", username, "partial", msg)
    return False, msg


def import_browser_session(username: str, browser: str = "auto", profile: str = "") -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Account name is required"
    cookies, source_message = read_tiktok_cookies(browser, profile)
    if not cookies:
        add_job("browser_cookie_import", username, "failed", source_message)
        return False, source_message + "\n\n" + format_browser_profiles()
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    target = _cookie_file(username)
    with target.open("wb") as f:
        pickle.dump(cookies, f)
    accounts = sync_accounts()
    health = next((a for a in accounts if a.username == username), None)
    if health and health.has_sessionid:
        msg = f"{source_message}. Saved healthy TikTok session for {username}: {target}"
        add_job("browser_cookie_import", username, "done", msg)
        return True, msg
    msg = f"{source_message}, but the saved cookies did not include a usable sessionid. Open TikTok in your browser and make sure you are logged in."
    add_job("browser_cookie_import", username, "partial", msg)
    return False, msg

def sync_accounts() -> list[AccountHealth]:
    init_db()
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    accounts: list[AccountHealth] = []
    for path in sorted(COOKIES_DIR.glob(f"{COOKIE_PREFIX}*.cookie")):
        username = _account_from_cookie(path)
        has_session = _has_sessionid(path)
        status = "healthy" if has_session else "expired"
        message = "sessionid cookie found" if has_session else "cookie file exists but no sessionid was found; login again"
        accounts.append(AccountHealth(username, str(path), status, has_session, message))
    seen = {acct.username for acct in accounts}
    with connect() as db:
        for acct in accounts:
            db.execute(
                """insert into tiktok_accounts(username,cookie_path,status,last_checked_at,notes,created_at)
                   values (?,?,?,?,?,?) on conflict(username) do update set
                   cookie_path=excluded.cookie_path, status=excluded.status,
                   last_checked_at=excluded.last_checked_at, notes=excluded.notes""",
                (acct.username, acct.cookie_path, acct.status, now_iso(), acct.message, now_iso()),
            )
        for username, cookie_path in db.execute("select username,cookie_path from tiktok_accounts").fetchall():
            if username not in seen or not Path(cookie_path).exists():
                db.execute(
                    "update tiktok_accounts set status='missing', last_checked_at=?, notes=? where username=?",
                    (now_iso(), "cookie file is missing; import cookies or login again", username),
                )
        db.commit()
    add_job("accounts", "cookies", "done", f"Checked {len(accounts)} account sessions")
    return accounts


def account_rows() -> list[tuple]:
    sync_accounts()
    with connect() as db:
        return db.execute(
            "select id,username,status,cookie_path,last_checked_at,notes from tiktok_accounts order by username"
        ).fetchall()


def login_command(username: str) -> list[str]:
    return [PYTHON, "cli.py", "login", "-n", username.strip()]


def run_login(username: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Account name is required"
    cmd = login_command(username)
    try:
        proc = subprocess.run(cmd, cwd=UPLOADER_DIR, capture_output=True, text=True, timeout=900)
    except Exception as exc:
        add_job("account_login", username, "failed", str(exc))
        return False, str(exc)
    sync_accounts()
    output = (proc.stdout or proc.stderr or "").strip()[-1200:]
    if proc.returncode != 0:
        add_job("account_login", username, "failed", output)
        return False, output or "Login command failed"
    add_job("account_login", username, "done", "Login command completed")
    return True, output or f"Login completed for {username}"


def _resolve_source(source_ref: str) -> Path:
    path = Path(source_ref)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _uploader_video_arg(source_ref: str) -> str:
    path = _resolve_source(source_ref)
    try:
        return str(path.relative_to(READY_DIR))
    except ValueError:
        return str(path)


def queue_ready_items(account: str = "", limit: int = 20) -> int:
    init_db()
    if not account:
        account = brand_settings().default_account
    count = 0
    rows = [r for r in production_rows(500) if r.status in {"ready", "scheduled"} and (r.item_type.startswith("draft/") or r.item_type == "local_video")]
    with connect() as db:
        for row in rows[:limit]:
            source = row.source.split(": ", 1)[-1]
            if not source.lower().endswith(tuple(VIDEO_EXTS)):
                continue
            exists = db.execute("select id from upload_queue where source_ref=? and status in ('queued','running','done')", (source,)).fetchone()
            if exists:
                continue
            title = row.title[:180] or Path(source).stem
            caption = row.title[:220]
            db.execute(
                """insert into upload_queue(source_ref,title,caption,account,status,scheduled_for,library_key,created_at,updated_at)
                   values (?,?,?,?,?,?,?,?,?)""",
                (source, title, caption, account or row.account or "", "queued", row.scheduled_for or None, row.key, now_iso(), now_iso()),
            )
            count += 1
        db.commit()
    add_job("upload_queue", "ready_items", "done", f"Queued {count} ready items")
    return count


def add_to_queue(source_ref: str, title: str = "", caption: str = "", account: str = "", scheduled_for: str = "", library_key: str = "") -> tuple[bool, str]:
    init_db()
    source = _resolve_source(source_ref)
    if not source.exists() or source.suffix.lower() not in VIDEO_EXTS:
        return False, f"Missing supported video: {source}"
    rel = str(source.relative_to(ROOT)) if str(source).lower().startswith(str(ROOT).lower()) else str(source)
    if not account:
        account = brand_settings().default_account
    title = title.strip() or source.stem
    caption = caption.strip() or title
    with connect() as db:
        db.execute(
            """insert into upload_queue(source_ref,title,caption,account,status,scheduled_for,library_key,created_at,updated_at)
               values (?,?,?,?,?,?,?,?,?)""",
            (rel, title[:180], caption[:2200], account.strip(), "queued", scheduled_for or None, library_key, now_iso(), now_iso()),
        )
        db.commit()
    add_job("upload_queue", rel, "done", "Added item to upload queue")
    return True, f"Queued {rel}"


def queue_rows(limit: int = 100) -> list[QueueItem]:
    init_db()
    with connect() as db:
        rows = db.execute(
            """select id,source_ref,title,caption,account,status,coalesce(scheduled_for,''),library_key,
                      uploader_command,last_message,created_at from upload_queue order by id desc limit ?""",
            (limit,),
        ).fetchall()
    return [QueueItem(*row) for row in rows]


def build_upload_command(item: QueueItem, schedule_seconds: int = 0) -> list[str]:
    cmd = [PYTHON, "cli.py", "upload", "-u", item.account, "-v", _uploader_video_arg(item.source_ref), "-t", item.caption or item.title]
    if schedule_seconds > 0:
        cmd += ["-sc", str(schedule_seconds)]
    return cmd


def run_queue_item(item_id: int, dry_run: bool = True) -> tuple[bool, str]:
    init_db()
    with connect() as db:
        row = db.execute(
            """select id,source_ref,title,caption,account,status,coalesce(scheduled_for,''),library_key,
                      uploader_command,last_message,created_at from upload_queue where id=?""",
            (item_id,),
        ).fetchone()
    if not row:
        return False, f"Queue item not found: {item_id}"
    item = QueueItem(*row)
    if not item.account:
        return False, "Choose an account before running this upload"
    cmd = build_upload_command(item)
    command_text = " ".join(shlex.quote(x) for x in cmd)
    if dry_run:
        health = {r[1]: r[2] for r in account_rows()}
        health_note = "" if health.get(item.account) == "healthy" else "\nWarning: account '" + item.account + "' is not healthy yet; login/re-login before real upload."
        command_text = command_text + health_note
        with connect() as db:
            db.execute("update upload_queue set uploader_command=?, last_message=?, updated_at=? where id=?", (command_text, "Dry run command prepared", now_iso(), item_id))
            db.commit()
        return True, command_text
    health = {r[1]: r[2] for r in account_rows()}
    if health.get(item.account) != "healthy":
        return False, f"Account '{item.account}' is not healthy. Use login/re-login first."
    with connect() as db:
        db.execute("update upload_queue set status='running', uploader_command=?, updated_at=? where id=?", (command_text, now_iso(), item_id))
        db.commit()
    try:
        proc = subprocess.run(cmd, cwd=UPLOADER_DIR, capture_output=True, text=True, timeout=1800)
    except Exception as exc:
        message = str(exc)
        ok = False
    else:
        message = (proc.stdout or proc.stderr or "").strip()[-2000:]
        ok = proc.returncode == 0
    with connect() as db:
        db.execute("update upload_queue set status=?, last_message=?, updated_at=? where id=?", ("done" if ok else "failed", message, now_iso(), item_id))
        db.commit()
    if ok and item.library_key:
        update_item_status(item.library_key, "uploaded", account=item.account, notes="Uploaded through queue")
    add_job("upload", str(item_id), "done" if ok else "failed", message or command_text)
    return ok, message or command_text



def healthy_accounts() -> list[str]:
    return [row[1] for row in account_rows() if row[2] == "healthy"]


def auto_assign_healthy_account(preferred: str = "") -> tuple[int, str]:
    init_db()
    accounts = healthy_accounts()
    if preferred and preferred in accounts:
        account = preferred
    elif brand_settings().default_account in accounts:
        account = brand_settings().default_account
    elif accounts:
        account = accounts[0]
    else:
        return 0, "No healthy TikTok account session found. Use Import From Browser first."
    with connect() as db:
        db.execute("update upload_queue set account=?, updated_at=? where status in ('queued','failed') and coalesce(account,'')=''", (account, now_iso()))
        changed = db.total_changes
        db.commit()
    add_job("upload_queue", "auto_assign", "done" if changed else "skipped", f"Assigned {account} to {changed} queue items")
    return changed, f"Assigned {account} to {changed} queued items"


def upload_preflight(item_id: int) -> tuple[bool, str]:
    rows = {item.id: item for item in queue_rows(500)}
    item = rows.get(item_id)
    if not item:
        return False, f"Queue item not found: {item_id}"
    checks: list[tuple[str, bool, str]] = []
    source = _resolve_source(item.source_ref)
    checks.append(("Video file", source.exists() and source.suffix.lower() in VIDEO_EXTS, str(source)))
    checks.append(("Caption", bool((item.caption or item.title).strip()), "caption/title present" if (item.caption or item.title).strip() else "caption is empty"))
    checks.append(("Account assigned", bool(item.account.strip()), item.account or "no account"))
    health = {row[1]: row for row in account_rows()}
    acct = health.get(item.account)
    checks.append(("Account session", bool(acct and acct[2] == "healthy"), acct[5] if acct else "account not registered"))
    ok_cmd, command = run_queue_item(item_id, dry_run=True) if item.account else (False, "assign account first")
    checks.append(("Uploader command", ok_cmd and not command.startswith("Warning"), command.splitlines()[0] if command else "not built"))
    ready = all(ok for _name, ok, _note in checks)
    lines = [f"Upload Preflight: queue #{item.id}", f"Title: {item.title}", ""]
    for name, ok, note in checks:
        lines.append(("PASS" if ok else "FIX") + f" - {name}: {note}")
    lines += ["", "Result: " + ("ready to upload" if ready else "needs fixes before upload")]
    add_job("upload_preflight", str(item_id), "done" if ready else "blocked", lines[-1])
    return ready, "\n".join(lines)

def assign_queue_account(item_id: int, account: str) -> tuple[bool, str]:
    init_db()
    account = account.strip()
    if not account:
        return False, "Account name is required"
    with connect() as db:
        db.execute("update upload_queue set account=?, updated_at=? where id=? and status in ('queued','failed')", (account, now_iso(), item_id))
        changed = db.total_changes
        db.commit()
    if changed:
        add_job("upload_queue", str(item_id), "done", f"Assigned account {account}")
        return True, f"Assigned {account} to queue item {item_id}"
    return False, "Queue item not found or not editable"

def cancel_queue_item(item_id: int) -> tuple[bool, str]:
    init_db()
    with connect() as db:
        db.execute("update upload_queue set status='cancelled', updated_at=? where id=? and status in ('queued','failed')", (now_iso(), item_id))
        changed = db.total_changes
        db.commit()
    return (changed > 0, "Cancelled" if changed else "Nothing cancelled")


def queue_summary_lines() -> list[str]:
    init_db()
    with connect() as db:
        return [f"{status}: {count}" for status, count in db.execute("select status,count(*) from upload_queue group by status order by status")]
