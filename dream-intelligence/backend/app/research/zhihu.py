"""Small, user-initiated Zhihu search collector using its own local Edge profile."""

from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.connectors.rss import plain_text
from app.db.database import DATA_DIR

from .websites import WebItem


PROFILE_DIR = DATA_DIR / "zhihu-browser-profile"
ZHIHU_HOME = "https://www.zhihu.com/"
MAX_ARTICLES_PER_TOPIC = 1
MAX_ARTICLES_PER_RUN = 8
PAGE_TIMEOUT_MS = 15_000


class ZhihuLoginRequired(Exception):
    """The dedicated profile needs its owner to sign in."""


class ZhihuAccessBlocked(Exception):
    """Zhihu refused browser collection; do not try to bypass its restriction."""


class ZhihuBrowserUnavailable(Exception):
    """The dedicated browser could not start or navigate."""


def is_zhihu_search_site(site_url: str) -> bool:
    parts = urlsplit(site_url)
    return (parts.scheme == "https" and parts.hostname in ("zhihu.com", "www.zhihu.com")
            and parts.path in ("", "/", "/search") and not parts.query)


def article_url(value: str) -> str | None:
    """Accept only original Zhihu answers/articles, with stable canonical URLs."""
    try:
        parts = urlsplit(value)
        invalid = parts.scheme != "https" or parts.username or parts.password or parts.port
    except ValueError:
        return None
    if invalid:
        return None
    segments = [part for part in parts.path.split("/") if part]
    if (parts.hostname == "www.zhihu.com" and len(segments) == 4
            and segments[0] == "question" and segments[2] == "answer"
            and segments[1].isdigit() and segments[3].isdigit()):
        return urlunsplit(("https", "www.zhihu.com", "/" + "/".join(segments), "", ""))
    if (parts.hostname == "zhuanlan.zhihu.com" and len(segments) == 2
            and segments[0] == "p" and segments[1].isdigit()):
        return urlunsplit(("https", "zhuanlan.zhihu.com", "/" + "/".join(segments), "", ""))
    return None


def search_article_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    # Only search-result cards: the AI answer panel can also contain citations.
    for anchor in soup.select(".SearchResult-Card a[href], .SearchResult a[href]"):
        link = article_url(urljoin(ZHIHU_HOME, anchor.get("href", "")))
        if link and link not in links:
            links.append(link)
    return links


def parse_article(html: str, url: str) -> WebItem | None:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if heading is None:
        return None
    title = " ".join(heading.get_text(" ", strip=True).split())[:300]
    # Read the destination body. Search-card snippets and Zhihu's generated answer
    # are deliberately never used as source content.
    for selector in (".Post-RichTextContainer", ".Post-RichText", ".RichContent-inner",
                     ".RichText.ztext", "article"):
        body = soup.select_one(selector)
        if body is not None:
            content = plain_text(str(body))[:4000]
            if title and len(content) >= 30:
                return WebItem(title, url, content)
    return None


def _block_large_resources(route):
    if route.request.resource_type in ("image", "media", "font"):
        route.abort()
    else:
        route.continue_()


class ZhihuBrowserCollector:
    def __init__(self, profile_dir: Path = PROFILE_DIR):
        self.profile_dir = Path(profile_dir)

    def collect(self, site_url: str, topics: list[str]) -> list[WebItem]:
        if not is_zhihu_search_site(site_url):
            raise ValueError("Zhihu browser collector supports the Zhihu home/search URL only")
        if not self.profile_dir.exists():
            raise ZhihuLoginRequired()
        from playwright.sync_api import Error as PlaywrightError, sync_playwright

        collected: list[WebItem] = []
        seen: set[str] = set()
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), channel="msedge", headless=False,
                    accept_downloads=False, timeout=PAGE_TIMEOUT_MS)
                try:
                    context.route("**/*", _block_large_resources)
                    page = context.pages[0] if context.pages else context.new_page()
                    page.set_default_timeout(5_000)
                    for topic in topics[:8]:
                        if len(collected) >= MAX_ARTICLES_PER_RUN:
                            break
                        search_url = f"https://www.zhihu.com/search?type=content&q={quote(topic, safe='')}"
                        response = page.goto(search_url, wait_until="domcontentloaded",
                                             timeout=PAGE_TIMEOUT_MS)
                        if response is not None and response.status == 403:
                            raise ZhihuAccessBlocked()
                        if (response is None or response.status >= 400
                                or "signin" in page.url):
                            raise ZhihuLoginRequired()
                        try:
                            page.locator("a[href*='/question/'], a[href*='zhuanlan.zhihu.com/p/']").first.wait_for(timeout=5_000)
                        except PlaywrightError:
                            if "登录" in page.locator("body").inner_text()[:1000]:
                                raise ZhihuLoginRequired() from None
                            continue
                        candidates = search_article_links(page.content())
                        taken = 0
                        for link in candidates:
                            if link in seen:
                                continue
                            if taken >= MAX_ARTICLES_PER_TOPIC:
                                break
                            seen.add(link)
                            response = page.goto(link, wait_until="domcontentloaded",
                                                 timeout=PAGE_TIMEOUT_MS)
                            if response is not None and response.status == 403:
                                raise ZhihuAccessBlocked()
                            if (response is None or response.status >= 400
                                    or "signin" in page.url):
                                raise ZhihuLoginRequired()
                            if article_url(page.url) != link:
                                continue
                            try:
                                page.locator("h1").first.wait_for(timeout=5_000)
                            except PlaywrightError:
                                continue
                            item = parse_article(page.content(), link)
                            if item:
                                collected.append(item)
                                taken += 1
                                break
                    return collected
                finally:
                    context.close()
        except (ZhihuLoginRequired, ZhihuAccessBlocked):
            raise
        except PlaywrightError:
            # Do not persist browser errors: they can include URLs and profile paths.
            raise ZhihuBrowserUnavailable() from None
