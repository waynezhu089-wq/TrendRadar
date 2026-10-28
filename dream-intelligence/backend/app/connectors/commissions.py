"""Bounded public demand pages. No login, bid, message, or contact-unlocking actions."""
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlsplit
from urllib.request import getproxies

import httpx
from bs4 import BeautifulSoup
from app.research.websites import require_public_host

SOURCES = {
    'sdm': ('AigcSDM', 'https://square.aigcsdm.com/demands'),
    'manju': ('漫剧工场', 'https://www.manjugongchang.com/demand?cat=production'),
    'tahou': ('塔猴', 'https://www.tahou.com/earns/all'),
    # The public search redirects to verification. This readable AI-video detail
    # exposes live related-demand links; discovery is deliberately one hop only.
    'zbj': ('猪八戒', 'https://www.zbj.com/xq/mFH6Vil9ALqQ7GFo.html'),
}
SOURCE_COVERAGE = {
    'sdm': '公开需求列表，每次最多核对 10 条详情。',
    'manju': '公开找承制方列表，每次最多核对 10 条详情。',
    'tahou': '公开商单中心，每次最多核对 10 条详情；仅保存可公开读取的需求。',
    'zbj': '有限发现：公开 AI 视频详情及其相似需求，最多 10 条；搜索入口当前要求验证，并非全站搜索。',
}
MAX_DETAILS = 10
CREATIVE = re.compile(r'AI|AIGC|人工智能', re.I)
MEDIA = re.compile(r'视频|短剧|漫剧|动画|图像|绘图|图片|宣传片|广告片|插画|海报|数字人')
SUPPLIER = re.compile(r'团队承接|承接全流程|我们是.{0,20}团队|可承接[：:]|找甲方|招聘人才|培训招生|课程招生')
OVERSEAS = re.compile(r'海外|欧美市场|香港|澳门|台湾|\boverseas\b', re.I)
MAINLAND = re.compile(r'中国大陆|国内|广东|广州|深圳|北京|上海|浙江|杭州|江苏|南京|苏州|成都|四川|重庆|湖北|武汉|湖南|长沙|福建|厦门|山东|河南|河北|陕西|西安|安徽|天津|抖音|千川|红果')


def fetch_public(url):
    """Only fixed marketplace catalogues/details, via the user's normal system proxy.

    Keep certificate verification enabled; never forward proxy credentials or follow redirects.
    This does not change the generic user-URL collector's network policy.
    """
    parts = urlsplit(url)
    paths = {'square.aigcsdm.com': r'/demands(?:/\d+)?',
        'www.manjugongchang.com': r'/demand(?:/\d+)?',
        'www.tahou.com': r'/(?:earns/all|earn/\d+)',
        'www.zbj.com': r'/xq/[A-Za-z0-9]{16}\.html'}
    if (parts.scheme != 'https' or parts.hostname not in paths or parts.username or parts.password
            or parts.port or not re.fullmatch(paths[parts.hostname], parts.path)
            or parts.query not in ('', 'cat=production')):
        raise ValueError('SOURCE_URL_REJECTED')
    require_public_host(url)
    proxies = getproxies()
    proxy = proxies.get('https') or proxies.get('all')
    if proxy:
        parsed = urlsplit(proxy)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            raise ValueError('SOURCE_PROXY_UNSUPPORTED')
    with httpx.Client(timeout=12, proxy=proxy, trust_env=False, follow_redirects=False,
            headers={'User-Agent': 'DSIH-Opportunities/0.1', 'Accept': 'text/html'}) as client:
        with client.stream('GET', url) as response:
            if response.status_code != 200:
                raise ValueError('SOURCE_HTTP_ERROR')
            kind = response.headers.get('content-type', '').split(';')[0]
            if kind != 'text/html':
                raise ValueError('SOURCE_FORMAT_CHANGED')
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1_000_000:
                    raise ValueError('SOURCE_TOO_LARGE')
            return url, bytes(body), kind


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def date_value(value):
    match = re.search(r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})', value or '')
    if not match:
        return None
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def state(value):
    if any(word in value for word in ('已关闭', '已结束', '停止招募', '已完成', '已定标',
            '已结算', '已签单', '已完结', '选标中', '报名结束', '已取消', '工作中', '交付中', '待结算')):
        return 'CLOSED'
    if any(word in value for word in ('招标中', '招募中', '报名中', '进行中')):
        return 'OPEN'
    return 'UNKNOWN'


def category(title, content):
    value = title + ' ' + content
    if re.search(r'漫剧|短剧|动画', value):
        return '漫剧与动画'
    if re.search(r'视频|宣传片|广告片|数字人', value):
        return '视频与广告'
    return '图片与视觉'


def region_evidence(value):
    match = MAINLAND.search(value)
    if not match:
        return None
    # A textual clue is never a verified identity or company location.
    return value[max(0, match.start()-12):match.end()+25].strip()


@dataclass
class Candidate:
    url: str
    title: str
    description: str = ''
    budget: str | None = None
    deadline: str | None = None
    publisher: str | None = None
    source_status: str = 'UNKNOWN'
    confirmed_on: str | None = None


def candidates(source, body):
    if source in ('tahou', 'zbj'):
        from .commission_marketplaces import marketplace_candidates
        return marketplace_candidates(source, body)
    soup = BeautifulSoup(body, 'html.parser')
    result = []
    pattern = r'/demands/\d+' if source == 'sdm' else r'/demand/\d+'
    seen = set()
    recognized = 0
    for link in soup.select('a[href]'):
        href = link.get('href', '')
        if not re.fullmatch(pattern, href) or href in seen:
            continue
        seen.add(href)
        card = link
        while card and not card.find('h3'):
            card = card.parent
        if not card or card.name in ('body', 'html'):
            continue
        recognized += 1
        title = text(card.find('h3'))
        description = text(card.find('p')) if source == 'manju' else ''
        value = text(card)
        if (OVERSEAS.search(value) or SUPPLIER.search(title+' '+description)
                or source == 'manju' and '找承制方' not in value):
            continue
        fields = {text(dt): text(dt.find_next_sibling('dd')) for dt in card.select('dt')}
        publisher = None
        if source == 'manju':
            publisher_node = card.select_one('div.truncate')
            publisher = text(publisher_node) or None
        confirmed = re.search(r'最近确认\s*(20\d{2}/\d{1,2}/\d{1,2})', value)
        deadline = re.search(r'截止\s*(20\d{2}/\d{1,2}/\d{1,2})', value)
        result.append(Candidate(urljoin(SOURCES[source][1], href), title, description,
            fields.get('预算 / 合作方式'), date_value(deadline.group(1)) if deadline else None,
            publisher, state(value), date_value(confirmed.group(1)) if confirmed else None))
    # An empty catalogue is valid only when the page explicitly says so.
    if not recognized and not re.search(r'共\s*0\s*个需求|暂无需求|暂无相关需求', text(soup)):
        raise ValueError('SOURCE_FORMAT_CHANGED')
    return result[:MAX_DETAILS]


def detail(source, candidate, body):
    if source in ('tahou', 'zbj'):
        from .commission_marketplaces import marketplace_detail
        return marketplace_detail(source, candidate, body)
    soup = BeautifulSoup(body, 'html.parser')
    h1 = soup.find('h1')
    if not h1:
        raise ValueError('DETAIL_FORMAT_CHANGED')
    title = text(h1)
    service = {}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or '')
            if isinstance(data, dict) and data.get('@type') == 'Service':
                service = data
        except (ValueError, TypeError):
            continue
    heading = next((h for h in soup.select('h2,h3') if text(h) in ('需求描述', '需求详情')), None)
    if not heading:
        raise ValueError('DETAIL_FORMAT_CHANGED')
    description = service.get('description')
    if not isinstance(description, str) or not description.strip():
        block = heading.parent
        if text(block) == text(heading):
            block = block.parent
        description = text(block).removeprefix(text(heading)).strip()
    description = description.replace('\\r', '').replace('\\n', '\n')[:5000]
    if not CREATIVE.search(title+' '+description) or not MEDIA.search(title+' '+description):
        return None
    if SUPPLIER.search(title+' '+description) or OVERSEAS.search(title+' '+description):
        return None
    header = text(h1.parent if source == 'manju' else h1.parent.parent)
    published = date_value(str(service.get('datePosted', '')))
    if not published and source == 'sdm':
        m = re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日)\s*发布', header)
        published = date_value(m.group(1)) if m else None
    if not published and source == 'manju':
        # This site's public SSR header uses en-US M/D/YYYY. No relative-date guessing.
        m = re.search(r'发布于\s*(\d{1,2})/(\d{1,2})/(20\d{2})', header)
        if m:
            published = date_value(f'{m[3]}-{m[1]}-{m[2]}')
    budget = candidate.budget
    deadline = candidate.deadline
    publisher = candidate.publisher
    if source == 'sdm':
        for label in soup.find_all(['p', 'div', 'span']):
            if text(label) == '预算' and label.find_next_sibling():
                budget = text(label.find_next_sibling())[:200] or None
            if text(label) == '截止日期' and label.find_next_sibling():
                deadline = date_value(text(label.find_next_sibling()))
        owner = next((h for h in soup.select('h2') if text(h) == '需求方信息'), None)
        publisher = text(owner.parent.find('p')) if owner else None
    evidence = region_evidence(title+' '+(publisher or '')+' '+description)
    return dict(source=source, source_name=SOURCES[source][0], url=candidate.url, title=title[:300],
        description=description, budget=budget, deadline=deadline, publisher=publisher,
        published_on=published, confirmed_on=candidate.confirmed_on,
        source_status=state(header) if state(header) != 'UNKNOWN' else candidate.source_status,
        category=category(title, description), region='MAINLAND_CLUE' if evidence else 'UNKNOWN',
        region_evidence=evidence)


class CommissionConnector:
    def __init__(self, fetch=None):
        self.fetch = fetch or fetch_public

    def collect_source(self, source):
        started = time.monotonic()
        final, body, _ = self.fetch(SOURCES[source][1])
        expected = urlsplit(SOURCES[source][1]).hostname
        if urlsplit(final).hostname != expected:
            raise ValueError('SOURCE_REDIRECTED')
        choices = candidates(source, body)
        rows, errors = [], []
        checked = 0
        for candidate in choices:
            if time.monotonic()-started > 65:
                errors.append('SOURCE_TIME_LIMIT'); break
            checked += 1
            try:
                # The ZBJ discovery entry is already a demand detail, not a list.
                if candidate.url == SOURCES[source][1]:
                    final, detail_body = final, body
                else:
                    final, detail_body, _ = self.fetch(candidate.url)
                if final != candidate.url:
                    raise ValueError('DETAIL_REDIRECTED')
                row = detail(source, candidate, detail_body)
                if row:
                    rows.append(row)
            except Exception:
                errors.append('DETAIL_UNAVAILABLE')
        return rows, {'source': source, 'name': SOURCES[source][0], 'url': SOURCES[source][1],
            'status': 'PARTIAL' if errors else 'OK', 'checked': checked, 'accepted': len(rows),
            'errors': errors, 'coverage': SOURCE_COVERAGE[source]}
