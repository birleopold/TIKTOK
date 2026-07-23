from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TIKTOK_HOST = "tiktok.com"

@dataclass
class BrowserProfile:
    browser: str
    profile: str
    cookies_path: Path
    local_state_path: Path | None = None


def _env_path(name: str) -> Path:
    value = os.environ.get(name, "")
    return Path(value) if value else Path.home()


def discover_browser_profiles() -> list[BrowserProfile]:
    local = _env_path("LOCALAPPDATA")
    roaming = _env_path("APPDATA")
    candidates: list[tuple[str, Path, Path | None]] = [
        ("chrome", local / "Google" / "Chrome" / "User Data", local / "Google" / "Chrome" / "User Data" / "Local State"),
        ("edge", local / "Microsoft" / "Edge" / "User Data", local / "Microsoft" / "Edge" / "User Data" / "Local State"),
        ("brave", local / "BraveSoftware" / "Brave-Browser" / "User Data", local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Local State"),
        ("firefox", roaming / "Mozilla" / "Firefox" / "Profiles", None),
    ]
    profiles: list[BrowserProfile] = []
    for browser, base, local_state in candidates:
        if not base.exists():
            continue
        if browser == "firefox":
            for profile_dir in sorted(base.glob("*")):
                cookies = profile_dir / "cookies.sqlite"
                if cookies.exists():
                    profiles.append(BrowserProfile(browser, profile_dir.name, cookies, None))
            continue
        for profile_dir in sorted(base.iterdir()):
            if not profile_dir.is_dir():
                continue
            if profile_dir.name not in {"Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"} and not profile_dir.name.startswith("Profile"):
                continue
            cookies = profile_dir / "Network" / "Cookies"
            if not cookies.exists():
                cookies = profile_dir / "Cookies"
            if cookies.exists():
                profiles.append(BrowserProfile(browser, profile_dir.name, cookies, local_state if local_state and local_state.exists() else None))
    return profiles


def format_browser_profiles() -> str:
    rows = discover_browser_profiles()
    if not rows:
        return "No Chrome, Edge, Brave, or Firefox cookie profiles found on this Windows account."
    lines = ["Browser profiles with cookie stores:"]
    for idx, row in enumerate(rows, start=1):
        lines.append(f"{idx}. {row.browser}/{row.profile} -> {row.cookies_path}")
    return "\n".join(lines)


def _copy_sqlite(source: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="creator-browser-cookies-")) / source.name
    shutil.copy2(source, tmp)
    wal = source.with_name(source.name + "-wal")
    shm = source.with_name(source.name + "-shm")
    if wal.exists():
        shutil.copy2(wal, tmp.with_name(tmp.name + "-wal"))
    if shm.exists():
        shutil.copy2(shm, tmp.with_name(tmp.name + "-shm"))
    return tmp


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt_unprotect_data(data: bytes) -> bytes:
    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("Windows DPAPI could not decrypt browser cookie data")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _chrome_master_key(local_state_path: Path | None) -> bytes | None:
    if not local_state_path or not local_state_path.exists():
        return None
    data = json.loads(local_state_path.read_text(encoding="utf-8", errors="replace"))
    encrypted_key = data.get("os_crypt", {}).get("encrypted_key")
    if not encrypted_key:
        return None
    raw = base64.b64decode(encrypted_key)
    if raw.startswith(b"DPAPI"):
        raw = raw[5:]
    return _crypt_unprotect_data(raw)


def _decrypt_chrome_value(value: str, encrypted: bytes, master_key: bytes | None) -> str:
    if value:
        return value
    if not encrypted:
        return ""
    if encrypted.startswith((b"v10", b"v11", b"v20")):
        if not master_key:
            return ""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted[3:15]
            ciphertext = encrypted[15:]
            return AESGCM(master_key).decrypt(nonce, ciphertext, None).decode("utf-8", errors="replace")
        except Exception:
            return ""
    try:
        return _crypt_unprotect_data(encrypted).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _chrome_expiry(expires_utc: int | None) -> int | None:
    if not expires_utc:
        return None
    try:
        # Chromium stores microseconds since 1601-01-01 UTC.
        return int((expires_utc / 1_000_000) - 11644473600)
    except Exception:
        return None


def _same_site(value) -> str | None:
    mapping = {-1: None, 0: "None", 1: "Lax", 2: "Strict"}
    try:
        return mapping.get(int(value))
    except Exception:
        return None


def _read_chromium(profile: BrowserProfile) -> list[dict]:
    db_path = _copy_sqlite(profile.cookies_path)
    master_key = _chrome_master_key(profile.local_state_path)
    cookies: list[dict] = []
    with sqlite3.connect(db_path) as db:
        rows = db.execute("""select host_key,name,value,encrypted_value,path,expires_utc,is_secure,is_httponly,samesite
                             from cookies where host_key like ?""", (f"%{TIKTOK_HOST}%",)).fetchall()
    for host, name, value, encrypted, path, expires, secure, http_only, same_site in rows:
        cookie_value = _decrypt_chrome_value(value or "", encrypted or b"", master_key)
        if not cookie_value:
            continue
        cookie = {"name": name, "value": cookie_value, "domain": host, "path": path or "/", "secure": bool(secure), "httpOnly": bool(http_only)}
        expiry = _chrome_expiry(expires)
        if expiry and expiry > 0:
            cookie["expiry"] = expiry
        ss = _same_site(same_site)
        if ss:
            cookie["sameSite"] = ss
        cookies.append(cookie)
    return cookies


def _read_firefox(profile: BrowserProfile) -> list[dict]:
    db_path = _copy_sqlite(profile.cookies_path)
    cookies: list[dict] = []
    with sqlite3.connect(db_path) as db:
        rows = db.execute("""select host,name,value,path,expiry,isSecure,isHttpOnly,sameSite
                             from moz_cookies where host like ?""", (f"%{TIKTOK_HOST}%",)).fetchall()
    for host, name, value, path, expiry, secure, http_only, same_site in rows:
        if not value:
            continue
        cookie = {"name": name, "value": value, "domain": host, "path": path or "/", "secure": bool(secure), "httpOnly": bool(http_only)}
        if expiry:
            cookie["expiry"] = int(expiry)
        ss = _same_site(same_site)
        if ss:
            cookie["sameSite"] = ss
        cookies.append(cookie)
    return cookies


def read_tiktok_cookies(browser: str = "auto", profile: str = "") -> tuple[list[dict], str]:
    profiles = discover_browser_profiles()
    browser = (browser or "auto").lower().strip()
    profile = profile.strip().lower()
    selected = []
    for item in profiles:
        if browser != "auto" and item.browser != browser:
            continue
        if profile and item.profile.lower() != profile:
            continue
        selected.append(item)
    if not selected:
        return [], f"No browser profile matched browser={browser!r} profile={profile or 'any'!r}"
    errors: list[str] = []
    for item in selected:
        try:
            cookies = _read_firefox(item) if item.browser == "firefox" else _read_chromium(item)
        except Exception as exc:
            errors.append(f"{item.browser}/{item.profile}: {exc}")
            continue
        if any(c.get("name") == "sessionid" and c.get("value") for c in cookies):
            return cookies, f"Imported TikTok session from {item.browser}/{item.profile}"
        if cookies:
            errors.append(f"{item.browser}/{item.profile}: found {len(cookies)} TikTok cookies but no sessionid; open TikTok in that browser and log in")
    return [], "; ".join(errors) if errors else "No TikTok cookies found. Open TikTok in Chrome, Edge, Brave, or Firefox and log in first."


def browser_session_health() -> list[tuple[str, str, int, str, str]]:
    rows: list[tuple[str, str, int, str, str]] = []
    for item in discover_browser_profiles():
        try:
            cookies = _read_firefox(item) if item.browser == "firefox" else _read_chromium(item)
            has_session = any(c.get("name") == "sessionid" and c.get("value") for c in cookies)
            status = "healthy" if has_session else ("logged out" if cookies else "no TikTok cookies")
            note = "sessionid found" if has_session else (f"{len(cookies)} TikTok cookies, no sessionid" if cookies else "open TikTok and log in")
            rows.append((item.browser, item.profile, len(cookies), status, note))
        except Exception as exc:
            rows.append((item.browser, item.profile, 0, "error", str(exc)))
    return rows


def format_browser_session_health() -> str:
    rows = browser_session_health()
    if not rows:
        return format_browser_profiles()
    lines = ["Browser TikTok Session Health:", ""]
    for browser, profile, count, status, note in rows:
        lines.append(f"- {browser}/{profile}: {status} ({count} TikTok cookies) - {note}")
    return "\n".join(lines)


def cookie_header_for_tiktok(browser: str = "auto", profile: str = "") -> tuple[str, str]:
    cookies, message = read_tiktok_cookies(browser, profile)
    if not cookies:
        return "", message
    pairs = []
    seen = set()
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        pairs.append(f"{name}={value}")
    return "; ".join(pairs), message
