"""Bounded public RSS/HTML collection for URLs entered by a local user."""

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.connectors.rss import entry_time, plain_text

MAX_BODY_BYTES = 1_000_000
MAX_ITEMS_PER_SITE = 3
MAX_REDIRECTS = 3


def normalize_site_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
        if (parts.scheme not in ("https", "http") or not parts.hostname or
                parts.username or parts.password or port not in (None, 80, 443)):
            raise ValueError
        host = parts.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if host.replace(".", "").isdigit():
                raise
        else:
            if not address.is_global:
                raise ValueError
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                           parts.path or "/", parts.query, ""))
    except ValueError:
        raise ValueError("Enter a public HTTP(S) website URL on port 80 or 443") from None


def require_public_host(url: str) -> None:
    parts = urlsplit(normalize_site_url(url))
    host = parts.hostname or ""
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private website addresses are not supported")
    try:
        addresses = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError("Private website addresses are not supported")
    except (socket.gaierror, OSError, ValueError):
        raise ValueError("Website address could not be resolved") from None


@dataclass(frozen=True)
class WebItem:
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    external_id: str | None = None


class WebsiteCollector:
    def fetch(self, url: str) -> tuple[str, bytes, str]:
        """Check every redirect and cap the body; never forward ambient proxy credentials."""
        current = normalize_site_url(url)
        with httpx.Client(timeout=8, trust_env=False, follow_redirects=False,
                          headers={"User-Agent": "DSIH-Research/0.1", "Accept":
                                   "text/html, application/rss+xml, application/atom+xml, application/xml"}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                require_public_host(current)
                try:
                    with client.stream("GET", current) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location:
                                raise ValueError("Website redirect has no destination")
                            current = normalize_site_url(urljoin(current, location))
                            continue
                        if response.status_code >= 400:
                            raise ValueError(f"Website HTTP {response.status_code}")
                        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        if media_type and not any(term in media_type for term in
                                                  ("html", "xml", "rss", "atom", "text/plain")):
                            raise ValueError("Website response is not HTML or RSS/Atom")
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_BODY_BYTES:
                                raise ValueError("Website response exceeds size limit")
                        return normalize_site_url(str(response.url)), bytes(body), media_type
                except httpx.HTTPError:
                    raise ValueError("Website request failed") from None
        raise ValueError("Website redirected too many times")

    def _feed_items(self, body: bytes, base_url: str) -> list[WebItem]:
        parsed = feedparser.parse(body)
        if not parsed.version:
            return []
        result = []
        for entry in parsed.entries[:MAX_ITEMS_PER_SITE]:
            title = str(entry.get("title") or "").strip()
            link = str(entry.get("link") or "").strip()
            if not title or not link:
                continue
            try:
                url = normalize_site_url(urljoin(base_url, link))
                require_public_host(url)
            except ValueError:
                continue
            content = entry.get("content") or []
            body_html = str(content[0].get("value") or "") if content else ""
            result.append(WebItem(title[:300], url,
                                  plain_text(body_html or str(entry.get("summary") or ""))[:4000],
                                  entry_time(entry)))
        return result

    @staticmethod
    def _html_item(body: bytes, url: str) -> WebItem | None:
        soup = BeautifulSoup(body, "html.parser")
        heading = soup.find("h1") or soup.find("title")
        title = heading.get_text(" ", strip=True) if heading else ""
        if not title:
            return None
        main = soup.find("article") or soup.find("main") or soup.body or soup
        return WebItem(title[:300], url, plain_text(str(main))[:4000])

    def collect(self, site_url: str) -> list[WebItem]:
        site_url = normalize_site_url(site_url)
        final_url, body, media_type = self.fetch(site_url)
        feed_items = self._feed_items(body, final_url)
        if feed_items or any(kind in media_type for kind in ("rss", "atom", "xml")):
            return feed_items
        soup = BeautifulSoup(body, "html.parser")
        for link in soup.find_all("link", rel=lambda rel: rel and "alternate" in rel,
                                  href=True):
            if any(kind in (link.get("type") or "") for kind in ("rss", "atom", "xml")):
                try:
                    feed_url = normalize_site_url(urljoin(final_url, link["href"]))
                    feed_url, feed_body, _ = self.fetch(feed_url)
                    feed_items = self._feed_items(feed_body, feed_url)
                    if feed_items:
                        return feed_items
                except ValueError:
                    continue
        links = []
        host = urlsplit(final_url).hostname
        for tag in soup.select("article a[href], h2 a[href], h3 a[href]"):
            try:
                link = normalize_site_url(urljoin(final_url, tag["href"]))
            except ValueError:
                continue
            if urlsplit(link).hostname == host and link != final_url and link not in links:
                links.append(link)
            if len(links) >= MAX_ITEMS_PER_SITE:
                break
        if not links:
            item = self._html_item(body, final_url)
            return [item] if item else []
        items = []
        for link in links:
            try:
                resolved, article_body, _ = self.fetch(link)
                item = self._html_item(article_body, resolved)
                if item:
                    items.append(item)
            except ValueError:
                continue
        if not items:
            raise ValueError("No readable article links")
        return items
