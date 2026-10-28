"""Bounded adapter to a separately installed MediaCrawler, without vendored code."""

import os
import logging
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from uuid import uuid4

from app.db.database import DATA_DIR, ROOT
from .websites import WebItem


class BilibiliUnavailable(Exception): pass
class BilibiliLoginRequired(Exception): pass
class BilibiliBusy(Exception): pass
class BilibiliTimeout(Exception): pass
class BilibiliCollectionFailed(Exception): pass


def is_bilibili_site(url: str) -> bool:
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.hostname in ("www.bilibili.com", "bilibili.com")
            and parts.path in ("", "/") and not parts.query)


# Integration code only: configure the external tool and call its public classes.
# Cap the search response before its detail tasks are created, even if an external
# version rounds the requested count to a full page. Never enter an automatic login.
DRIVER = r'''
import asyncio, sys
import config
from media_platform.bilibili.core import BilibiliCrawler
from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.login import BilibiliLogin
config.PLATFORM = "bili"
config.KEYWORDS = sys.argv[2]
config.CRAWLER_TYPE = "search"
config.BILI_SEARCH_MODE = "normal"
config.START_PAGE = 1
config.CRAWLER_MAX_NOTES_COUNT = 20
config.MAX_CONCURRENCY_NUM = 1
config.CRAWLER_MAX_SLEEP_SEC = 2
config.ENABLE_GET_COMMENTS = config.ENABLE_GET_SUB_COMMENTS = False
config.ENABLE_GET_MEDIA = config.ENABLE_GET_WORDCLOUD = False
config.ENABLE_IP_PROXY = config.ENABLE_CDP_MODE = False
config.SAVE_LOGIN_STATE = True
config.HEADLESS = True
config.COOKIES = ""
config.SAVE_DATA_OPTION = "jsonl"
config.SAVE_DATA_PATH = sys.argv[1]
original_search = BilibiliClient.search_video_by_keyword
async def limited_search(self, *args, **kwargs):
    result = await original_search(self, *args, **kwargs)
    result["result"] = (result.get("result") or [])[:3]
    return result
async def require_owner_login(self):
    raise RuntimeError("DSIH_LOGIN_REQUIRED")
BilibiliClient.search_video_by_keyword = limited_search
BilibiliLogin.begin = require_owner_login
async def run():
    crawler = BilibiliCrawler()
    try:
        await crawler.start()
    finally:
        context = getattr(crawler, "browser_context", None)
        if context:
            try:
                await context.close()
            except Exception:
                pass  # The external crawler can already have closed its context.
asyncio.run(run())
'''


class BilibiliMediaCrawlerCollector:
    def __init__(self, directory: Path | None = None, timeout: int = 240):
        self.directory = Path(directory or os.environ.get("DSIH_MEDIACRAWLER_DIR")
                              or ROOT.parent / ".lab-tools" / "MediaCrawler-main").resolve()
        self.timeout = timeout
        self.received = 0

    def collect(self, site_url: str, topics: list[str]) -> list[WebItem]:
        if not is_bilibili_site(site_url) or not 1 <= len(topics) <= 8:
            raise ValueError("Invalid Bilibili plan")
        if any("," in topic or "，" in topic for topic in topics):
            raise ValueError("Use one topic per line")
        python = self.directory / ".venv" / "Scripts" / "python.exe"
        if not python.is_file() or not (self.directory / "media_platform/bilibili/core.py").is_file():
            raise BilibiliUnavailable()
        import msvcrt
        DATA_DIR.mkdir(exist_ok=True)
        with (DATA_DIR / "bilibili-browser.lock").open("a+b") as lock:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise BilibiliBusy() from None
            try:
                return self._collect(python, topics)
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def _collect(self, python: Path, topics: list[str]) -> list[WebItem]:
        from .mediacrawler import read_bilibili_jsonl, relevant_to_topic
        output = self.directory / "dsih-output" / uuid4().hex
        output.mkdir(parents=True)
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                   "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "COMSPEC", "PATHEXT",
                   "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "USERNAME",
                   "USERDOMAIN", "PLAYWRIGHT_BROWSERS_PATH"}
        env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen([str(python), "-c", DRIVER, str(output), ",".join(topics)],
            cwd=self.directory, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            log, _ = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            process.communicate()
            raise BilibiliTimeout() from None
        if b"DSIH_LOGIN_REQUIRED" in log:
            raise BilibiliLoginRequired()
        if process.returncode:
            kind = next((name for name in ("ModuleNotFoundError", "TargetClosedError",
                "TimeoutError", "DataFetchError", "AttributeError", "PermissionError")
                if name.encode() in log), "EXTERNAL_PROCESS_FAILED")
            module = "pwd" if b"No module named 'pwd'" in log else "unspecified"
            logging.getLogger(__name__).warning("Bilibili external failure: %s, module=%s", kind, module)
            raise BilibiliCollectionFailed()
        files = list((output / "bili/jsonl").glob("search_contents_*.jsonl"))
        if not files:
            if b"No more videos" in log:
                self.received = 0
                return []
            raise BilibiliCollectionFailed()
        rows = []
        invalid = 0
        for file in files:
            parsed, rejected = read_bilibili_jsonl(file)
            rows.extend(parsed)
            invalid += rejected
        if invalid or len(rows) > len(topics) * 3:
            raise BilibiliCollectionFailed()
        self.received = len(rows)
        selected = {row["url"]: row for row in rows if row["keyword"] in topics and
                    relevant_to_topic(row["keyword"], row["title"], row["content"])}
        return [WebItem(row["title"], row["url"], row["content"], row["published_at"])
                for row in selected.values()]
