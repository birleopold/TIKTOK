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
    content_sourcing.py
    daily_command.py
    db.py
    dependency_check.py
    drafts.py
    jobs.py
    library.py
    production_library.py
    ready_package.py
    source.py
    tiktok_profile.py
    upload_queue.py
    video_tools.py
  ui/
    main_window.py
  data/
```

## Main Tabs

- `Paste & Go`: paste a TikTok page/video, YouTube link, website, RSS/feed URL, text idea, local video, or local folder. It detects the type and shows recommended actions.
- `TikTok Analyzer`: paste a TikTok profile/page and save a local profile snapshot, public video clues, hashtags, caption patterns, next-post ideas, and content gaps.
- `Workflow Presets`: human workflows like Make AI Short, Make Compilation, Upload Video, Schedule Posts, Caption Video, Batch Prepare Folder, and Repurpose YouTube Short.
- `No-Key Automations`: duplicate reports, clean renaming, what-to-post-today, calendar export, thumbnail creation, audio extraction, and TikTok-ready conversion.
- `Accounts & Upload Queue`: checks saved TikTok sessions, starts login/re-login, queues ready videos, prepares uploader commands, and runs existing uploader automation.
- `Setup Doctor`: checks Python packages, Chrome, FFmpeg, ImageMagick, folders, uploader CLI, and Playwright browser runtime. It also has repair/install buttons.
- `Projects`: launch the remaining useful creator tools.
- `Content Hunt`: saves public metadata and candidate media/page links without API keys.
- `Draft Queue`: turns hunted content and local videos into draft posts with captions and hashtags.
- `Library & Analytics`: unified production library for drafts, local videos, hunted candidates, statuses, schedule fields, account notes, CSV export, and upload tracking.
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
C:\Python314\python.exe -m unified_app.app --deep-refresh-sources
C:\Python314\python.exe -m unified_app.app --source-digest
C:\Python314\python.exe -m unified_app.app --source-digest-export
C:\Python314\python.exe -m unified_app.app --draft-top 5
C:\Python314\python.exe -m unified_app.app --make-drafts
C:\Python314\python.exe -m unified_app.app --drafts
C:\Python314\python.exe -m unified_app.app --doctor
C:\Python314\python.exe -m unified_app.app --detect https://www.tiktok.com/@example
C:\Python314\python.exe -m unified_app.app --paste-go "street food video in Kampala"
C:\Python314\python.exe -m unified_app.app --paste-action "street food video in Kampala"
C:\Python314\python.exe -m unified_app.app --workflows
C:\Python314\python.exe -m unified_app.app --workflow caption
C:\Python314\python.exe -m unified_app.app --workflow-info caption
C:\Python314\python.exe -m unified_app.app --duplicates .
C:\Python314\python.exe -m unified_app.app --clean-rename C:\path\to\folder
C:\Python314\python.exe -m unified_app.app --today 5
C:\Python314\python.exe -m unified_app.app --export-today 5
C:\Python314\python.exe -m unified_app.app --calendar 14
C:\Python314\python.exe -m unified_app.app --thumbnail C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --extract-audio C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --tiktok-ready C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --ready-package C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --burn-caption C:\path\to\video.mp4 "Watch this before you scroll"
C:\Python314\python.exe -m unified_app.app --watermark C:\path\to\video.mp4 "@yourpage"
C:\Python314\python.exe -m unified_app.app --brand-video C:\path\to\video.mp4 "Watch this" "@yourpage"
C:\Python314\python.exe -m unified_app.app --srt C:\path\to\video.mp4 "Caption text here"
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3 --batch-queue --batch-account mypage
C:\Python314\python.exe -m unified_app.app --tiktok-profile https://www.tiktok.com/@example
C:\Python314\python.exe -m unified_app.app --profile-snapshots
C:\Python314\python.exe -m unified_app.app --library
C:\Python314\python.exe -m unified_app.app --library-summary
C:\Python314\python.exe -m unified_app.app --library-rebuild
C:\Python314\python.exe -m unified_app.app --schedule-drafts 7
C:\Python314\python.exe -m unified_app.app --set-status draft:1 ready
C:\Python314\python.exe -m unified_app.app --mark-uploaded draft:1
C:\Python314\python.exe -m unified_app.app --library-export
C:\Python314\python.exe -m unified_app.app --accounts
C:\Python314\python.exe -m unified_app.app --login-account mypage
C:\Python314\python.exe -m unified_app.app --import-cookies mypage C:\path\to\cookies.json
C:\Python314\python.exe -m unified_app.app --browser-sessions
C:\Python314\python.exe -m unified_app.app --import-browser-session mypage auto
C:\Python314\python.exe -m unified_app.app --queue-ready mypage
C:\Python314\python.exe -m unified_app.app --queue
C:\Python314\python.exe -m unified_app.app --queue-dry-run 1
C:\Python314\python.exe -m unified_app.app --queue-run 1
C:\Python314\python.exe -m unified_app.app --daily
C:\Python314\python.exe -m unified_app.app --daily-export
C:\Python314\python.exe -m unified_app.app --settings
C:\Python314\python.exe -m unified_app.app --set watermark @leosoft
C:\Python314\python.exe -m unified_app.app --analytics
C:\Python314\python.exe -m unified_app.app --analytics-export
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

Current status on this machine: FFmpeg is green because the app can use Playwright bundled FFmpeg.

## Workflow Presets

Available workflow IDs:

- `ai_short`
- `compilation`
- `upload`
- `schedule`
- `translate`
- `caption`
- `batch_prepare`
- `repurpose_youtube`
- `source_tools`

Run `C:\Python314\python.exe -m unified_app.app --workflows` to list them.

## Phase 2 Paste & Go

The home screen now detects and acts on:

- TikTok profile/page: saves source, fetches public metadata, attempts to discover public video links, generates reusable hashtags and next-post ideas.
- TikTok video link: saves candidate metadata and creates a draft caption/repost plan.
- YouTube/Shorts link: saves candidate metadata, creates a draft, and points toward uploader/yt-dlp preparation.
- Local video: creates a draft and can copy the file to the uploader-ready folder.
- Local folder: scans videos, detects duplicate groups, indexes assets, and supports clean renaming through the recommended action.
- Plain text idea: creates hooks, captions, hashtags, and a draft note without network access.

CLI examples:

```powershell
C:\Python314\python.exe -m unified_app.app --paste-go "street food video in Kampala"
C:\Python314\python.exe -m unified_app.app --paste-go https://www.tiktok.com/@example
C:\Python314\python.exe -m unified_app.app --paste-go .
C:\Python314\python.exe -m unified_app.app --paste-action .
```

## Phase 3 Workflow Presets

Workflow Presets now show readiness, inputs, outputs, and steps before running. In the desktop app, open `Workflow Presets`, click `Details` to inspect a workflow, then run it when ready.

CLI examples:

```powershell
C:\Python314\python.exe -m unified_app.app --workflows
C:\Python314\python.exe -m unified_app.app --workflow-info caption
C:\Python314\python.exe -m unified_app.app --duplicates .
C:\Python314\python.exe -m unified_app.app --clean-rename C:\path\to\folder
C:\Python314\python.exe -m unified_app.app --today 5
C:\Python314\python.exe -m unified_app.app --export-today 5
C:\Python314\python.exe -m unified_app.app --calendar 14
C:\Python314\python.exe -m unified_app.app --thumbnail C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --extract-audio C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --tiktok-ready C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --ready-package C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --burn-caption C:\path\to\video.mp4 "Watch this before you scroll"
C:\Python314\python.exe -m unified_app.app --watermark C:\path\to\video.mp4 "@yourpage"
C:\Python314\python.exe -m unified_app.app --brand-video C:\path\to\video.mp4 "Watch this" "@yourpage"
C:\Python314\python.exe -m unified_app.app --srt C:\path\to\video.mp4 "Caption text here"
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3 --batch-queue --batch-account mypage
C:\Python314\python.exe -m unified_app.app --tiktok-profile https://www.tiktok.com/@example
C:\Python314\python.exe -m unified_app.app --profile-snapshots
C:\Python314\python.exe -m unified_app.app --library
C:\Python314\python.exe -m unified_app.app --library-summary
C:\Python314\python.exe -m unified_app.app --library-rebuild
C:\Python314\python.exe -m unified_app.app --schedule-drafts 7
C:\Python314\python.exe -m unified_app.app --set-status draft:1 ready
C:\Python314\python.exe -m unified_app.app --mark-uploaded draft:1
C:\Python314\python.exe -m unified_app.app --library-export
C:\Python314\python.exe -m unified_app.app --accounts
C:\Python314\python.exe -m unified_app.app --login-account mypage
C:\Python314\python.exe -m unified_app.app --import-cookies mypage C:\path\to\cookies.json
C:\Python314\python.exe -m unified_app.app --browser-sessions
C:\Python314\python.exe -m unified_app.app --import-browser-session mypage auto
C:\Python314\python.exe -m unified_app.app --queue-ready mypage
C:\Python314\python.exe -m unified_app.app --queue
C:\Python314\python.exe -m unified_app.app --queue-dry-run 1
C:\Python314\python.exe -m unified_app.app --queue-run 1
C:\Python314\python.exe -m unified_app.app --daily
C:\Python314\python.exe -m unified_app.app --daily-export
C:\Python314\python.exe -m unified_app.app --settings
C:\Python314\python.exe -m unified_app.app --set watermark @leosoft
C:\Python314\python.exe -m unified_app.app --analytics
C:\Python314\python.exe -m unified_app.app --analytics-export
C:\Python314\python.exe -m unified_app.app --workflow caption
```

All current workflow presets report GREEN on this machine.

## Phase 4 No-Key Content Automations

Added local automations that do not need API keys:

- Duplicate video report exported to CSV.
- Clean batch rename for videos in a folder.
- What-to-post-today list from the Draft Queue.
- Local posting calendar CSV export.
- Thumbnail image generation from a video.
- MP3 audio extraction from a video.
- TikTok-ready conversion to vertical 1080x1920 MP4 with normalized audio.

These are available in the `No-Key Automations` tab and through CLI flags.

Phase 4 validation outputs created:

- `exports/duplicate-report-20260723-131147.csv`
- `exports/draft-posting-plan-20260723-131147.csv`
- `exports/thumb-pre-processed.jpg`
- `exports/audio-pre-processed.mp3`
- `TiktokAutoUploader-main/VideosDirPath/ready-20260723-131238-pre-processed.mp4`

The app uses system FFmpeg when available, otherwise `imageio-ffmpeg`, and only falls back to Playwright FFmpeg for limited cases.

## Phase 5 TikTok Page Analyzer

Added a no-key TikTok profile analyzer:

- Saves each profile/page as a local source.
- Stores profile snapshots in `creator_library.db`.
- Extracts username, visible bio/name/metrics when public HTML exposes them.
- Attempts to discover recent public video links and embedded video metadata.
- Builds reusable hashtags, caption/title patterns, next-post ideas, and content-gap notes.
- Integrates with `Paste & Go`, a new `TikTok Analyzer` desktop tab, and CLI.

TikTok can hide or change public HTML. When that happens, the app still saves a profile shell and explains what was unavailable instead of pretending the scrape worked.

## Phase 6 Local Content Library

The app now has a real production-library layer over the existing SQLite data:

- One unified list for drafts, local videos, and hunted candidates.
- Status workflow: `candidate`, `draft`, `edited`, `ready`, `scheduled`, `uploaded`, `archived`.
- Local schedule fields, account/page tracking, upload timestamp, and notes fields.
- Rebuild Library scans local videos and refreshes draft rows.
- Schedule Next 7 assigns local posting times to draft posts.
- Mark Uploaded records local upload completion without needing API keys.
- Export CSV creates a complete production-library handoff in `exports/`.
- The desktop `Library & Analytics` tab now acts as the production dashboard.

This keeps the app simple: paste links, prepare content, schedule locally, upload through your saved browser/session flow, then mark the item uploaded.

## Phase 7 Make It TikTok Ready Package

Added a full one-click ready package workflow for local videos:

- Converts the video to TikTok vertical MP4 in the uploader-ready folder.
- Creates a thumbnail image in `exports/`.
- Extracts MP3 audio in `exports/`.
- Generates caption and hashtag text locally.
- Creates or updates a Draft Queue row.
- Marks the draft and local asset as `ready` in the production library.
- Records the operation in Jobs.

Use the `Full Ready Package` button from `Paste & Go` or `No-Key Automations`, or run:

```powershell
C:\Python314\python.exe -m unified_app.app --ready-package C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --burn-caption C:\path\to\video.mp4 "Watch this before you scroll"
C:\Python314\python.exe -m unified_app.app --watermark C:\path\to\video.mp4 "@yourpage"
C:\Python314\python.exe -m unified_app.app --brand-video C:\path\to\video.mp4 "Watch this" "@yourpage"
C:\Python314\python.exe -m unified_app.app --srt C:\path\to\video.mp4 "Caption text here"
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3 --batch-queue --batch-account mypage
```

## Phase 8 Accounts & Upload Queue

Added a no-key account/session manager and upload queue:

- Detects saved TikTok account cookie files in `TiktokAutoUploader-main/CookiesDir`.
- Reports local session health based on whether a `sessionid` cookie exists.
- Starts the existing uploader login flow with `cli.py login -n ACCOUNT`.
- Queues ready/scheduled production-library videos for upload.
- Prepares dry-run uploader commands before real upload.
- Can run the existing uploader automation for a selected queue item.
- Tracks queue status: `queued`, `running`, `done`, `failed`, `cancelled`.
- Integrates with the new `Accounts & Upload Queue` desktop tab and CLI.

This keeps login simple: add/re-login an account once, then queue ready videos without API keys.

## Browser Cookie Import

`Accounts & Upload Queue` now has `Import Cookies`. Use it when you already have TikTok logged in elsewhere and have exported cookies intentionally. Supported inputs:

- JSON cookie exports containing a list or a `cookies` list.
- Netscape cookie text exports.
- Existing uploader `.cookie` pickle files.

The importer saves to `TiktokAutoUploader-main/CookiesDir/tiktok_session-ACCOUNT.cookie` and marks the account healthy only when a `sessionid` cookie is present.

## Phase 9 Creator Pipeline Analytics

Added local pipeline analytics:

- Counts drafts, assets, candidates, upload queue items, account health, sources, profile snapshots, and jobs.
- Shows recommended next actions based on bottlenecks.
- Appears inside `Library & Analytics`.
- Exports a text report into `exports/`.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --daily
C:\Python314\python.exe -m unified_app.app --daily-export
C:\Python314\python.exe -m unified_app.app --settings
C:\Python314\python.exe -m unified_app.app --set watermark @leosoft
C:\Python314\python.exe -m unified_app.app --analytics
C:\Python314\python.exe -m unified_app.app --analytics-export
```

## Phase 10 No-Key Content Sourcing Digest

Content Hunt is now a daily sourcing tool, not just a link saver:

- Expands saved sources, feeds, and pages into candidate links.
- Scores candidates locally based on title, description, media links, and creator-friendly patterns.
- Adds rights/usage notes for each candidate.
- Generates an idea prompt with hook, caption, and hashtags.
- Shows a scored digest in the `Content Hunt` tab.
- Exports sourcing digest CSV files into `exports/`.
- Can create drafts from top scored candidates.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --deep-refresh-sources
C:\Python314\python.exe -m unified_app.app --source-digest
C:\Python314\python.exe -m unified_app.app --source-digest-export
C:\Python314\python.exe -m unified_app.app --draft-top 5
```

Reminder: this is for owned content, permitted content, public-domain/licensed material, research, and inspiration. The app keeps rights notes visible so reposting does not become accidental.

## Phase 11 Caption & Branding Studio

Added local caption and branding tools:

- Burn caption/title text into a video.
- Add a text watermark.
- Create a branded video with caption plus watermark.
- Generate simple `.srt` sidecar captions from text.
- Saves generated videos into `TiktokAutoUploader-main/VideosDirPath`.
- Saves SRT files into `exports/`.
- Available in `No-Key Automations` and CLI.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --burn-caption C:\path\to\video.mp4 "Watch this before you scroll"
C:\Python314\python.exe -m unified_app.app --watermark C:\path\to\video.mp4 "@yourpage"
C:\Python314\python.exe -m unified_app.app --brand-video C:\path\to\video.mp4 "Watch this" "@yourpage"
C:\Python314\python.exe -m unified_app.app --srt C:\path\to\video.mp4 "Caption text here"
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3 --batch-queue --batch-account mypage
```

## Phase 12 Daily Command Center

Added a daily command center that becomes the first desktop tab:

- Shows today's pipeline snapshot.
- Lists recommended focus actions.
- Shows scheduled posts for today.
- Shows ready videos/drafts that can be queued or uploaded.
- Shows upload queue state.
- Highlights blocked work, such as missing TikTok session health or queue items without accounts.
- Exports a daily CSV work plan into `exports/`.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --daily
C:\Python314\python.exe -m unified_app.app --daily-export
C:\Python314\python.exe -m unified_app.app --settings
C:\Python314\python.exe -m unified_app.app --set watermark @leosoft
```

## Phase 13 Batch Campaign Builder

Added batch campaign processing for local folders:

- Clean-renames videos in a selected folder.
- Creates a duplicate report.
- Builds full ready packages for a limited number of videos.
- Creates drafts, thumbnails, audio, and uploader-ready MP4s through the existing ready-package flow.
- Optionally queues finished videos for upload and assigns an account.
- Exports a campaign CSV report into `exports/`.
- Available from `No-Key Automations` and CLI.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3
C:\Python314\python.exe -m unified_app.app --batch-campaign C:\path\to\folder --batch-limit 3 --batch-queue --batch-account mypage
```

## Phase 14 Brand Profile & Defaults

Added app-wide brand/default settings:

- Brand name.
- TikTok handle.
- Default uploader account.
- Watermark text.
- Default hashtags.
- Caption style note.
- Posting hour.
- Batch limit.

These settings are used by scheduling, queueing, batch campaigns, and branding when the user does not provide a value.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --settings
C:\Python314\python.exe -m unified_app.app --set watermark @leosoft
C:\Python314\python.exe -m unified_app.app --set default_account mypage
```


## Creator OS Features

The desktop app now includes a `Creator OS` tab for the next production layer:

- Real Upload Assistant Mode: pick a queue item, review video/caption/account health, preview uploader command, then confirm the posted URL.
- Content Calendar Board: Today, This week, Scheduled, Ready, Uploaded, Missed, and Needs account.
- Caption Library: reusable caption styles for sales, education, repair/tech, funny, storytelling, and calls to action.
- Hashtag Sets: reusable packs for LEOSOFT repair, Uganda tech, phone repair, business promo, and tutorials.
- Draft Editor: edit title, hook, caption, hashtags, notes, account, status, and schedule date.
- Upload Result Tracker: stores TikTok URL, upload date, account, caption, views, likes, comments, shares, and notes.
- Performance Analytics: local production and upload tracking summaries.
- Content Templates: before/after repair, product showcase, customer question, 3 tips, mistake to avoid, promo offer, and behind the scenes.
- Thumbnail/Frame Picker: generates multiple frame choices and stores the selected thumbnail.
- Auto-Repurpose Long Video: cuts a source video into TikTok-ready clips and creates drafts.
- Series Builder: creates multi-part draft campaigns.
- Backup / Restore: creates local zip backups and restores the database with a safety copy.

CLI examples:

```powershell
C:\Python314\python.exe -m unified_app.app --calendar-board 7
C:\Python314\python.exe -m unified_app.app --upload-assistant 1
C:\Python314\python.exe -m unified_app.app --confirm-upload 1 https://www.tiktok.com/@mypage/video/123
C:\Python314\python.exe -m unified_app.app --caption-styles
C:\Python314\python.exe -m unified_app.app --apply-caption-style 1 "Repair/tech caption"
C:\Python314\python.exe -m unified_app.app --hashtag-sets
C:\Python314\python.exe -m unified_app.app --apply-hashtag-set 1 "LEOSOFT repair"
C:\Python314\python.exe -m unified_app.app --templates
C:\Python314\python.exe -m unified_app.app --template-draft "3 tips" "phone repair battery care"
C:\Python314\python.exe -m unified_app.app --draft-update 1 notes "ready for review"
C:\Python314\python.exe -m unified_app.app --thumbnail-choices C:\path\to\video.mp4
C:\Python314\python.exe -m unified_app.app --repurpose-long C:\path\to\long-video.mp4 --segment-seconds 45 --parts 3
C:\Python314\python.exe -m unified_app.app --series-create "Battery Care Series" "phone battery care" --parts 3
C:\Python314\python.exe -m unified_app.app --performance
C:\Python314\python.exe -m unified_app.app --backup
C:\Python314\python.exe -m unified_app.app --backups
```


## Direct Browser Session Import

In `Accounts & Upload Queue`, click `Import From Browser` to pull your TikTok login from Chrome, Edge, Brave, or Firefox without manually exporting cookies. Use `auto` to scan all detected profiles, or choose one browser name.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --browser-sessions
C:\Python314\python.exe -m unified_app.app --import-browser-session mypage auto
C:\Python314\python.exe -m unified_app.app --import-browser-session mypage chrome
C:\Python314\python.exe -m unified_app.app --import-browser-session mypage firefox
```

This stays local on your machine. If no `sessionid` is found, open TikTok in that browser, log in, then run the import again.


## Upload Readiness Improvements

The upload tab now includes:

- `Browser Health`: checks Chrome, Edge, Brave, and Firefox for TikTok login status without printing cookie values.
- `Auto Account`: assigns a healthy TikTok account to queued items that do not have one yet.
- `Preflight`: checks the selected queue item for video file, caption, account assignment, session health, and uploader command readiness.

CLI:

```powershell
C:\Python314\python.exe -m unified_app.app --browser-session-health
C:\Python314\python.exe -m unified_app.app --queue-auto-account mypage
C:\Python314\python.exe -m unified_app.app --queue-preflight 1
```
