"""Public reset records plus an optional dedicated, user-owned X browser session."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.db.database import DATA_DIR

ACCOUNT = 'thsottiaux'
PROFILE_DIR = DATA_DIR / 'x-browser-profile'
FEED_BASE = 'https://codex-resets.com/api/v1'
CREDIT_URL = 'https://codex-resets.com/'


class ResetFeedUnavailable(Exception): pass
class XLoginRequired(Exception): pass
class XAccessBlocked(Exception): pass
class XBrowserUnavailable(Exception): pass


def aware(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    try:
        stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except ValueError:
        return None


def post_identity(value):
    try:
        parts=urlsplit(value)
        if (parts.scheme!='https' or parts.hostname not in ('x.com','www.x.com','twitter.com','www.twitter.com')
                or parts.username or parts.password or parts.port):return None
        match=re.fullmatch(r'/thsottiaux/status/(\d+)/?',parts.path,re.I)
        return match[1] if match else None
    except ValueError:return None


@dataclass(frozen=True)
class TiboPost:
    external_id: str
    text: str
    source_kind: str
    source_url: str
    feed_signal: str = 'NONE'
    published_at: datetime | None = None
    reported_at: datetime | None = None

    @property
    def url(self):return f'https://x.com/{ACCOUNT}/status/{self.external_id}'


def feed_post(row, signal):
    if not isinstance(row,dict):return None
    source=row.get('source') or {}
    ident=post_identity(source.get('url',''))
    if not ident or source.get('type') not in ('x_post','observed'):return None
    if str(source.get('author',ACCOUNT)).lower()!=ACCOUNT:return None
    body=row.get('text')
    date=aware(row.get('announced_at'))
    if not isinstance(body,str) or not body.strip() or not date:return None
    observed=source['type']=='observed'
    return TiboPost(ident,body.strip()[:10000],
        'community_observed' if observed else 'community_x_post',CREDIT_URL,
        signal,None if observed else date,date)


class ResetFeedCollector:
    def __init__(self, now=None):self.now=now or datetime.now(timezone.utc)

    def get(self,path):
        try:
            response=httpx.get(f'{FEED_BASE}/{path}',timeout=20,follow_redirects=False,
                headers={'User-Agent':'DreamIntelligence/0.1 (Tibo reset subscription)'})
            response.raise_for_status()
            if len(response.content)>1_000_000:raise ValueError()
            body=response.json();generated=aware(body.get('meta',{}).get('generated_at'))
            if not generated or not -timedelta(minutes=5)<=self.now-generated<=timedelta(minutes=15):
                raise ValueError()
            return body['data']
        except Exception:raise ResetFeedUnavailable() from None

    def collect(self):
        status=self.get('status')
        history=self.get('resets?limit=5')
        if not isinstance(status,dict) or not isinstance(history,list):raise ResetFeedUnavailable()
        rows=[]
        for row in history[:5]:
            if value:=feed_post(row,'CONFIRMED'):rows.append(value)
        for key,signal in [('scheduled_reset','SCHEDULED'),('latest_reset','CONFIRMED')]:
            if value:=feed_post(status.get(key),signal):rows.append(value)
        # active_watch, prediction percentages and scheduled_for are deliberately excluded.
        return list({post.external_id:post for post in rows}.values())


def browser_posts(html):
    results=[];seen=set()
    for card in BeautifulSoup(html,'html.parser').select('article[data-testid="tweet"]'):
        author=card.select_one('[data-testid="User-Name"]')
        if author is None or '@'+ACCOUNT not in author.get_text(' ',strip=True).lower():continue
        stamp=card.select_one('a time[datetime]')
        if stamp is None:continue
        anchor=stamp.find_parent('a')
        value=anchor.get('href','')
        ident=post_identity('https://x.com'+value if value.startswith('/') else value)
        body=card.select_one('[data-testid="tweetText"]')
        date=aware(stamp.get('datetime'))
        if not ident or ident in seen or body is None or not date:continue
        text=' '.join(body.get_text(' ',strip=True).split())
        if not text:continue
        seen.add(ident)
        results.append(TiboPost(ident,text[:10000],'x_browser',f'https://x.com/{ACCOUNT}',published_at=date))
        if len(results)>=12:break
    return results


class XBrowserCollector:
    def collect(self):
        if not PROFILE_DIR.is_dir():raise XLoginRequired()
        from playwright.sync_api import Error as BrowserError,sync_playwright
        try:
            with sync_playwright() as p:
                context=p.chromium.launch_persistent_context(str(PROFILE_DIR),channel='chrome',
                    headless=True,accept_downloads=False,timeout=20000)
                try:
                    def route(request):
                        if request.request.resource_type in ('image','media','font'):request.abort()
                        else:request.continue_()
                    context.route('**/*',route)
                    page=context.pages[0] if context.pages else context.new_page()
                    response=page.goto(f'https://x.com/{ACCOUNT}/with_replies',
                        wait_until='domcontentloaded',timeout=20000)
                    if response and response.status in (403,429):raise XAccessBlocked()
                    if response is None or response.status>=400:raise XBrowserUnavailable()
                    try:
                        page.locator('[data-testid="SideNav_AccountSwitcher_Button"]').wait_for(timeout=8000)
                    except BrowserError:raise XLoginRequired() from None
                    try:
                        page.locator('article[data-testid="tweet"]').first.wait_for(timeout=8000)
                    except BrowserError:raise XAccessBlocked() from None
                    return browser_posts(page.content())
                finally:context.close()
        except (XLoginRequired,XAccessBlocked,XBrowserUnavailable):raise
        except BrowserError:raise XBrowserUnavailable() from None
