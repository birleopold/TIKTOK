# Unified TikTok Python Creator System

This workspace is now a modular local creator app focused on content creation, uploading, scheduling, repurposing, analytics, and no-key content research.

## Run

Double-click:

```text
RUN_UNIFIED_PYTHON_APP.bat
```

Or run:

```powershell
C:\Python314\python.exe -m unified_app.app
```

The old command still works too:

```powershell
C:\Python314\python.exe unified_tiktok_app.py
```

## Structure

```text
unified_app/
  app.py
  adapters/
    launcher.py
    projects.py
  services/
    content_hunt.py
    db.py
    dependency_check.py
    drafts.py
    jobs.py
    library.py
    source.py
    video_tools.py
  ui/
    main_window.py
  data/
```

## Main Tabs

- `Paste & Go`: paste a TikTok page/video, YouTube link, website, RSS/feed URL, text idea, local video, or local folder. It detects the type and shows recommended actions.
- `Setup Doctor`: checks Python packages, Chrome, FFmpeg, ImageMagick, folders, uploader CLI, and Playwright browser runtime. It also has repair/install buttons.
- `Projects`: launch the remaining useful creator tools.
- `Content Hunt`: saves public metadata and candidate media/page links without API keys.
- `Draft Queue`: turns hunted content and local videos into draft posts with captions and hashtags.
- `Library & Analytics`: shows hunted sources, local videos, and saved rows in `creator_library.db`.
- `Jobs`: shows launch, scan, hunt, install, export, and prepare history.
- `Python Source`: browses the remaining Python code.

## CLI

```powershell
C:\Python314\python.exe -m unified_app.app --list
C:\Python314\python.exe -m unified_app.app --files
C:\Python314\python.exe -m unified_app.app --check
C:\Python314\python.exe -m unified_app.app --hunt https://www.tiktok.com/@example
C:\Python314\python.exe -m unified_app.app --ideas "street food video in Kampala"
C:\Python314\python.exe -m unified_app.app --prepare C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --scan-local
C:\Python314\python.exe -m unified_app.app --export-plan 7
C:\Python314\python.exe -m unified_app.app --add-source https://example.com/feed.xml
C:\Python314\python.exe -m unified_app.app --refresh-sources
C:\Python314\python.exe -m unified_app.app --make-drafts
C:\Python314\python.exe -m unified_app.app --drafts
C:\Python314\python.exe -m unified_app.app --doctor
C:\Python314\python.exe -m unified_app.app --detect https://www.tiktok.com/@example
```

## No-Key Automations

- Public page/profile/video metadata hunting.
- Candidate source library in SQLite.
- Saved source list with refresh-all hunting.
- Local video asset scanning.
- Copy local videos into the uploader-ready folder.
- Caption, hook, keyword, and hashtag generation using local text logic.
- Draft Queue generation from candidates and local assets.
- CSV draft posting-plan export into `exports/`.
- Job history inside the app.

Review rights before reposting third-party content. The content hunter is for research, inspiration, owned content, permitted content, public-domain content, and workflow planning.

## Doctor Status

- `GREEN`: ready.
- `YELLOW`: usable with a caveat or optional improvement.
- `RED`: needs fixing before that feature should be used.

Current expected caveat on this machine: system `ffmpeg` may be yellow if it is not on PATH, even though Playwright FFmpeg is installed.
