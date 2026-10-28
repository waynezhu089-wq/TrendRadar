"""Public Tahou/ZBJ adapters. Parse only demand content, never seller offers or contacts."""
import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from .commissions import (Candidate, SOURCES, MAX_DETAILS, CREATIVE, MEDIA, SUPPLIER,
    OVERSEAS, text, state, date_value, category, region_evidence)

SOFTWARE = re.compile(r'(?:软件|系统|小程序|APP|智能体|工具).{0,8}(?:开发|搭建|定制)|(?:开发|搭建).{0,8}(?:软件|系统|小程序|APP|智能体)', re.I)


def structured(soup):
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(tag.string or '')
            if isinstance(value, dict):
                yield value
        except (ValueError, TypeError):
            pass


def local_timestamp(value):
    """The source explicitly displays Beijing local time; never infer relative dates."""
    value = (value or '').strip().replace('/', '-')
    try:
        stamp = datetime.fromisoformat(value)
        return (stamp.replace(tzinfo=timezone(timedelta(hours=8))) if not stamp.tzinfo else stamp).isoformat()
    except (ValueError, TypeError):
        return None


def marketplace_candidates(source, body):
    soup = BeautifulSoup(body, 'html.parser')
    rows, seen = [], set()
    if source == 'tahou':
        for link in soup.select('a.earn-card[href]'):
            href = link['href']
            if not re.fullmatch(r'/earn/\d+', href) or href in seen:
                continue
            seen.add(href)
            value = text(link)
            if OVERSEAS.search(value):
                continue
            title = text(link.select_one('.title'))
            if not title:
                raise ValueError('SOURCE_FORMAT_CHANGED')
            rows.append(Candidate('https://www.tahou.com'+href, title,
                budget=text(link.select_one('.price-value')) or None,
                source_status=state(text(link.select_one('.status')))))
        if not seen and not re.search(r'暂未搜索到商单|暂无商单', text(soup)):
            raise ValueError('SOURCE_FORMAT_CHANGED')
    else:
        # ZBJ full search requires a verification flow. Do not follow it, solve
        # challenges, spoof a crawler, or turn product/service advertisements into leads.
        title = next((text(label.find_next_sibling()) for label in soup.select('.base-info-title')
            if text(label) == '需求标题'), '')
        if not title:
            raise ValueError('SOURCE_FORMAT_CHANGED')
        rows.append(Candidate(SOURCES[source][1], title))
        seen.add(SOURCES[source][1])
        related = next((node for node in soup.find_all(['div','h2','h3']) if text(node) == '类似需求'), None)
        # The exact recommendation card class is verified against the public SSR page.
        for link in soup.select('a[href]'):
            href = link['href']
            if not re.fullmatch(r'https://www\.zbj\.com/xq/[A-Za-z0-9]{16}\.html', href) or href in seen:
                continue
            seen.add(href)
            value = text(link)
            if not value or OVERSEAS.search(value) or SUPPLIER.search(value):
                continue
            # The demand links on this page's related section contain a publication
            # label; seller ads elsewhere link to /fw/ and are never selected.
            if not related or '发布该需求' not in value:
                continue
            rows.append(Candidate(href, value[:300]))
    return rows[:MAX_DETAILS]


def marketplace_detail(source, candidate, body):
    soup = BeautifulSoup(body, 'html.parser')
    published = deadline = deadline_at = delivery_deadline = publisher = None
    budget = candidate.budget
    if source == 'tahou':
        title = text(soup.select_one('.hero-title'))
        heading = next((h for h in soup.select('h3') if text(h) in ('需求描述','商单详情')), None)
        description = text(heading.find_next_sibling('p')) if heading else ''
        tags = text(soup.select_one('.tag-row'))
        fields = {text(row.select_one('.indicator-label')):
            text(row.select_one('.indicator-val,.budget-val,.status-text'))
            for row in soup.select('.indicator-item')}
        budget = fields.get('商单预算') or budget
        deadline = date_value(fields.get('报名截止日期'))
        deadline_at = local_timestamp(fields.get('报名截止日期'))
        delivery_deadline = fields.get('交付截止日期') or None
        raw_status = fields.get('当前状态', '')
        meta = {text(row.select_one('.meta-label')): text(row.select_one('.meta-val')) for row in soup.select('.meta-item')}
        published = date_value(meta.get('发布时间'))
        location = None
        for data in structured(soup):
            if data.get('@type') != 'JobPosting':
                continue
            # hiringOrganization is the platform, not evidence of the actual client.
            address = (data.get('jobLocation') or {}).get('address') or {}
            if isinstance(address, dict) and address.get('addressCountry') == 'CN':
                location = '原站商单地区标注 CN（中国），实际发布方所在地仍待核实'
    else:
        fields = {text(row.select_one('.base-info-title,.detail-info-title')):
            text(row.select_one('.base-info-value,.detail-info-value'))
            for row in soup.select('.base-info-row,.detail-info-item')}
        title, description = fields.get('需求标题',''), fields.get('需求描述','')
        budget = fields.get('预算金额') or None
        # Do not reuse recommendation-card prices, where zero can mean quotation needed.
        if budget in ('--', '￥0', '¥0', '0元'):
            budget = None
        deadline = date_value(fields.get('期望完成日期'))
        delivery_deadline = fields.get('期望完成日期') if deadline else None
        raw_status = text(soup.select_one('.title-label-ing'))
        tags = text(soup.select_one('.title-label-item-list'))
        location = region_evidence(text(soup.select_one('.title-label-region')))
        # This is the demand location, NOT the talent-location filter or footer cities.
        location = '原帖需求地区：'+location if location else None
        for data in structured(soup):
            published = date_value(data.get('pubDate')) or published
        if not published:
            published = date_value(text(soup.select_one('.title-label-box')))
    if not title or not description or not raw_status:
        raise ValueError('DETAIL_FORMAT_CHANGED')
    value = title+' '+tags+' '+description
    if (not CREATIVE.search(value) or not MEDIA.search(value) or SOFTWARE.search(title+' '+tags)
            or SUPPLIER.search(title+' '+description) or OVERSEAS.search(value)):
        return None
    evidence = location or region_evidence(value)
    return dict(source=source, source_name=SOURCES[source][0], url=candidate.url,
        title=title[:300], description=description[:5000], budget=budget, publisher=publisher,
        published_on=published, deadline=deadline, deadline_at=deadline_at,
        deadline_kind='REGISTRATION' if source == 'tahou' else 'DELIVERY',
        delivery_deadline=delivery_deadline, confirmed_on=None,
        source_status=state(raw_status), source_status_text=raw_status[:80],
        category=category(title, tags+' '+description), region='MAINLAND_CLUE' if evidence else 'UNKNOWN',
        region_evidence=evidence)
