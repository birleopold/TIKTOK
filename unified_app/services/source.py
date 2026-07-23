from __future__ import annotations

from pathlib import Path

from unified_app.config import ROOT


def scan_python_files() -> list[Path]:
    ignored = {"node_modules", ".git", "__pycache__", ".venv", "venv", "env"}
    return sorted([p.relative_to(ROOT) for p in ROOT.rglob("*.py") if not any(x in ignored for x in p.parts)], key=lambda p: str(p).lower())
