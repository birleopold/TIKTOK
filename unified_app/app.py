from __future__ import annotations

import argparse

from unified_app.adapters.projects import PROJECTS
from unified_app.config import PIP_HINTS
from unified_app.services.content_hunt import hunt_urls, refresh_sources, save_source
from unified_app.services.content_sourcing import draft_top_candidates, expand_source, export_source_digest, format_source_digest, refresh_saved_sources_deep, score_all_candidates
from unified_app.services.daily_command import export_daily_plan, format_daily_plan
from unified_app.services.db import init_db
from unified_app.services.dependency_check import dependency_report
from unified_app.services.drafts import content_pack, export_posting_plan, make_drafts, recent_drafts
from unified_app.services.library import scan_local_assets
from unified_app.services.input_detector import detect_input, format_detection
from unified_app.services.paste_go import analyze_value, run_primary_action
from unified_app.services.production_library import draft_from_item, export_library_csv, library_summary_lines, mark_uploaded, production_rows, rebuild_library, schedule_next_drafts, update_item_status
from unified_app.services.ready_package import make_ready_package
from unified_app.services.settings import format_settings, set_setting
from unified_app.services.setup_doctor import format_doctor_report, run_doctor
from unified_app.services.source import scan_python_files
from unified_app.services.tiktok_profile import analyze_tiktok_profile_url, format_profile_report, recent_profile_snapshots
from unified_app.services.upload_queue import account_rows, add_to_queue, assign_queue_account, auto_assign_healthy_account, cancel_queue_item, import_browser_session, import_cookie_file, queue_ready_items, queue_rows, queue_summary_lines, run_login, run_queue_item, sync_accounts, upload_preflight
from unified_app.services.video_tools import prepare_video_for_upload
from unified_app.services.analytics import export_analytics_report, format_analytics_report
from unified_app.services.automations import clean_rename_folder, duplicate_report, export_calendar, export_today_list, extract_audio, make_thumbnail, make_tiktok_ready, what_to_post_today
from unified_app.services.batch_campaign import build_batch_campaign
from unified_app.services.browser_cookies import format_browser_profiles, format_browser_session_health
from unified_app.services.creator_os import add_caption_style, add_hashtag_set, apply_caption_style, apply_hashtag_set, backup_app, backup_rows, caption_style_rows, create_draft_from_template, create_series, export_calendar_board, format_calendar_board, generate_thumbnail_choices, hashtag_set_rows, performance_report, record_upload_result, repurpose_long_video, restore_backup, select_thumbnail, series_rows, template_rows, thumbnail_rows, update_draft_field, upload_assistant, upload_result_rows
from unified_app.services.branding import add_watermark, brand_video, burn_caption, create_srt
from unified_app.services.workflows import WORKFLOW_PRESETS, format_workflow, get_workflow, list_workflow_summaries, run_workflow
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
    parser.add_argument("--deep-refresh-sources", action="store_true", help="Expand saved sources into candidate links and score them")
    parser.add_argument("--expand-source", metavar="URL", help="Expand one source/feed/page into candidate links")
    parser.add_argument("--source-digest", action="store_true", help="Show scored no-key content sourcing digest")
    parser.add_argument("--source-digest-export", action="store_true", help="Export scored content sourcing digest CSV")
    parser.add_argument("--draft-top", type=int, metavar="COUNT", help="Create drafts from top scored candidates")
    parser.add_argument("--make-drafts", action="store_true", help="Create draft posts from hunted links and local videos")
    parser.add_argument("--drafts", action="store_true", help="List recent draft posts")
    parser.add_argument("--doctor", action="store_true", help="Run Setup Doctor checks")
    parser.add_argument("--detect", help="Detect pasted input type and recommended actions")
    parser.add_argument("--workflows", action="store_true", help="List creator workflow presets")
    parser.add_argument("--workflow", help="Run a workflow preset by id")
    parser.add_argument("--workflow-info", help="Show workflow preset details by id")
    parser.add_argument("--paste-go", help="Run full Paste & Go analysis for one input")
    parser.add_argument("--paste-action", help="Run the recommended Paste & Go action for one input")
    parser.add_argument("--duplicates", nargs="?", const=".", help="Export duplicate video report for a folder")
    parser.add_argument("--clean-rename", nargs="?", const=".", help="Clean-rename videos in a folder")
    parser.add_argument("--today", type=int, nargs="?", const=5, help="Show what to post today")
    parser.add_argument("--export-today", type=int, nargs="?", const=5, help="Export what-to-post-today CSV")
    parser.add_argument("--calendar", type=int, nargs="?", const=14, help="Export local posting calendar CSV")
    parser.add_argument("--thumbnail", help="Create thumbnail image from video")
    parser.add_argument("--extract-audio", help="Extract MP3 audio from video")
    parser.add_argument("--tiktok-ready", help="Convert video to TikTok-ready 1080x1920 MP4")
    parser.add_argument("--ready-package", help="Create full TikTok-ready package: video, thumbnail, audio, draft, and library status")
    parser.add_argument("--burn-caption", nargs=2, metavar=("VIDEO", "TEXT"), help="Burn caption/title text into a video")
    parser.add_argument("--watermark", nargs=2, metavar=("VIDEO", "TEXT"), help="Add text watermark to a video")
    parser.add_argument("--brand-video", nargs=3, metavar=("VIDEO", "CAPTION", "WATERMARK"), help="Add caption and watermark to a video")
    parser.add_argument("--srt", nargs=2, metavar=("VIDEO", "TEXT"), help="Create simple SRT captions from text")
    parser.add_argument("--batch-campaign", metavar="FOLDER", help="Build ready packages for videos in a folder")
    parser.add_argument("--batch-limit", type=int, default=5, help="Maximum videos for --batch-campaign")
    parser.add_argument("--batch-queue", action="store_true", help="Queue batch campaign outputs for upload")
    parser.add_argument("--batch-account", default="", help="Account name to assign when queueing batch outputs")
    parser.add_argument("--tiktok-profile", help="Analyze a public TikTok profile/page and save a local snapshot")
    parser.add_argument("--profile-snapshots", action="store_true", help="List recent TikTok profile snapshots")
    parser.add_argument("--library", action="store_true", help="List the unified production content library")
    parser.add_argument("--library-summary", action="store_true", help="Show production library status counts")
    parser.add_argument("--library-export", action="store_true", help="Export the production library to CSV")
    parser.add_argument("--library-rebuild", action="store_true", help="Scan local assets and rebuild drafts")
    parser.add_argument("--schedule-drafts", type=int, metavar="COUNT", help="Schedule the next draft posts locally")
    parser.add_argument("--set-status", nargs=2, metavar=("KEY", "STATUS"), help="Set status for a library item, like draft:1 ready")
    parser.add_argument("--mark-uploaded", metavar="KEY", help="Mark a library item uploaded, like draft:1")
    parser.add_argument("--draft-from", metavar="KEY", help="Create a draft from an asset or candidate key")
    parser.add_argument("--accounts", action="store_true", help="List local TikTok account/session health")
    parser.add_argument("--login-account", metavar="NAME", help="Open uploader login flow for one account name")
    parser.add_argument("--import-cookies", nargs=2, metavar=("ACCOUNT", "FILE"), help="Import exported TikTok browser cookies for an account")
    parser.add_argument("--browser-sessions", action="store_true", help="List installed browser profiles that can be scanned for TikTok cookies")
    parser.add_argument("--browser-session-health", action="store_true", help="Check TikTok login health in installed browser profiles without showing cookie values")
    parser.add_argument("--import-browser-session", nargs="+", metavar="ARGS", help="Import TikTok cookies directly from Chrome, Edge, Brave, or Firefox. Example: --import-browser-session mypage auto")
    parser.add_argument("--queue-ready", nargs="?", const="", metavar="ACCOUNT", help="Queue ready library videos for upload, optionally assigning an account")
    parser.add_argument("--queue-add", metavar="VIDEO", help="Add a local video to the upload queue")
    parser.add_argument("--queue", action="store_true", help="List upload queue rows")
    parser.add_argument("--queue-summary", action="store_true", help="Show upload queue status counts")
    parser.add_argument("--queue-dry-run", type=int, metavar="ID", help="Prepare uploader command for a queue item without uploading")
    parser.add_argument("--queue-preflight", type=int, metavar="ID", help="Check whether a queue item is ready to upload")
    parser.add_argument("--queue-auto-account", nargs="?", const="", metavar="ACCOUNT", help="Assign a healthy account to queued items missing one")
    parser.add_argument("--queue-account", nargs=2, metavar=("ID", "ACCOUNT"), help="Assign an account to a queued upload item")
    parser.add_argument("--queue-run", type=int, metavar="ID", help="Run uploader for a queue item")
    parser.add_argument("--queue-cancel", type=int, metavar="ID", help="Cancel a queued or failed upload item")
    parser.add_argument("--analytics", action="store_true", help="Show local creator pipeline analytics")
    parser.add_argument("--analytics-export", action="store_true", help="Export local creator pipeline analytics report")
    parser.add_argument("--daily", action="store_true", help="Show today's creator command plan")
    parser.add_argument("--daily-export", action="store_true", help="Export today's creator command plan CSV")

    parser.add_argument("--calendar-board", type=int, nargs="?", const=7, help="Show visual-style content calendar board")
    parser.add_argument("--calendar-board-export", type=int, nargs="?", const=7, help="Export content calendar board CSV")
    parser.add_argument("--upload-assistant", type=int, metavar="ID", help="Guide one queued upload step by step")
    parser.add_argument("--confirm-upload", nargs=2, metavar=("ID", "URL"), help="Record a completed TikTok upload result")
    parser.add_argument("--upload-results", action="store_true", help="List tracked upload results")
    parser.add_argument("--caption-styles", action="store_true", help="List reusable caption styles")
    parser.add_argument("--add-caption-style", nargs=2, metavar=("NAME", "TEMPLATE"), help="Create or update a reusable caption style")
    parser.add_argument("--apply-caption-style", nargs=2, metavar=("DRAFT_ID", "STYLE"), help="Apply a caption style to a draft")
    parser.add_argument("--hashtag-sets", action="store_true", help="List reusable hashtag packs")
    parser.add_argument("--add-hashtag-set", nargs=2, metavar=("NAME", "HASHTAGS"), help="Create or update a reusable hashtag pack")
    parser.add_argument("--apply-hashtag-set", nargs=2, metavar=("DRAFT_ID", "SET"), help="Apply a hashtag pack to a draft")
    parser.add_argument("--templates", action="store_true", help="List content templates")
    parser.add_argument("--template-draft", nargs=2, metavar=("TEMPLATE", "TOPIC"), help="Create a draft from a content template")
    parser.add_argument("--draft-update", nargs=3, metavar=("DRAFT_ID", "FIELD", "VALUE"), help="Edit a draft field")
    parser.add_argument("--performance", action="store_true", help="Show upload and production performance analytics")
    parser.add_argument("--thumbnail-choices", metavar="VIDEO", help="Generate five thumbnail/frame choices for a video")
    parser.add_argument("--select-thumbnail", type=int, metavar="ID", help="Select one generated thumbnail choice")
    parser.add_argument("--thumbnails", action="store_true", help="List recent thumbnail choices")
    parser.add_argument("--repurpose-long", metavar="VIDEO", help="Cut a long video into TikTok-ready clips")
    parser.add_argument("--segment-seconds", type=int, default=45, help="Seconds per clip for --repurpose-long")
    parser.add_argument("--parts", type=int, default=3, help="Number of clips or series posts")
    parser.add_argument("--series-create", nargs=2, metavar=("NAME", "TOPIC"), help="Create a multi-part content series")
    parser.add_argument("--series", action="store_true", help="List content series")
    parser.add_argument("--backup", action="store_true", help="Backup database, exports, queue, and ready videos")
    parser.add_argument("--backups", action="store_true", help="List local backups")
    parser.add_argument("--restore-backup", metavar="ZIP", help="Restore app database from a backup zip")
    parser.add_argument("--settings", action="store_true", help="Show brand profile defaults")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a brand/default setting")
    args = parser.parse_args()

    if args.doctor:
        print(format_doctor_report(run_doctor())); return
    if args.detect:
        print(format_detection(detect_input(args.detect))); return
    if args.paste_go:
        print(analyze_value(args.paste_go).report); return
    if args.paste_action:
        result=detect_input(args.paste_action); ok,msg=run_primary_action(result); print(msg); raise SystemExit(0 if ok else 1)
    if args.workflows:
        for line in list_workflow_summaries():
            print(line)
        return
    if args.workflow_info:
        preset=get_workflow(args.workflow_info)
        if not preset:
            print(f"Unknown workflow: {args.workflow_info}"); raise SystemExit(1)
        print(format_workflow(preset)); return
    if args.workflow:
        ok,msg=run_workflow(args.workflow); print(msg); raise SystemExit(0 if ok else 1)
    if args.duplicates is not None:
        path, groups, files = duplicate_report(args.duplicates); print(f"{path} ({groups} groups, {files} files)"); return
    if args.clean_rename is not None:
        renamed, notes = clean_rename_folder(args.clean_rename); print(f"Renamed {renamed} videos"); print("\n".join(notes)); return
    if args.today is not None:
        for row in what_to_post_today(args.today): print(row)
        return
    if args.export_today is not None:
        print(export_today_list(args.export_today)); return
    if args.calendar is not None:
        print(export_calendar(args.calendar)); return
    if args.thumbnail:
        ok,msg=make_thumbnail(args.thumbnail); print(msg); raise SystemExit(0 if ok else 1)
    if args.extract_audio:
        ok,msg=extract_audio(args.extract_audio); print(msg); raise SystemExit(0 if ok else 1)
    if args.tiktok_ready:
        ok,msg=make_tiktok_ready(args.tiktok_ready); print(msg); raise SystemExit(0 if ok else 1)
    if args.ready_package:
        ok,_package,msg=make_ready_package(args.ready_package); print(msg); raise SystemExit(0 if ok else 1)
    if args.burn_caption:
        ok,msg=burn_caption(args.burn_caption[0], args.burn_caption[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.watermark:
        ok,msg=add_watermark(args.watermark[0], args.watermark[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.brand_video:
        ok,msg=brand_video(args.brand_video[0], args.brand_video[1], args.brand_video[2]); print(msg); raise SystemExit(0 if ok else 1)
    if args.srt:
        ok,msg=create_srt(args.srt[0], args.srt[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.batch_campaign:
        ok,_result,msg=build_batch_campaign(args.batch_campaign, limit=args.batch_limit, queue=args.batch_queue, account=args.batch_account); print(msg); raise SystemExit(0 if ok else 1)
    if args.tiktok_profile:
        print(format_profile_report(analyze_tiktok_profile_url(args.tiktok_profile))); return
    if args.profile_snapshots:
        for row in recent_profile_snapshots():
            print(row)
        return
    if args.library:
        for row in production_rows():
            print((row.key, row.item_type, row.title, row.status, row.scheduled_for, row.account, row.source))
        return
    if args.library_summary:
        for line in library_summary_lines():
            print(line)
        return
    if args.library_export:
        print(export_library_csv()); return
    if args.library_rebuild:
        assets,drafts=rebuild_library(); print(f"Rebuilt library: {assets} assets, {drafts} drafts"); return
    if args.schedule_drafts:
        count,msg=schedule_next_drafts(args.schedule_drafts); print(msg); raise SystemExit(0 if count else 1)
    if args.set_status:
        ok,msg=update_item_status(args.set_status[0], args.set_status[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.mark_uploaded:
        ok,msg=mark_uploaded(args.mark_uploaded); print(msg); raise SystemExit(0 if ok else 1)
    if args.draft_from:
        ok,msg=draft_from_item(args.draft_from); print(msg); raise SystemExit(0 if ok else 1)
    if args.accounts:
        sync_accounts()
        for row in account_rows():
            print(row)
        return
    if args.login_account:
        ok,msg=run_login(args.login_account); print(msg); raise SystemExit(0 if ok else 1)
    if args.import_cookies:
        ok,msg=import_cookie_file(args.import_cookies[0], args.import_cookies[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.browser_sessions:
        print(format_browser_profiles()); return
    if args.browser_session_health:
        print(format_browser_session_health()); return
    if args.import_browser_session:
        vals=args.import_browser_session
        account=vals[0]
        browser=vals[1] if len(vals) > 1 else "auto"
        profile=" ".join(vals[2:]) if len(vals) > 2 else ""
        ok,msg=import_browser_session(account,browser,profile); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue_ready is not None:
        print(f"Queued {queue_ready_items(args.queue_ready)} ready items"); return
    if args.queue_add:
        ok,msg=add_to_queue(args.queue_add); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue:
        for row in queue_rows():
            print((row.id,row.status,row.account,row.source_ref,row.title,row.scheduled_for,row.library_key))
        return
    if args.queue_summary:
        for line in queue_summary_lines(): print(line)
        return
    if args.queue_dry_run:
        ok,msg=run_queue_item(args.queue_dry_run, dry_run=True); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue_preflight:
        ok,msg=upload_preflight(args.queue_preflight); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue_auto_account is not None:
        count,msg=auto_assign_healthy_account(args.queue_auto_account); print(msg); raise SystemExit(0 if count else 1)
    if args.queue_account:
        ok,msg=assign_queue_account(int(args.queue_account[0]), args.queue_account[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue_run:
        ok,msg=run_queue_item(args.queue_run, dry_run=False); print(msg); raise SystemExit(0 if ok else 1)
    if args.queue_cancel:
        ok,msg=cancel_queue_item(args.queue_cancel); print(msg); raise SystemExit(0 if ok else 1)

    if args.calendar_board is not None:
        print(format_calendar_board(args.calendar_board)); return
    if args.calendar_board_export is not None:
        print(export_calendar_board(args.calendar_board_export)); return
    if args.upload_assistant:
        print(upload_assistant(args.upload_assistant)); return
    if args.confirm_upload:
        ok,msg=record_upload_result(int(args.confirm_upload[0]), args.confirm_upload[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.upload_results:
        for row in upload_result_rows(): print(row)
        return
    if args.caption_styles:
        for row in caption_style_rows(): print(row)
        return
    if args.add_caption_style:
        ok,msg=add_caption_style(args.add_caption_style[0], args.add_caption_style[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.apply_caption_style:
        ok,msg=apply_caption_style(int(args.apply_caption_style[0]), args.apply_caption_style[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.hashtag_sets:
        for row in hashtag_set_rows(): print(row)
        return
    if args.add_hashtag_set:
        ok,msg=add_hashtag_set(args.add_hashtag_set[0], args.add_hashtag_set[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.apply_hashtag_set:
        ok,msg=apply_hashtag_set(int(args.apply_hashtag_set[0]), args.apply_hashtag_set[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.templates:
        for row in template_rows(): print(row)
        return
    if args.template_draft:
        ok,msg=create_draft_from_template(args.template_draft[0], args.template_draft[1]); print(msg); raise SystemExit(0 if ok else 1)
    if args.draft_update:
        ok,msg=update_draft_field(int(args.draft_update[0]), args.draft_update[1], args.draft_update[2]); print(msg); raise SystemExit(0 if ok else 1)
    if args.performance:
        print(performance_report()); return
    if args.thumbnail_choices:
        ok,msg=generate_thumbnail_choices(args.thumbnail_choices); print(msg); raise SystemExit(0 if ok else 1)
    if args.select_thumbnail:
        ok,msg=select_thumbnail(args.select_thumbnail); print(msg); raise SystemExit(0 if ok else 1)
    if args.thumbnails:
        for row in thumbnail_rows(): print(row)
        return
    if args.repurpose_long:
        ok,msg=repurpose_long_video(args.repurpose_long, args.segment_seconds, args.parts); print(msg); raise SystemExit(0 if ok else 1)
    if args.series_create:
        ok,msg=create_series(args.series_create[0], args.series_create[1], args.parts); print(msg); raise SystemExit(0 if ok else 1)
    if args.series:
        for row in series_rows(): print(row)
        return
    if args.backup:
        ok,msg=backup_app(); print(msg); raise SystemExit(0 if ok else 1)
    if args.backups:
        for row in backup_rows(): print(row)
        return
    if args.restore_backup:
        ok,msg=restore_backup(args.restore_backup); print(msg); raise SystemExit(0 if ok else 1)
    if args.analytics:
        print(format_analytics_report()); return
    if args.analytics_export:
        print(export_analytics_report()); return
    if args.daily:
        print(format_daily_plan()); return
    if args.daily_export:
        print(export_daily_plan()); return
    if args.settings:
        print(format_settings()); return
    if args.set:
        set_setting(args.set[0], args.set[1]); print(format_settings()); return
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
    if args.deep_refresh_sources:
        ok, failed = refresh_saved_sources_deep()
        print(f"Expanded {ok} candidates; {failed} errors"); return
    if args.expand_source:
        ok, errs = expand_source(args.expand_source)
        print(f"Expanded {ok} candidates")
        for err in errs: print("ERROR " + err)
        return
    if args.source_digest:
        print(format_source_digest()); return
    if args.source_digest_export:
        print(export_source_digest()); return
    if args.draft_top:
        print(f"Created {draft_top_candidates(args.draft_top)} drafts from top candidates"); return
    if args.make_drafts:
        print(f"Created or updated {make_drafts()} drafts"); return
    if args.drafts:
        for row in recent_drafts():
            print(row)
        return
    UnifiedApp().mainloop()


if __name__ == "__main__":
    main()
