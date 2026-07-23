from __future__ import annotations

from pathlib import Path
from tkinter import simpledialog

from unified_app.adapters.launcher import install_requirements, open_folder, run_script
from unified_app.config import Action, Project, ROOT


def uploader_login() -> tuple[bool, str]:
    name = simpledialog.askstring("TikTok Login", "Account name to save locally:")
    if not name:
        return False, "Login cancelled."
    return run_script("TiktokAutoUploader-main", "cli.py", ("login", "-n", name.strip()))


def project_open_action(folder: str) -> Action:
    return Action("Open folder", "Open this project folder.", lambda folder=folder: open_folder(folder))


def open_hunt_downloads() -> tuple[bool, str]:
    folder = Path("downloads") / "hunt"
    (ROOT / folder).mkdir(parents=True, exist_ok=True)
    return open_folder(str(folder))


PROJECTS = (
    Project(
        "Hunt Downloads",
        ".",
        "Content Sourcing",
        "active",
        (
            "Multi-select saved Hunt candidates, preview public sources, download "
            "authorized videos, preserve source metadata, and index files locally."
        ),
        (
            "multi-select results",
            "preview source",
            "video check",
            "public video download",
            "source metadata",
            "Library indexing",
        ),
        (
            Action(
                "Launch Hunt Downloads",
                "Choose saved Hunt results and download only authorized videos.",
                lambda: run_script(".", "hunt_downloader.py"),
                ".",
                "hunt_downloader.py",
            ),
            Action(
                "Open Hunt downloads",
                "Open the local Hunt download folder.",
                open_hunt_downloads,
            ),
        ),
    ),
    Project(
        "TikTok Auto Uploader",
        "TiktokAutoUploader-main",
        "Publishing",
        "active",
        "Python CLI for saved accounts, browser login, uploads, schedules, and local video storage.",
        ("login", "upload local video", "upload YouTube video", "schedule", "list accounts", "list videos"),
        (
            Action("Install requirements", "Installs uploader requirements.", lambda: install_requirements("TiktokAutoUploader-main/requirements.txt")),
            Action("Open interactive uploader", "Runs cli.py interactive shell.", lambda: run_script("TiktokAutoUploader-main", "cli.py"), "TiktokAutoUploader-main", "cli.py"),
            Action("Login", "Save a TikTok browser session.", uploader_login, "TiktokAutoUploader-main", "cli.py"),
            Action("Start scheduler", "Runs scheduler/main.py.", lambda: run_script("TiktokAutoUploader-main", str(Path("scheduler") / "main.py")), "TiktokAutoUploader-main", str(Path("scheduler") / "main.py")),
            project_open_action("TiktokAutoUploader-main"),
        ),
    ),
    Project(
        "ShortGPT",
        "ShortGPT-stable",
        "AI Creation",
        "launchable",
        "AI short/video framework for scripts, voiceover, captions, assets, editing, translation, and rendering.",
        ("AI scripts", "voiceover", "captions", "asset sourcing", "video rendering", "translation"),
        (
            Action("Install requirements", "Installs ShortGPT requirements.", lambda: install_requirements("ShortGPT-stable/requirements.txt")),
            Action("Launch ShortGPT", "Runs runShortGPT.py.", lambda: run_script("ShortGPT-stable", "runShortGPT.py"), "ShortGPT-stable", "runShortGPT.py"),
            project_open_action("ShortGPT-stable"),
        ),
    ),
    Project(
        "TikTok Compilation Video Generator",
        "TikTok-Compilation-Video-Generator-master",
        "Editing",
        "launchable",
        "Python server/client/generator workflow for clip collection, review, and compilation rendering.",
        ("clip server", "clip review", "intro/outro", "intervals", "render compilation", "credits export"),
        (
            Action("Install requirements", "Installs compilation requirements.", lambda: install_requirements("TikTok-Compilation-Video-Generator-master/requirements.txt")),
            Action("Launch clip server", "Runs TikTok Server/main.py.", lambda: run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Server"), "main.py"), str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Server"), "main.py"),
            Action("Launch clip editor", "Runs TikTok Client/main.py.", lambda: run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Client"), "main.py"), str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Client"), "main.py"),
            Action("Launch video generator", "Runs TikTok Video Generator/main.py.", lambda: run_script(str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Video Generator"), "main.py"), str(Path("TikTok-Compilation-Video-Generator-master") / "TikTok Video Generator"), "main.py"),
            project_open_action("TikTok-Compilation-Video-Generator-master"),
        ),
    ),
    Project(
        "tiktok-uploader Library",
        "tiktok-uploader-main",
        "Publishing Library",
        "source available",
        "Pure Python package for browser-based TikTok uploads, auth, examples, and tests.",
        ("auth", "upload", "examples", "tests", "Playwright backend"),
        (project_open_action("tiktok-uploader-main"),),
    ),
    Project(
        "tiktokpy",
        "tiktokpy-master",
        "Library",
        "source available",
        "Python TikTok client code, quickstart scripts, models, and tests.",
        ("client", "quick login", "quickstart", "models", "tests"),
        (
            Action("Run quickstart", "Runs quickstart.py.", lambda: run_script("tiktokpy-master", "quickstart.py"), "tiktokpy-master", "quickstart.py"),
            Action("Run quicklogin", "Runs quicklogin.py.", lambda: run_script("tiktokpy-master", "quicklogin.py"), "tiktokpy-master", "quicklogin.py"),
            project_open_action("tiktokpy-master"),
        ),
    ),
    Project(
        "sklhdaudbus",
        "sklhdaudbus-master",
        ".NET Reference",
        "source available",
        "Visual Studio solution indexed for completeness.",
        ("solution file", "desktop source"),
        (project_open_action("sklhdaudbus-master"),),
    ),
)
