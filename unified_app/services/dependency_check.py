from __future__ import annotations

import importlib.util

from unified_app.config import DEPENDENCY_GROUPS


def missing_modules(mods: tuple[str, ...]) -> list[str]:
    return [m for m in mods if importlib.util.find_spec(m) is None]


def dependency_report() -> tuple[bool, list[str]]:
    ok = True
    lines: list[str] = []
    for group, mods in DEPENDENCY_GROUPS.items():
        missing = missing_modules(mods)
        if missing:
            ok = False
            lines.append(f"{group}: missing {', '.join(missing)}")
        else:
            lines.append(f"{group}: OK")
    return ok, lines
