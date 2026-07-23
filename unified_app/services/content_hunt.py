from __future__ import annotations

import html
import ipaddress
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from unified_app.config import Candidate, IMAGE_EXTS, USER_AGENT, VIDEO_EXTS
from unified_app.services.db import connect, init_db, now_iso
from unified_app.services.jobs import add_job


SEARCH_LIMIT_MAX = 25
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
BING_RSS_URL = "https://www.bing.com/search"


def looks_like_url(value: str) -> bool:
    value = (value or "").strip()
    if not value or any(ch.isspace() for ch in value):
        return False
    if re.match(r"^https?://", value, re.I):
        return True
    return bool(re.match(r"^(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?::\d+)?(?:[/#?].*)?$", value, re.I))


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if value and not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    return value


def _host_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def classify_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if _host_matches(host, "tiktok.com"):
        return "tiktok"
    if _host_matches(host, "youtube.com") or _host_matches(host, "youtu.be"):
        return "youtube"
    if path.endswith((".rss", ".xml")) or "feed" in path:
        return "feed"
    return "web"


def _validate_public_url(url: str) -> str:
    url = normalize_url(url)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("URL is missing a hostname")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Localhost URLs are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("Private or local network URLs are not allowed")
    return url


def fetch_url(url: str) -> str:
    url = _validate_public_url(url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(2_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def extract_attr(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    return html.unescape(match.group(1).strip()) if match else ""


def extract_links(page: str, base: str) -> list[str]:
    raw = re.findall(r"""(?:href|src)=["']([^"']+)["']""", page, re.I)
    raw += re.findall(r"""https?://[^\s"'<>]+""", page, re.I)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        item = html.unescape(item).strip()
        if item.startswith(("mailto:", "javascript:", "data:")):
            continue
        link = urllib.parse.urljoin(base, item)
        if link.startswith(("http://", "https://")) and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def analyze_url(url: str) -> Candidate:
    url = _validate_public_url(url)
    page = fetch_url(url)
    title = extract_attr(page, r"<title[^>]*>(.*?)</title>") or urllib.parse.urlparse(url).netloc
    desc = extract_attr(
        page,
        r"""<meta[^>]+(?:name|property)=["'](?:description|og:description)["'][^>]+content=["']([^"']*)["']""",
    )
    if not desc:
        desc = extract_attr(
            page,
            r"""<meta[^>]+content=["']([^"']*)["'][^>]+(?:name|property)=["'](?:description|og:description)["']""",
        )
    links = extract_links(page, url)
    media = [
        link
        for link in links
        if Path(urllib.parse.urlparse(link).path).suffix.lower() in (VIDEO_EXTS | IMAGE_EXTS)
    ]
    return Candidate(
        url,
        title,
        desc,
        classify_url(url),
        media,
        "Review rights before reposting; use for owned, permitted, public-domain, or inspiration workflows.",
    )


def save_candidate(candidate: Candidate) -> None:
    init_db()
    with connect() as db:
        db.execute(
            """insert into content_candidates(url,title,description,source_type,media_urls,notes,created_at)
            values (?,?,?,?,?,?,?) on conflict(url) do update set title=excluded.title,
            description=excluded.description, source_type=excluded.source_type,
            media_urls=excluded.media_urls, notes=excluded.notes""",
            (
                candidate.url,
                candidate.title[:500],
                candidate.description[:1200],
                candidate.source_type,
                json.dumps(candidate.media_urls[:80]),
                candidate.notes,
                now_iso(),
            ),
        )
        db.commit()


def hunt_urls(values: list[str]) -> tuple[list[Candidate], list[str]]:
    found: list[Candidate] = []
    errors: list[str] = []
    for raw in values:
        if not raw.strip():
            continue
        if not looks_like_url(raw):
            errors.append(f"{raw}: this does not look like a URL")
            continue
        url = normalize_url(raw)
        try:
            candidate = analyze_url(url)
            save_candidate(candidate)
            found.append(candidate)
            add_job("hunt", url, "done", candidate.title)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            add_job("hunt", url, "failed", str(exc))
    return found, errors


def _platform_query(keyword: str, platform: str) -> str:
    keyword = " ".join((keyword or "").split())
    selected = (platform or "all").strip().lower()
    if selected == "youtube":
        return f"{keyword} site:youtube.com"
    if selected == "tiktok":
        return f"{keyword} site:tiktok.com"
    if selected == "web":
        return f"{keyword} -site:youtube.com -site:tiktok.com"
    return keyword


def _decode_search_url(value: str) -> str:
    value = html.unescape((value or "").strip())
    if value.startswith("//"):
        value = "https:" + value
    parsed = urllib.parse.urlsplit(value)
    if _host_matches(parsed.hostname or "", "duckduckgo.com"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            value = urllib.parse.unquote(target)
    return value


def _clean_search_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(value).split())


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._capture = ""
        self._buffer: list[str] = []
        self._href = ""

    @staticmethod
    def _classes(attrs) -> set[str]:
        values = dict(attrs).get("class", "")
        return {part.strip() for part in values.split() if part.strip()}

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = self._classes(attrs)
        if tag == "a" and "result__a" in classes:
            self._capture = "title"
            self._buffer = []
            self._href = dict(attrs).get("href", "")
        elif "result__snippet" in classes:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            title = _clean_search_text(" ".join(self._buffer))
            url = _decode_search_url(self._href)
            if title and url:
                self.results.append({"title": title, "url": url, "description": ""})
            self._capture = ""
            self._buffer = []
            self._href = ""
        elif self._capture == "snippet" and tag in {"a", "div", "span"}:
            snippet = _clean_search_text(" ".join(self._buffer))
            if snippet and self.results and not self.results[-1]["description"]:
                self.results[-1]["description"] = snippet
            self._capture = ""
            self._buffer = []


def _duckduckgo_results(query: str, limit: int) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        f"{DDG_SEARCH_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        page = response.read(2_000_000).decode(
            response.headers.get_content_charset() or "utf-8",
            errors="replace",
        )
    parser = _DuckDuckGoParser()
    parser.feed(page)
    return parser.results[:limit]


def _bing_rss_results(query: str, limit: int) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query, "format": "rss"})
    req = urllib.request.Request(
        f"{BING_RSS_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(2_000_000)
    root = ET.fromstring(data)
    out: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = _clean_search_text(item.findtext("title", default=""))
        url = _decode_search_url(item.findtext("link", default=""))
        description = _clean_search_text(item.findtext("description", default=""))
        if title and url:
            out.append({"title": title, "url": url, "description": description})
        if len(out) >= limit:
            break
    return out


def _matches_platform(url: str, platform: str) -> bool:
    selected = (platform or "all").strip().lower()
    source_type = classify_url(url)
    if selected == "youtube":
        return source_type == "youtube"
    if selected == "tiktok":
        return source_type == "tiktok"
    if selected == "web":
        return source_type not in {"youtube", "tiktok"}
    return True


def search_keywords(
    keyword: str,
    platform: str = "all",
    limit: int = 10,
) -> tuple[list[Candidate], list[str]]:
    keyword = " ".join((keyword or "").split())
    if not keyword:
        return [], ["Search keyword is empty"]
    limit = max(1, min(int(limit or 10), SEARCH_LIMIT_MAX))
    search_query = _platform_query(keyword, platform)
    provider_errors: list[str] = []
    raw_results: list[dict[str, str]] = []

    try:
        raw_results = _duckduckgo_results(search_query, limit * 2)
    except Exception as exc:
        provider_errors.append(f"DuckDuckGo search failed: {exc}")

    if not raw_results:
        try:
            raw_results = _bing_rss_results(search_query, limit * 2)
        except Exception as exc:
            provider_errors.append(f"Bing fallback failed: {exc}")

    found: list[Candidate] = []
    seen: set[str] = set()
    for row in raw_results:
        url = _decode_search_url(row.get("url", ""))
        if not url.startswith(("http://", "https://")):
            continue
        if not _matches_platform(url, platform) or url in seen:
            continue
        seen.add(url)
        candidate = Candidate(
            url,
            row.get("title", "") or urllib.parse.urlparse(url).netloc,
            row.get("description", ""),
            classify_url(url),
            [],
            f"Found from keyword search: {keyword}. Review rights before reuse; treat as research or inspiration unless permission is confirmed.",
        )
        save_candidate(candidate)
        found.append(candidate)
        add_job("keyword_hunt", keyword, "done", f"{candidate.source_type}: {candidate.title}")
        if len(found) >= limit:
            break

    errors: list[str] = []
    if not found:
        errors.extend(provider_errors or [f"No results found for: {keyword}"])
        add_job("keyword_hunt", keyword, "failed", "; ".join(errors))
    return found, errors


def hunt_inputs(
    values: list[str],
    platform: str = "all",
    limit: int = 10,
) -> tuple[list[Candidate], list[str]]:
    found: list[Candidate] = []
    errors: list[str] = []
    normalized_limit = max(1, min(int(limit or 10), SEARCH_LIMIT_MAX))
    remaining = normalized_limit

    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        if looks_like_url(value):
            candidates, item_errors = hunt_urls([value])
        else:
            candidates, item_errors = search_keywords(value, platform=platform, limit=remaining)
        for candidate in candidates:
            if candidate.url not in {item.url for item in found}:
                found.append(candidate)
        errors.extend(item_errors)
        remaining = max(0, normalized_limit - len(found))
        if remaining == 0:
            break
    return found, errors


def save_source(url: str, label: str = "") -> tuple[bool, str]:
    init_db()
    if not looks_like_url(url):
        return False, "Enter a public URL when saving a source"
    url = _validate_public_url(url)
    label = label.strip() or urllib.parse.urlparse(url).netloc or url
    with connect() as db:
        db.execute(
            """insert into content_sources(url,label,source_type,created_at) values (?,?,?,?)
            on conflict(url) do update set label=excluded.label, source_type=excluded.source_type, status='active'""",
            (url, label[:160], classify_url(url), now_iso()),
        )
        db.commit()
    add_job("source", url, "saved", label)
    return True, f"Saved source: {label}"


def recent_sources(limit: int = 100) -> list[tuple]:
    init_db()
    with connect() as db:
        return db.execute(
            "select id,source_type,label,url,status,last_checked_at from content_sources order by id desc limit ?",
            (limit,),
        ).fetchall()


def refresh_sources() -> tuple[int, int]:
    init_db()
    ok = 0
    failed = 0
    with connect() as db:
        rows = db.execute(
            "select id,url from content_sources where status='active' order by id desc"
        ).fetchall()
    for source_id, url in rows:
        candidates, errors = hunt_urls([url])
        if candidates:
            ok += 1
            with connect() as db:
                db.execute(
                    "update content_sources set last_checked_at=? where id=?",
                    (now_iso(), source_id),
                )
                db.commit()
        if errors:
            failed += 1
    add_job("refresh", "sources", "done", f"{ok} refreshed, {failed} failed")
    return ok, failed
