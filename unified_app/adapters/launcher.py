from __future__ import annotations

import os
import subprocess
from pathlib import Path

from unified_app.config import PYTHON, ROOT
from unified_app.services.jobs import add_job


def run_script(folder: str, script: str, extra_args: tuple[str, ...] = ()) -> tuple[bool, str]:
    cwd = ROOT / folder
    target = cwd / script
    if not target.exists():
        return False, f"Missing script: {target}"
    try:
        kwargs = {"cwd": str(cwd)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        proc = subprocess.Popen([PYTHON, script, *extra_args], **kwargs)
    except Exception as exc:
        add_job("launch", str(target), "failed", str(exc))
        return False, f"Could not launch {target.name}: {exc}"
    add_job("launch", str(target), "started", f"pid {proc.pid}")
    return True, f"Launched {target.name} with pid {proc.pid}"


def open_folder(folder: str) -> tuple[bool, str]:
    path = ROOT / folder
    if not path.exists():
        return False, f"Missing folder: {path}"
    try:
        subprocess.Popen(["explorer", str(path)] if os.name == "nt" else ["xdg-open", str(path)])
    except Exception as exc:
        return False, f"Could not open folder: {exc}"
    return True, f"Opened {path}"


def install_requirements(req_file: str) -> tuple[bool, str]:
    req = ROOT / req_file
    if not req.exists():
        return False, f"Missing requirements file: {req}"
    try:
        kwargs = {"cwd": str(ROOT)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        proc = subprocess.Popen([PYTHON, "-m", "pip", "install", "-r", str(req)], **kwargs)
    except Exception as exc:
        add_job("install", req_file, "failed", str(exc))
        return False, f"Could not start pip install: {exc}"
    add_job("install", req_file, "started", f"pid {proc.pid}")
    return True, f"Started dependency install with pid {proc.pid}: {req}"
