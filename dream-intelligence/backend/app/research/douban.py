"""Read small book/movie review samples in the user's dedicated Chrome session.

No password handling, cookie export, writes to Douban or challenge workarounds.
The optional douban-cli lab tool only exposes long-review abstracts; this adapter
reads the visible original review pages instead.
"""

import errno
import msvcrt
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs, quote, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.db.database import DATA_DIR
from .websites import WebItem

PROFILE_DIR = DATA_DIR / 'douban-browser-profile'
MAX_SUBJECTS = 2
MAX_TOPICS = 2
SHORTS_PER_SUBJECT = 3
LONGS_PER_SUBJECT = 1
MAX_CONTENT = 6000
PAGE_TIMEOUT_MS = 15000
RUN_TIMEOUT_SECONDS = 120
HOSTS = {'www.douban.com', 'douban.com', 'movie.douban.com', 'book.douban.com'}


class DoubanLoginRequired(Exception):
    pass


class DoubanAccessBlocked(Exception):
    pass


class DoubanBrowserUnavailable(Exception):
    pass


class DoubanBusy(Exception):
    pass


class DoubanUnsupportedPage(Exception):
    pass


class DoubanPageUnavailable(Exception):
    pass


class DoubanTimeout(Exception):
    pass


def is_douban_site(value: str) -> bool:
    return (urlsplit(value).hostname or '') in HOSTS


def subject_url(value: str) -> str | None:
    """Only canonical HTTPS book/movie subjects; never follow arbitrary links."""
    try:
        parts = urlsplit(value)
        if (parts.scheme != 'https' or parts.username or parts.password or parts.port
                or parts.hostname not in {'book.douban.com', 'movie.douban.com'}):
            return None
    except ValueError:
        return None
    match = re.fullmatch(r'/subject/(\d+)(?:/(?:comments|reviews))?/?', parts.path)
    return f'https://{parts.hostname}/subject/{match[1]}/' if match else None


def supports_douban_site(value: str) -> bool:
    parts = urlsplit(value)
    return bool(subject_url(value) or (parts.scheme == 'https' and parts.hostname in HOSTS
        and parts.path in ('', '/') and not parts.query and not parts.username
        and not parts.password and parts.port is None))


def publication_time(value: str):
    try:
        stamp = datetime.fromisoformat(value.strip())
        return (stamp if stamp.tzinfo else stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'))).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def text(element) -> str:
    if element is None:
        return ''
    for node in element.select('script, style, .report-comment, .comment-report'):
        node.decompose()
    return ' '.join(element.get_text(' ', strip=True).split())


def search_subjects(html: str, kind: str) -> list[str]:
    results = []
    for anchor in BeautifulSoup(html, 'html.parser').select('.result h3 a[href]'):
        value = urljoin('https://www.douban.com/', anchor['href'])
        parts = urlsplit(value)
        if parts.scheme == 'https' and parts.hostname == 'www.douban.com' and parts.path == '/link2/':
            value = parse_qs(parts.query).get('url', [''])[0]
        url = subject_url(value)
        if url and urlsplit(url).hostname == f'{kind}.douban.com' and url not in results:
            results.append(url)
    return results


def parse_shorts(html: str, subject: str, label: str) -> list[WebItem]:
    items = []
    for card in BeautifulSoup(html, 'html.parser').select('.comment-item'):
        ident = card.get('data-cid', '')
        body = text(card.select_one('.short'))
        if not ident.isdigit() or not body:
            continue
        author = text(card.select_one('.comment-info a')) or '匿名'
        stamp = card.select_one('.comment-time')
        date = publication_time(stamp.get('title') or text(stamp)) if stamp else None
        host = urlsplit(subject).hostname
        items.append(WebItem(f'{label}｜短评 · {author}'[:300],
            f'https://{host}/comment/{ident}/',
            f'豆瓣用户短评；作品：{label}；作者：{author}。\n{body[:MAX_CONTENT]}', date,
            f'douban:{host}:comment:{ident}'))
        if len(items) >= SHORTS_PER_SUBJECT:
            break
    return items


def review_links(html: str, subject: str) -> list[str]:
    host = urlsplit(subject).hostname
    results = []
    for anchor in BeautifulSoup(html, 'html.parser').select('.review-item h2 a[href]'):
        parts = urlsplit(urljoin(subject, anchor['href']))
        try:
            port = parts.port
        except ValueError:
            continue
        if (parts.scheme == 'https' and parts.hostname == host and not parts.username
                and not parts.password and port is None
                and re.fullmatch(r'/review/\d+/', parts.path)):
            url = f'https://{host}{parts.path}'
            if url not in results:
                results.append(url)
    return results[:LONGS_PER_SUBJECT]


def parse_review(html: str, url: str, label: str) -> WebItem:
    soup = BeautifulSoup(html, 'html.parser')
    body = text(soup.select_one('.review-content'))
    heading = text(soup.select_one('h1'))
    if not body or not heading:
        raise DoubanPageUnavailable()
    author = text(soup.select_one('header .main-hd .name, .main-hd .name, .main-hd a[property="v:reviewer"]')) or '未标明'
    stamp = soup.select_one('[property="v:dtreviewed"], .main-hd .main-meta')
    date = publication_time(stamp.get('content') or text(stamp)) if stamp else None
    ident = urlsplit(url).path.strip('/').split('/')[-1]
    return WebItem(f'{label}｜长评 · {heading}'[:300], url,
        f'豆瓣用户长评正文节选（最多{MAX_CONTENT}字）；作品：{label}；作者：{author}。\n{body[:MAX_CONTENT]}',
        date, f'douban:{urlsplit(url).hostname}:review:{ident}')


@contextmanager
def profile_lock(profile: Path):
    """Independent OS lock, unrelated to scheduler or notification state."""
    path = profile.parent / 'douban-browser.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EDEADLK):
                raise DoubanBusy() from None
            raise
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _resource_route(route):
    host = urlsplit(route.request.url).hostname or ''
    if route.request.resource_type in ('image', 'media', 'font') or not (
            host == 'douban.com' or host.endswith('.douban.com') or host.endswith('.doubanio.com')):
        route.abort()
    else:
        route.continue_()


class DoubanBrowserCollector:
    def __init__(self, profile_dir: Path = PROFILE_DIR):
        self.profile_dir = Path(profile_dir)
        self.errors = []
        self.received = 0

    def collect(self, site_url: str, topics: list[str]) -> list[WebItem]:
        self.errors, self.received = [], 0
        if not supports_douban_site(site_url):
            raise DoubanUnsupportedPage()
        if not self.profile_dir.is_dir():
            raise DoubanLoginRequired()
        from playwright.sync_api import Error as BrowserError, sync_playwright
        started = monotonic()
        def navigate(page, url):
            remaining = RUN_TIMEOUT_SECONDS - (monotonic() - started)
            if remaining <= 0:
                raise DoubanTimeout()
            response = page.goto(url, wait_until='domcontentloaded',
                timeout=min(PAGE_TIMEOUT_MS, int(remaining * 1000)))
            if (urlsplit(page.url).hostname == 'sec.douban.com'
                    or response and response.status in (403, 429)
                    or page.locator('iframe[src*="captcha"]').count()):
                raise DoubanAccessBlocked()
            if urlsplit(page.url).hostname == 'accounts.douban.com':
                raise DoubanLoginRequired()
            if not response or response.status >= 400:
                raise DoubanPageUnavailable()
            body = page.locator('body').inner_text(timeout=5000)[:1000]
            if '检测到有异常请求' in body or '安全验证' in body:
                raise DoubanAccessBlocked()

        items = []
        with profile_lock(self.profile_dir):
            try:
                with sync_playwright() as p:
                    context = p.chromium.launch_persistent_context(str(self.profile_dir),
                        channel='chrome', headless=False, accept_downloads=False, timeout=20000)
                    try:
                        context.route('**/*', _resource_route)
                        page = context.pages[0] if context.pages else context.new_page()
                        navigate(page, 'https://www.douban.com/')
                        if not page.locator('a[href*="logout"]').count():
                            raise DoubanLoginRequired()
                        explicit = subject_url(site_url)
                        subjects = [explicit] if explicit else []
                        kinds = ([urlsplit(site_url).hostname.split('.')[0]]
                                 if urlsplit(site_url).hostname in {'movie.douban.com', 'book.douban.com'}
                                 else ['movie', 'book'])
                        if not explicit:
                            for topic in topics[:MAX_TOPICS]:
                                for kind in kinds:
                                    cat = '1002' if kind == 'movie' else '1001'
                                    navigate(page, f'https://www.douban.com/search?cat={cat}&q={quote(topic, safe="")}')
                                    for url in search_subjects(page.content(), kind)[:1]:
                                        if url not in subjects:
                                            subjects.append(url)
                                    if len(subjects) >= MAX_SUBJECTS:
                                        break
                                if len(subjects) >= MAX_SUBJECTS:
                                    break
                        for subject in subjects[:MAX_SUBJECTS]:
                            try:
                                navigate(page, subject + 'comments/')
                                soup = BeautifulSoup(page.content(), 'html.parser')
                                label = text(soup.select_one('h1')).removesuffix('短评').strip() or subject
                                items.extend(parse_shorts(str(soup), subject, label))
                                navigate(page, subject + 'reviews/')
                                links = review_links(page.content(), subject)
                                for url in links:
                                    navigate(page, url)
                                    items.append(parse_review(page.content(), url, label))
                            except (DoubanLoginRequired, DoubanAccessBlocked, DoubanTimeout) as error:
                                self.errors.append(type(error).__name__)
                                break  # Stop further requests after a challenge or lost session.
                            except (BrowserError, DoubanPageUnavailable):
                                self.errors.append('DoubanPageUnavailable')
                        self.received = len(items)
                        return items
                    finally:
                        context.close()
            except BrowserError:
                raise DoubanBrowserUnavailable() from None
