from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unified_app.adapters.launcher import open_folder, run_script
from unified_app.config import ROOT
from unified_app.services.dependency_check import missing_modules
from unified_app.services.drafts import export_posting_plan, make_drafts
from unified_app.services.jobs import add_job
from unified_app.services.library import library_counts, scan_local_assets

@dataclass(frozen=True)
class WorkflowPreset:
    id: str
    label: str
    description: str
    button: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    steps: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    project_folder: str | None = None


WORKFLOW_PRESETS = (
    WorkflowPreset(
        "ai_short", "Make AI Short", "Create an AI-assisted short with script, voiceover, captions, media, and render support.", "Launch",
        ("Text idea or topic", "Optional local assets"),
        ("Rendered short", "Captions", "Draft metadata"),
        ("Open ShortGPT", "Choose short automation", "Generate script/assets", "Render output", "Return to Draft Queue"),
        ("gradio", "openai", "edge_tts", "tinydb"), "ShortGPT-stable",
    ),
    WorkflowPreset(
        "compilation", "Make Compilation", "Build a compilation using the clip server, review editor, and video generator.", "Launch Tools",
        ("Clip folder or collected clips", "Intro/outro choices"),
        ("Compilation video", "Credits file", "Draft row"),
        ("Start clip server", "Review clips", "Pick intro/outro", "Render compilation"),
        ("PyQt5", "cv2", "pyftpdlib", "pydub"), "TikTok-Compilation-Video-Generator-master",
    ),
    WorkflowPreset(
        "upload", "Upload Video", "Upload a ready video using saved TikTok browser sessions.", "Open Uploader",
        ("Saved account session", "Upload-ready local video", "Caption/hashtags"),
        ("Uploaded post", "Job history", "Updated draft status later"),
        ("Open uploader", "Choose account", "Choose video", "Paste caption", "Upload"),
        ("selenium", "yt_dlp", "fake_useragent"), "TiktokAutoUploader-main",
    ),
    WorkflowPreset(
        "schedule", "Schedule Posts", "Export a posting plan and open upload tools for scheduling work.", "Prepare",
        ("Draft Queue", "Posting window"),
        ("CSV posting plan", "Uploader opened"),
        ("Make drafts", "Export 7-day plan", "Open uploader", "Schedule manually/through uploader flow"),
        ("sqlmodel",), "TiktokAutoUploader-main",
    ),
    WorkflowPreset(
        "translate", "Translate/Dub Video", "Translate or dub an existing video using ShortGPT's translation tooling.", "Launch",
        ("Local video or YouTube link", "Target language"),
        ("Translated video", "Captions", "Draft metadata"),
        ("Open ShortGPT", "Choose translation tab", "Select source", "Render translated video"),
        ("gradio", "openai", "edge_tts"), "ShortGPT-stable",
    ),
    WorkflowPreset(
        "caption", "Caption Video", "Generate local hooks, captions, hashtags, and draft rows from your library.", "Make Drafts",
        ("Hunted links or local videos",),
        ("Draft captions", "Hashtags", "Hooks"),
        ("Read library", "Generate keyword set", "Create/update drafts"),
    ),
    WorkflowPreset(
        "batch_prepare", "Batch Prepare Folder", "Index local videos and prepare them as drafts for later upload.", "Scan + Draft",
        ("Local video folder",),
        ("Indexed videos", "Draft rows", "Duplicate awareness"),
        ("Scan folders", "Index assets", "Generate drafts", "Export plan if needed"),
    ),
    WorkflowPreset(
        "repurpose_youtube", "Repurpose YouTube Short", "Paste a YouTube link, create TikTok captions, and prepare the upload flow.", "Open Paste & Go",
        ("YouTube/Shorts URL",),
        ("Candidate metadata", "Draft caption", "Upload guidance"),
        ("Paste link into Paste & Go", "Fetch metadata", "Generate caption", "Use uploader YouTube import"),
        ("yt_dlp",), "TiktokAutoUploader-main",
    ),
    WorkflowPreset(
        "source_tools", "Open Source Tools", "Open the project workspace for advanced inspection and manual editing.", "Open",
        ("None",),
        ("Explorer window",),
        ("Open workspace", "Inspect source/tools"),
    ),
)


def get_workflow(workflow_id: str) -> WorkflowPreset | None:
    return next((preset for preset in WORKFLOW_PRESETS if preset.id == workflow_id), None)


def workflow_readiness(preset: WorkflowPreset) -> tuple[str, list[str]]:
    issues: list[str] = []
    if preset.dependencies:
        missing = missing_modules(preset.dependencies)
        if missing:
            issues.append("Missing modules: " + ", ".join(missing))
    if preset.project_folder and not (ROOT / preset.project_folder).exists():
        issues.append("Missing folder: " + preset.project_folder)
    counts = library_counts()
    if preset.id in {"caption", "batch_prepare", "schedule"} and counts.get("drafts", 0) == 0 and counts.get("local_assets", 0) == 0 and counts.get("web", 0) == 0:
        issues.append("Library is empty; use Paste & Go, Content Hunt, or Scan Local Videos first")
    if issues:
        return "YELLOW", issues
    return "GREEN", ["Ready"]


def format_workflow(preset: WorkflowPreset) -> str:
    status, notes = workflow_readiness(preset)
    lines = [
        f"{preset.label} ({preset.id})",
        f"Status: {status}",
        preset.description,
        "",
        "Inputs:",
        *["  - " + item for item in preset.inputs],
        "Outputs:",
        *["  - " + item for item in preset.outputs],
        "Steps:",
        *[f"  {i + 1}. {step}" for i, step in enumerate(preset.steps)],
        "Notes:",
        *["  - " + note for note in notes],
    ]
    return "\n".join(lines)


def list_workflow_summaries() -> list[str]:
    out: list[str] = []
    for preset in WORKFLOW_PRESETS:
        status, _ = workflow_readiness(preset)
        out.append(f"{preset.id}: [{status}] {preset.label} - {preset.description}")
    return out


def run_workflow(workflow_id: str) -> tuple[bool, str]:
    if workflow_id == "ai_short":
        return run_script("ShortGPT-stable", "runShortGPT.py")
    if workflow_id == "compilation":
        ok1, msg1 = run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Server"), "main.py")
        ok2, msg2 = run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Client"), "main.py")
        ok3, msg3 = run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Video Generator"), "main.py")
        return ok1 and ok2 and ok3, " | ".join([msg1, msg2, msg3])
    if workflow_id == "upload":
        return run_script("TiktokAutoUploader-main", "cli.py")
    if workflow_id == "schedule":
        path = export_posting_plan(7)
        ok, msg = run_script("TiktokAutoUploader-main", "cli.py")
        return ok, f"Exported {path.relative_to(ROOT)}; {msg}"
    if workflow_id == "translate":
        return run_script("ShortGPT-stable", "runShortGPT.py")
    if workflow_id == "caption":
        made = make_drafts()
        return True, f"Created or updated {made} caption drafts"
    if workflow_id == "batch_prepare":
        count = scan_local_assets()
        made = make_drafts()
        return True, f"Indexed {count} local videos and created/updated {made} drafts"
    if workflow_id == "repurpose_youtube":
        add_job("workflow", "repurpose_youtube", "ready", "Paste a YouTube link into Paste & Go")
        return True, "Paste a YouTube link into Paste & Go, then use Make Drafts or Upload Video."
    if workflow_id == "source_tools":
        return open_folder(".")
    return False, f"Unknown workflow: {workflow_id}"
