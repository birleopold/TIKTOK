from __future__ import annotations

import argparse

from unified_app.adapters.projects import PROJECTS
from unified_app.config import PIP_HINTS
from unified_app.services.content_hunt import hunt_urls, refresh_sources, save_source
from unified_app.services.db import init_db
from unified_app.services.dependency_check import dependency_report
from unified_app.services.drafts import content_pack, export_posting_plan, make_drafts, recent_drafts
from unified_app.services.library import scan_local_assets
from unified_app.services.input_detector import detect_input, format_detection
from unified_app.services.setup_doctor import format_doctor_report, run_doctor
from unified_app.services.source import scan_python_files
from unified_app.services.video_tools import prepare_video_for_upload
from unified_app.ui.main_window import UnifiedApp


def validate_projects() -> int:
    init_db()
    issues: list[str] = []
    for project in PROJECTS:
        if not project.path.exists():
            issues.append(f"missing project folder: {project.folder}")
        for action in project.actions:
            if action.folder and not (project.path.parents[0] / action.folder).exists():
                issues.append(f"{project.name} action '{action.label}' missing folder: {action.folder}")
            if action.folder and action.script and not (project.path.parents[0] / action.folder / action.script).exists():
                issues.append(f"{project.name} action '{action.label}' missing script")
    py_files = scan_python_files()
    deps_ok, dep_lines = dependency_report()
    print(f"Projects checked: {len(PROJECTS)}")
    print(f"Python files indexed: {len(py_files)}")
    print("Dependency check:")
    for line in dep_lines:
        print("  - " + line)
    if not deps_ok:
        print("Install hints:")
        for hint in PIP_HINTS:
            print("  - " + hint)
    if issues:
        print("Issues:")
        for issue in issues:
            print("  - " + issue)
        return 1
    if not deps_ok:
        print("Project folders and entry points are present, but some project dependencies are missing.")
        return 2
    print("All project folders, launchable Python entry points, and checked dependencies are present.")
    return 0


def print_projects() -> None:
    for project in PROJECTS:
        print(f"[{project.category}] {project.name} - {project.status}")
        print(f"  {project.folder}")
        print(f"  {project.summary}")
        print(f"  features: {', '.join(project.features)}")


def print_files() -> None:
    for path in scan_python_files():
        print(path)


def print_ideas(text: str) -> None:
    pack = content_pack(text, "")
    print("Keywords: " + ", ".join(pack["keywords"]))
    print("Hashtags: " + " ".join(pack["hashtags"]))
    print("Hooks:")
    for hook in pack["hooks"]:
        print("  - " + hook)
    print("Captions:")
    for caption in pack["captions"]:
        print("  - " + caption)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified pure-Python TikTok creator system")
    parser.add_argument("--list", action="store_true", help="List indexed projects and exit")
    parser.add_argument("--files", action="store_true", help="List indexed Python files and exit")
    parser.add_argument("--check", action="store_true", help="Validate project folders, entry points, and dependencies")
    parser.add_argument("--hunt", nargs="*", help="Fetch public metadata for one or more links and save to the content library")
    parser.add_argument("--ideas", help="Generate no-key captions, hooks, and hashtags from text")
    parser.add_argument("--prepare", help="Copy a local video into the uploader-ready folder")
    parser.add_argument("--scan-local", action="store_true", help="Index local video assets")
    parser.add_argument("--export-plan", type=int, metavar="DAYS", help="Export a CSV draft posting plan")
    parser.add_argument("--add-source", nargs="*", help="Save one or more content source URLs")
    parser.add_argument("--refresh-sources", action="store_true", help="Refresh all saved content sources")
    parser.add_argument("--make-drafts", action="store_true", help="Create draft posts from hunted links and local videos")
    parser.add_argument("--drafts", action="store_true", help="List recent draft posts")
    parser.add_argument("--doctor", action="store_true", help="Run Setup Doctor checks")
    parser.add_argument("--detect", help="Detect pasted input type and recommended actions")
    args = parser.parse_args()

    if args.doctor:
        print(format_doctor_report(run_doctor())); return
    if args.detect:
        print(format_detection(detect_input(args.detect))); return
    if args.list:
        print_projects(); return
    if args.files:
        print_files(); return
    if args.check:
        raise SystemExit(validate_projects())
    if args.hunt is not None:
        cands, errs = hunt_urls(args.hunt)
        for candidate in cands:
            print(f"SAVED [{candidate.source_type}] {candidate.title} -> {candidate.url} ({len(candidate.media_urls)} media links)")
        for err in errs:
            print("ERROR " + err)
        raise SystemExit(0 if not errs else 1)
    if args.ideas:
        print_ideas(args.ideas); return
    if args.prepare:
        ok, msg = prepare_video_for_upload(args.prepare)
        print(msg)
        raise SystemExit(0 if ok else 1)
    if args.scan_local:
        print(f"Indexed {scan_local_assets()} local video assets"); return
    if args.export_plan:
        print(export_posting_plan(args.export_plan)); return
    if args.add_source is not None:
        for url in args.add_source:
            ok, msg = save_source(url)
            print(msg)
        return
    if args.refresh_sources:
        ok, failed = refresh_sources()
        print(f"Refreshed {ok} sources; {failed} failed"); return
    if args.make_drafts:
        print(f"Created or updated {make_drafts()} drafts"); return
    if args.drafts:
        for row in recent_drafts():
            print(row)
        return
    UnifiedApp().mainloop()


if __name__ == "__main__":
    main()
