import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from app.config import NEWSNOW_API_URL
from .base import BaseConnector, CollectionResult, NormalizedItem

PLATFORMS = {
    "weibo": ("Weibo", "https://weibo.com"),
    "zhihu": ("Zhihu", "https://www.zhihu.com"),
    "bilibili-hot-search": ("Bilibili Hot Search", "https://www.bilibili.com"),
}

def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("Expected an absolute HTTP(S) item URL")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))

class NewsNowConnector(BaseConnector):
    def __init__(self, api_url: str = NEWSNOW_API_URL, timeout: float = 10):
        self.api_url = api_url
        self.timeout = timeout

    def _fetch(self, source: str) -> dict:
        parts = urlsplit(self.api_url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("NEWSNOW_API_URL must be an HTTP(S) URL")
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in ("id", "latest")]
        query.append(("id", source))
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query) + "&latest", ""))
        request = Request(url, headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        })
        with urlopen(request, timeout=self.timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get("status") not in ("success", "cache"):
            raise ValueError("NewsNow returned an unsuccessful response")
        if not isinstance(data.get("items"), list):
            raise ValueError("NewsNow response missing items list")
        return data

    def health(self) -> bool:
        try:
            self._fetch("weibo")
            return True
        except Exception:
            return False

    def normalize(self, source: str, raw: dict) -> NormalizedItem:
        if source not in PLATFORMS:
            raise ValueError("Unsupported NewsNow source")
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Missing item title")
        title = title.strip()
        url = normalize_url(raw.get("url") or "")
        # Source namespace preserves distinct user-visible sources for shared URLs.
        identity = [source, "url", url] if url else [source, "title", title]
        external_id = "newsnow:" + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        return NormalizedItem(source, external_id, title, url, "", None, None, datetime.now(timezone.utc))

    def collect_platform(self, source: str) -> CollectionResult:
        if source not in PLATFORMS:
            raise ValueError('Unsupported NewsNow platform')
        received = 0
        try:
            raw = self._fetch(source)["items"]
            received = len(raw)
            items = [self.normalize(source, item) for item in raw]
            return CollectionResult(source, items, received)
        except Exception as error:
            return CollectionResult(source, [], received, f"{type(error).__name__}: {error}")

    def collect(self) -> list[CollectionResult]:
        return [self.collect_platform(source) for source in PLATFORMS]
