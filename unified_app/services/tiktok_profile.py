from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from unified_app.config import USER_AGENT
from unified_app.services.browser_cookies import cookie_header_for_tiktok, read_tiktok_cookies
from unified_app.services.content_hunt import fetch_url, normalize_url, save_source
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.drafts import content_pack
from unified_app.services.jobs import add_job


@dataclass
class TikTokVideoInfo:
    url: str = ""
    title: str = ""
    created_at: str = ""
    plays: str = ""
    likes: str = ""
    comments: str = ""
    shares: str = ""


@dataclass
class TikTokProfileReport:
    profile_url: str
    username: str
    nickname: str = ""
    bio: str = ""
    follower_count: str = ""
    following_count: str = ""
    heart_count: str = ""
    video_count: str = ""
    recent_videos: list[TikTokVideoInfo] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    caption_patterns: list[str] = field(default_factory=list)
    next_post_ideas: list[str] = field(default_factory=list)
    content_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def extract_username(value: str) -> str:
    value = normalize_url(value)
    parsed = urllib.parse.urlparse(value)
    match = re.search(r"/@([^/?#]+)", parsed.path)
    if match:
        return "@" + urllib.parse.unquote(match.group(1))
    return parsed.path.strip("/").split("/")[0] or parsed.netloc or value


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _compact_count(value: Any) -> str:
    if value is None:
        return ""
    return _clean_text(value)


def _walk_json(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_json(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_json(value)


def _json_blobs(page: str) -> list[Any]:
    blobs: list[Any] = []
    patterns = [
        r'<script[^>]+id="SIGI_STATE"[^>]*>(.*?)</script>',
        r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, page, re.I | re.S):
            try:
                blobs.append(json.loads(html.unescape(raw.strip())))
            except json.JSONDecodeError:
                continue
    return blobs


def _meta(page: str, pattern: str) -> str:
    match = re.search(pattern, page, re.I | re.S)
    return _clean_text(match.group(1)) if match else ""


def _video_url(username: str, video_id: str) -> str:
    handle = username if username.startswith("@") else "@" + username
    return f"https://www.tiktok.com/{handle}/video/{video_id}"


def _extract_videos_from_text(page: str, username: str) -> list[TikTokVideoInfo]:
    videos: list[TikTokVideoInfo] = []
    seen: set[str] = set()
    expanded = html.unescape(page).replace("\\u002F", "/").replace("\\/", "/")
    for url in re.findall(r"https://(?:www\.)?tiktok\.com/@[^\"'\\< >]+/video/\d+", expanded):
        clean = url.split("?")[0]
        if clean in seen:
            continue
        seen.add(clean)
        videos.append(TikTokVideoInfo(url=clean))
    for video_id in re.findall(r'(?:(?:"|\\")id(?:"|\\")|(?:"|\\")videoId(?:"|\\"))\s*:\s*(?:"|\\")?(\d{8,})', expanded):
        url = _video_url(username, video_id)
        if url not in seen:
            seen.add(url)
            videos.append(TikTokVideoInfo(url=url))
    for video_id in re.findall(r'/video/(\d{8,})', expanded):
        url = _video_url(username, video_id)
        if url not in seen:
            seen.add(url)
            videos.append(TikTokVideoInfo(url=url))
    return videos[:40]


def _extract_from_json(blobs: list[Any], username: str) -> tuple[dict[str, str], list[TikTokVideoInfo]]:
    profile: dict[str, str] = {}
    videos: list[TikTokVideoInfo] = []
    seen: set[str] = set()
    for blob in blobs:
        for item in _walk_json(blob):
            user = item.get("user") if isinstance(item.get("user"), dict) else item
            stats = item.get("stats") or item.get("statsV2") or item.get("authorStats") or {}
            if isinstance(user, dict) and any(k in user for k in ("uniqueId", "nickname", "signature")):
                unique_id = _first(user.get("uniqueId"), user.get("unique_id"))
                if unique_id and username.lower().lstrip("@") not in unique_id.lower() and not profile:
                    continue
                profile["username"] = "@" + unique_id.lstrip("@") if unique_id else profile.get("username", username)
                profile["nickname"] = _first(user.get("nickname"), profile.get("nickname"))
                profile["bio"] = _first(user.get("signature"), user.get("bio"), profile.get("bio"))
                if isinstance(stats, dict):
                    profile["followers"] = _first(stats.get("followerCount"), stats.get("follower_count"), profile.get("followers"))
                    profile["following"] = _first(stats.get("followingCount"), stats.get("following_count"), profile.get("following"))
                    profile["hearts"] = _first(stats.get("heartCount"), stats.get("diggCount"), profile.get("hearts"))
                    profile["videos"] = _first(stats.get("videoCount"), profile.get("videos"))
            desc = _first(item.get("desc"), item.get("description"), item.get("title"))
            video_id = _first(item.get("id"), item.get("videoId"))
            if not desc and not video_id:
                continue
            if not video_id or not re.fullmatch(r"\d{8,}", video_id):
                continue
            url = _video_url(profile.get("username", username), video_id)
            if url in seen:
                continue
            seen.add(url)
            stats = item.get("stats") or item.get("statsV2") or {}
            created = ""
            if item.get("createTime"):
                try:
                    created = datetime.fromtimestamp(int(item["createTime"]), timezone.utc).date().isoformat()
                except (TypeError, ValueError, OSError):
                    created = _first(item.get("createTime"))
            videos.append(TikTokVideoInfo(
                url=url,
                title=desc,
                created_at=created,
                plays=_compact_count(stats.get("playCount") or stats.get("play_count") if isinstance(stats, dict) else ""),
                likes=_compact_count(stats.get("diggCount") or stats.get("likeCount") if isinstance(stats, dict) else ""),
                comments=_compact_count(stats.get("commentCount") if isinstance(stats, dict) else ""),
                shares=_compact_count(stats.get("shareCount") if isinstance(stats, dict) else ""),
            ))
    return profile, videos[:40]


def _caption_patterns(videos: list[TikTokVideoInfo], bio: str, fallback_title: str) -> tuple[list[str], list[str], list[str]]:
    text = " ".join([v.title for v in videos if v.title] + [bio, fallback_title])
    pack = content_pack(text or fallback_title or "TikTok creator profile", "")
    hashtags = sorted({tag.lower() for tag in re.findall(r"#[A-Za-z0-9_]+", text)})
    if not hashtags:
        hashtags = pack["hashtags"]
    starts: list[str] = []
    for video in videos:
        title = video.title.strip()
        if title:
            starts.append(title[:90])
    patterns = starts[:5] or ["No recent captions visible yet; use the ideas below as draft prompts, not detected patterns."]
    ideas = pack["hooks"][:5]
    return hashtags[:12], patterns[:6], ideas[:6]


def _content_gaps(report: TikTokProfileReport) -> list[str]:
    gaps: list[str] = []
    text = " ".join(v.title.lower() for v in report.recent_videos)
    if not report.recent_videos:
        gaps.append("Add or expose recent public videos so the app can compare caption and topic patterns.")
    if "behind" not in text:
        gaps.append("Try a behind-the-scenes post that shows the process, setup, or mistake before the result.")
    if "how" not in text and "tip" not in text:
        gaps.append("Add a simple how-to or quick-tip post for search-friendly discovery.")
    if not report.hashtags:
        gaps.append("Create a reusable hashtag set from your niche, location, format, and audience.")
    if len(report.recent_videos) < 5:
        gaps.append("Keep at least five recent public posts visible for stronger local analytics.")
    return gaps[:5]


def save_profile_snapshot(report: TikTokProfileReport) -> None:
    init_db()
    with connect() as db:
        db.execute(
            """insert into profile_snapshots(
                profile_url, username, nickname, bio, follower_count, following_count,
                heart_count, video_count, recent_videos, hashtags, content_gaps, notes, created_at)
                values (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                report.profile_url,
                report.username,
                report.nickname,
                report.bio,
                report.follower_count,
                report.following_count,
                report.heart_count,
                report.video_count,
                json.dumps([v.__dict__ for v in report.recent_videos[:40]]),
                json.dumps(report.hashtags[:20]),
                json.dumps(report.content_gaps[:10]),
                json.dumps(report.notes[:10]),
                now_iso(),
            ),
        )
        db.commit()



def _fetch_with_browser_session(url: str) -> tuple[str, str]:
    cookie_header, cookie_note = cookie_header_for_tiktok("auto")
    if not cookie_header:
        return "", cookie_note
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
            "Cookie": cookie_header,
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read(4_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace"), cookie_note



def _playwright_cookie(cookie: dict) -> dict | None:
    name = str(cookie.get("name") or "").strip()
    value = str(cookie.get("value") or "")
    domain = str(cookie.get("domain") or ".tiktok.com")
    if not name:
        return None
    out = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": str(cookie.get("path") or "/"),
        "httpOnly": bool(cookie.get("httpOnly", False)),
        "secure": bool(cookie.get("secure", True)),
    }
    expiry = cookie.get("expiry")
    if expiry:
        try:
            expires = int(expiry)
            if expires > 0:
                out["expires"] = expires
        except (TypeError, ValueError):
            pass
    same_site = cookie.get("sameSite")
    if same_site in {"Strict", "Lax", "None"}:
        out["sameSite"] = same_site
    return out


def _fetch_with_playwright_session(url: str) -> tuple[str, str]:
    cookies, cookie_note = read_tiktok_cookies("auto")
    if not cookies:
        return "", cookie_note
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return "", f"Playwright is not available: {exc}"
    prepared = [c for c in (_playwright_cookie(cookie) for cookie in cookies) if c]
    if not prepared:
        return "", "No usable TikTok cookies could be prepared for Playwright."
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
        )
        context.add_cookies(prepared)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)
        for _ in range(3):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1200)
        content = page.content()
        browser.close()
    return content, "Rendered page with Python Playwright and saved TikTok browser cookies: " + cookie_note

def _extract_page_data(page: str, username: str) -> tuple[str, str, dict[str, str], list[TikTokVideoInfo]]:
    title = _meta(page, r"<title[^>]*>(.*?)</title>") if page else ""
    desc = _meta(page, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']') if page else ""
    blobs = _json_blobs(page) if page else []
    profile, json_videos = _extract_from_json(blobs, username) if blobs else ({}, [])
    text_videos = _extract_videos_from_text(page, profile.get("username", username)) if page else []
    videos_by_url: dict[str, TikTokVideoInfo] = {}
    for video in json_videos + text_videos:
        if video.url:
            existing = videos_by_url.get(video.url)
            if existing and not existing.title and video.title:
                videos_by_url[video.url] = video
            else:
                videos_by_url.setdefault(video.url, video)
    return title, desc, profile, list(videos_by_url.values())[:40]

def analyze_tiktok_profile_url(url: str) -> TikTokProfileReport:
    init_db()
    profile_url = normalize_url(url)
    username = extract_username(profile_url)
    save_source(profile_url, username)
    notes: list[str] = []
    page = ""
    try:
        page = fetch_url(profile_url)
        notes.append("Fetched public TikTok HTML.")
    except Exception as exc:
        notes.append(f"Public TikTok page fetch failed: {exc}")
    title, desc, profile, videos = _extract_page_data(page, username)
    if not videos:
        try:
            session_page, session_note = _fetch_with_browser_session(profile_url)
            if session_page:
                session_title, session_desc, session_profile, session_videos = _extract_page_data(session_page, username)
                notes.append("Retried with saved browser TikTok session: " + session_note)
                if session_videos or len(session_page) > len(page):
                    page = session_page
                    title = session_title or title
                    desc = session_desc or desc
                    profile = {**profile, **session_profile}
                    videos = session_videos or videos
            else:
                notes.append("Browser-session retry unavailable: " + session_note)
        except Exception as exc:
            notes.append(f"Browser-session TikTok retry failed: {exc}")
    if not videos:
        try:
            rendered_page, render_note = _fetch_with_playwright_session(profile_url)
            if rendered_page:
                render_title, render_desc, render_profile, render_videos = _extract_page_data(rendered_page, username)
                notes.append(render_note)
                if render_videos or len(rendered_page) > len(page):
                    page = rendered_page
                    title = render_title or title
                    desc = render_desc or desc
                    profile = {**profile, **render_profile}
                    videos = render_videos or videos
            else:
                notes.append("Playwright browser-session render unavailable: " + render_note)
        except Exception as exc:
            notes.append(f"Playwright browser-session render failed: {exc}")
    report = TikTokProfileReport(
        profile_url=profile_url,
        username=profile.get("username", username),
        nickname=profile.get("nickname", ""),
        bio=_first(profile.get("bio"), desc),
        follower_count=profile.get("followers", ""),
        following_count=profile.get("following", ""),
        heart_count=profile.get("hearts", ""),
        video_count=profile.get("videos", ""),
        recent_videos=videos[:40],
        notes=notes,
    )
    if not page:
        report.notes.append("No TikTok HTML was available, so the report is a saved profile shell.")
    elif not report.recent_videos:
        report.notes.append("No recent video objects were exposed even after the available fetch attempts. TikTok may be returning a minimal or bot-protected page; open the profile in your browser, scroll the videos once, then run the analyzer again.")
    report.hashtags, report.caption_patterns, report.next_post_ideas = _caption_patterns(report.recent_videos, report.bio, title)
    report.content_gaps = _content_gaps(report)
    save_profile_snapshot(report)
    add_job("tiktok_profile", profile_url, "done" if report.recent_videos else "partial", f"Saved snapshot for {report.username} with {len(report.recent_videos)} videos")
    return report


def format_profile_report(report: TikTokProfileReport) -> str:
    lines = [
        "TikTok Page Analyzer",
        f"Profile: {report.profile_url}",
        f"Username: {report.username}",
    ]
    if report.nickname:
        lines.append(f"Name: {report.nickname}")
    if report.bio:
        lines.append(f"Bio: {report.bio[:700]}")
    metrics = []
    for label, value in (("Followers", report.follower_count), ("Following", report.following_count), ("Hearts", report.heart_count), ("Videos", report.video_count)):
        if value:
            metrics.append(f"{label}: {value}")
    if metrics:
        lines += ["", "Visible metrics:", *["  - " + x for x in metrics]]
    lines += ["", f"Recent public videos found: {len(report.recent_videos)}"]
    for video in report.recent_videos[:12]:
        bits = [video.url]
        if video.title:
            bits.append(video.title[:140])
        if video.created_at:
            bits.append("date " + video.created_at)
        if video.plays:
            bits.append("plays " + video.plays)
        lines.append("  - " + " | ".join(bits))
    lines += ["", "Caption/title patterns:"]
    lines += ["  - " + x for x in report.caption_patterns[:6]]
    lines += ["", "Reusable hashtag set:", "  " + " ".join(report.hashtags[:12])]
    lines += ["", "Next-post ideas:"]
    lines += ["  - " + x for x in report.next_post_ideas[:6]]
    lines += ["", "Content gaps:"]
    lines += ["  - " + x for x in report.content_gaps[:6]]
    if report.notes:
        lines += ["", "Notes:"] + ["  - " + x for x in report.notes]
    return "\n".join(lines)


def recent_profile_snapshots(limit: int = 25) -> list[tuple]:
    init_db()
    with connect() as db:
        return list(db.execute(
            """select id, username, nickname, follower_count, video_count, profile_url, created_at
               from profile_snapshots order by id desc limit ?""",
            (limit,),
        ))
