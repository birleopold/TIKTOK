from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from unified_app.config import DEPENDENCY_GROUPS, PIP_HINTS, PYTHON, READY_DIR, ROOT
from unified_app.services.jobs import add_job

@dataclass
class DoctorCheck:
    feature: str
    status: str
    message: str
    action: str = ""


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def check_module_group(name: str, modules: tuple[str, ...]) -> DoctorCheck:
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if missing:
        return DoctorCheck(name, "RED", "Missing Python modules: " + ", ".join(missing), "Install requirements")
    return DoctorCheck(name, "GREEN", "Python modules installed")


def check_folders() -> DoctorCheck:
    required = [READY_DIR, ROOT / "exports", ROOT / "unified_app" / "data"]
    missing = [p for p in required if not p.exists()]
    if missing:
        return DoctorCheck("Folders", "YELLOW", "Missing folders: " + ", ".join(str(p.relative_to(ROOT)) for p in missing), "Create folders")
    return DoctorCheck("Folders", "GREEN", "Required folders exist")


def check_chrome() -> DoctorCheck:
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    if any(p.exists() for p in candidates):
        return DoctorCheck("Chrome", "GREEN", "Google Chrome found")
    return DoctorCheck("Chrome", "YELLOW", "Google Chrome was not found in common locations; Playwright Chromium may still work", "Install Chrome")



def find_playwright_ffmpeg() -> Path | None:
    base = Path.home() / "AppData" / "Local" / "ms-playwright"
    if not base.exists():
        return None
    for candidate in base.glob("ffmpeg-*/*ffmpeg*.exe"):
        if candidate.exists():
            return candidate
    return None

def check_ffmpeg() -> DoctorCheck:
    if command_exists("ffmpeg"):
        return DoctorCheck("FFmpeg", "GREEN", "ffmpeg is available on PATH")
    bundled = find_playwright_ffmpeg()
    if bundled:
        return DoctorCheck("FFmpeg", "GREEN", f"Using Playwright bundled FFmpeg: {bundled}")
    return DoctorCheck("FFmpeg", "RED", "ffmpeg not found", "Install FFmpeg")


def check_imagemagick() -> DoctorCheck:
    if command_exists("magick") or command_exists("convert"):
        return DoctorCheck("ImageMagick", "GREEN", "ImageMagick command found")
    return DoctorCheck("ImageMagick", "YELLOW", "ImageMagick not found; only needed for some text-overlay/video caption flows", "Install ImageMagick")


def check_uploader_cli() -> DoctorCheck:
    cli = ROOT / "TiktokAutoUploader-main" / "cli.py"
    if not cli.exists():
        return DoctorCheck("Uploader CLI", "RED", "cli.py missing", "Restore uploader")
    try:
        proc = subprocess.run([PYTHON, "cli.py", "--help"], cwd=cli.parent, capture_output=True, text=True, timeout=20)
    except Exception as exc:
        return DoctorCheck("Uploader CLI", "RED", f"CLI test failed: {exc}", "Install requirements")
    if proc.returncode == 0:
        return DoctorCheck("Uploader CLI", "GREEN", "Uploader CLI starts")
    return DoctorCheck("Uploader CLI", "RED", (proc.stderr or proc.stdout).strip()[:300], "Install requirements")


def check_playwright_runtime() -> DoctorCheck:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("data:text/html,<title>ok</title>")
            title = page.title()
            browser.close()
        if title == "ok":
            return DoctorCheck("Playwright Browser", "GREEN", "Chromium launches")
    except Exception as exc:
        return DoctorCheck("Playwright Browser", "RED", f"Chromium launch failed: {exc}", "Install Playwright browser")
    return DoctorCheck("Playwright Browser", "RED", "Unexpected browser test result", "Install Playwright browser")


def run_doctor() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    for name, modules in DEPENDENCY_GROUPS.items():
        checks.append(check_module_group(name, modules))
    checks.extend([check_folders(), check_chrome(), check_ffmpeg(), check_imagemagick(), check_uploader_cli(), check_playwright_runtime()])
    return checks


def format_doctor_report(checks: list[DoctorCheck]) -> str:
    lines = []
    for c in checks:
        lines.append(f"[{c.status}] {c.feature}: {c.message}" + (f" | Action: {c.action}" if c.action else ""))
    return "\n".join(lines)


def fix_folders() -> tuple[bool, str]:
    for path in (READY_DIR, ROOT / "exports", ROOT / "unified_app" / "data"):
        path.mkdir(parents=True, exist_ok=True)
    add_job("doctor", "folders", "done", "Created required folders")
    return True, "Created required folders"


def install_all_requirements() -> tuple[bool, str]:
    started = 0
    for hint in PIP_HINTS:
        parts = hint.split("python -m pip install -r ", 1)
        if len(parts) != 2:
            continue
        req = ROOT / parts[1]
        if not req.exists():
            continue
        kwargs = {"cwd": str(ROOT)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen([PYTHON, "-m", "pip", "install", "-r", str(req)], **kwargs)
        started += 1
    add_job("doctor", "requirements", "started", f"Started {started} requirement installers")
    return True, f"Started {started} requirement installers"


def install_playwright_browser() -> tuple[bool, str]:
    kwargs = {"cwd": str(ROOT)}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    subprocess.Popen([PYTHON, "-m", "playwright", "install", "chromium"], **kwargs)
    add_job("doctor", "playwright", "started", "Started Playwright Chromium install")
    return True, "Started Playwright Chromium install"
