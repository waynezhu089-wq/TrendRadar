import hashlib
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import feedparser
from bs4 import BeautifulSoup

from .base import BaseConnector, CollectionResult, NormalizedItem


FEEDS = {
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Google DeepMind Blog": "https://deepmind.google/blog/rss.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
}
MAX_ITEMS = 3
MAX_FEED_BYTES = 2_000_000


def normalized_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def plain_text(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())[:5000]


def entry_time(entry) -> datetime | None:
    # feedparser aliases missing published fields to updated; avoid inventing publication times.
    parsed = dict(entry).get("published_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def sort_time(entry) -> datetime:
    if entry_time(entry):
        return entry_time(entry)
    updated = dict(entry).get("updated_parsed")
    if updated:
        try:
            return datetime(*updated[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


class RSSConnector(BaseConnector):
    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def _fetch(self, url: str):
        request = Request(url, headers={"User-Agent": "DSIH-RSS/0.1", "Accept":
            "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read(MAX_FEED_BYTES + 1)
        except HTTPError as error:
            raise ValueError(f"Feed HTTP {error.code}") from None
        except URLError as error:
            raise ValueError(f"Feed network error: {type(error.reason).__name__}") from None
        if len(body) > MAX_FEED_BYTES:
            raise ValueError("Feed exceeds size limit")
        feed = feedparser.parse(body)
        if not feed.version or not feed.entries:
            raise ValueError("No valid RSS/Atom entries")
        return feed

    def normalize(self, source: str, raw: dict) -> NormalizedItem:
        if source not in FEEDS:
            raise ValueError("Unsupported RSS source")
        title = str(raw.get("title") or "").strip()
        canonical = next((link.get("href", "") for link in raw.get("links", [])
                          if link.get("rel") == "canonical" and link.get("href")), "")
        url = normalized_url(canonical or str(raw.get("link") or ""))
        guid = str(raw.get("id") or raw.get("guid") or "").strip()
        published = entry_time(raw)
        if not title:
            raise ValueError("RSS entry has no title")
        identity = guid or url or f"{title}\0{published.isoformat() if published else ''}"
        external_id = "rss:" + hashlib.sha256(f"{source}\0{identity}".encode("utf-8")).hexdigest()
        content_entries = raw.get("content") or []
        content_html = str(content_entries[0].get("value") or "") if content_entries else ""
        summary_html = str(raw.get("summary") or raw.get("description") or "")
        author = str(raw.get("author") or "").strip() or None
        raw_json = {"id": guid or None, "title": title, "link": url,
                    "content": content_html[:10000] or None, "summary": summary_html[:10000] or None,
                    "author": author, "published": dict(raw).get("published"), "updated": dict(raw).get("updated")}
        return NormalizedItem(source=source, external_id=external_id, title=title, url=url,
                              content=plain_text(content_html or summary_html), author=author,
                              published_at=published, captured_at=datetime.now(timezone.utc),
                              raw_json=raw_json)

    def collect(self) -> list[CollectionResult]:
        results = []
        for name, url in FEEDS.items():
            try:
                feed = self._fetch(url)
                entries = sorted(feed.entries, key=sort_time, reverse=True)[:MAX_ITEMS]
                items = [self.normalize(name, entry) for entry in entries]
                results.append(CollectionResult(name, items, len(entries)))
            except ValueError as error:
                results.append(CollectionResult(name, [], error=str(error)))
            except Exception:
                results.append(CollectionResult(name, [], error="Feed fetch or parse failed"))
        return results

    def health(self) -> bool:
        try:
            return bool(self._fetch(next(iter(FEEDS.values()))).entries)
        except Exception:
            return False
