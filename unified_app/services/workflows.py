from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unified_app.adapters.launcher import open_folder, run_script
from unified_app.config import ROOT
from unified_app.services.drafts import export_posting_plan, make_drafts
from unified_app.services.jobs import add_job
from unified_app.services.library import scan_local_assets

@dataclass(frozen=True)
class WorkflowPreset:
    id: str
    label: str
    description: str
    button: str


WORKFLOW_PRESETS = (
    WorkflowPreset("ai_short", "Make AI Short", "Open ShortGPT for AI script, voiceover, caption, and short-video creation.", "Launch"),
    WorkflowPreset("compilation", "Make Compilation", "Launch the compilation server, editor, and video generator workflow.", "Launch Tools"),
    WorkflowPreset("upload", "Upload Video", "Open the uploader CLI where saved TikTok sessions and uploads are managed.", "Open Uploader"),
    WorkflowPreset("schedule", "Schedule Posts", "Open the uploader and export a draft posting plan for scheduling.", "Prepare"),
    WorkflowPreset("translate", "Translate/Dub Video", "Open ShortGPT translation/dubbing tooling.", "Launch"),
    WorkflowPreset("caption", "Caption Video", "Create/update local draft captions and hashtags from the library.", "Make Drafts"),
    WorkflowPreset("batch_prepare", "Batch Prepare Folder", "Scan local videos, index assets, and create draft rows.", "Scan + Draft"),
    WorkflowPreset("repurpose_youtube", "Repurpose YouTube Short", "Use Paste & Go with a YouTube link, then create drafts for TikTok upload.", "Open Paste & Go"),
    WorkflowPreset("source_tools", "Open Source Tools", "Open the advanced project/source folders.", "Open"),
)


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
