"""Official SZSE announcement metadata only; no PDF download or text extraction."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx


class UnsupportedMarketError(ValueError):
    pass


@dataclass(frozen=True)
class Announcement:
    external_id: str
    title: str
    url: str
    published_at: datetime | None
    source: str
    raw_json: dict


class MarketAnnouncementProvider(Protocol):
    def fetch_recent(self, symbol: str, market: str, limit: int = 10) -> list[Announcement]: ...


def official_url(url: str) -> str:
    value = url.strip()
    parsed = urlsplit(value)
    hostname = parsed.hostname
    if (parsed.scheme != "https" or not hostname or
            not (hostname == "szse.cn" or hostname.endswith(".szse.cn")) or
            parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Announcement URL is not an official SZSE HTTPS URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def normalize_szse_announcement(row: dict, symbol: str) -> Announcement:
    if not isinstance(row, dict):
        raise ValueError("Invalid SZSE announcement row")
    codes = row.get("secCode")
    if not isinstance(codes, list) or symbol not in codes:
        raise ValueError("SZSE announcement does not match requested symbol")
    title = row.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("SZSE announcement has no title")

    path = row.get("attachPath")
    if isinstance(path, str) and path:
        if path.startswith("//"):
            raise ValueError("Invalid SZSE attachment path")
        candidate = (path if path.startswith("https://") else
                     "https://disc.static.szse.cn/download" + path
                     if path.startswith("/disc/") else "")
    else:
        candidate = row.get("url")
    if not isinstance(candidate, str) or not candidate:
        raise ValueError("SZSE announcement has no official link")
    url = official_url(candidate)

    raw_time = row.get("publishTime")
    published_at = None
    if raw_time:
        if not isinstance(raw_time, str):
            raise ValueError("Invalid SZSE disclosure date")
        published_at = datetime.fromisoformat(raw_time.strip())
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=ZoneInfo("Asia/Shanghai"))

    official_id = row.get("annId")
    if official_id is None or str(official_id).strip() == "":
        official_id = row.get("id")
    if official_id is not None and str(official_id).strip():
        external_id = str(official_id)
    else:
        # The normalized official PDF/detail URL is the stable fallback, never the title.
        external_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return Announcement(external_id=external_id, title=title, url=url,
                        published_at=published_at, source="SZSE", raw_json=row)


class SZSEAnnouncementProvider:
    API_URL = "https://www.szse.cn/api/disc/announcement/annList"
    LIST_URL = "https://www.szse.cn/disclosure/listed/notice/index.html"

    def fetch_recent(self, symbol: str, market: str, limit: int = 10) -> list[Announcement]:
        if market != "SZ":
            raise UnsupportedMarketError(f"SZSE announcements do not support market {market}")
        if not 1 <= limit <= 10:
            raise ValueError("Announcement limit must be between 1 and 10")
        response = httpx.post(
            self.API_URL,
            json={"stock": [symbol], "seDate": [], "channelCode": ["listedNotice_disc"],
                  "pageSize": limit, "pageNum": 1},
            headers={"User-Agent": "Mozilla/5.0",
                     "Referer": self.LIST_URL,
                     "Origin": "https://www.szse.cn",
                     "Accept": "application/json"},
            timeout=15,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError(f"SZSE announcement list returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Invalid SZSE announcement list response")
        rows = payload["data"]
        count = payload.get("announceCount")
        if not rows and count != 0:
            raise ValueError("Empty SZSE page without confirmed zero announcement count")
        announcements = [normalize_szse_announcement(row, symbol) for row in rows[:limit]]
        return sorted(announcements, key=lambda item: item.published_at or datetime.min.replace(
            tzinfo=ZoneInfo("Asia/Shanghai")), reverse=True)
