"""Shared source catalog, declarative adapters and immutable per-run search evidence."""
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlsplit

import httpx
from sqlalchemy import select

from app.db.models import (SourceConnection, ResearchPlan, ResearchSourceReport, ResearchRunItem, Item, Source)
from app.schemas.source_connections import SourceBinding, SourceDefinition, SourceConnectionOutput
from .websites import WebItem, WebsiteCollector, normalize_site_url, require_public_host


GITHUB_TEMPLATE = SourceDefinition(
    name='GitHub 项目搜索', site_url='https://github.com/',
    endpoint='https://api.github.com/search/repositories',
    description='搜索公开仓库，按 star 或更新时间排序。排名仅覆盖所填检索式；star 是采集时快照，不代表质量或最新发布。',
    auth_env='GITHUB_TOKEN', query_param='q', query_suffix='is:public', items_path='items',
    field_map={'id':'id', 'title':'full_name', 'url':'html_url', 'content':'description',
               'published_at':'created_at', 'stars':'stargazers_count', 'updated_at':'updated_at'},
    params={'order':'desc', 'page':'1'}, sort_values=['stars','updated'], default_sort='stars', limit_param='per_page')

RSS_TEMPLATE = SourceDefinition(name='公共 RSS 来源', site_url='https://example.com/',
    adapter='rss', endpoint='https://example.com/feed.xml', query_param='', sort_param='', limit_param='',
    description='读取公开 RSS/Atom，按话题字面匹配；继承现有网页采集上限，每次最多三条。')

JSON_TEMPLATE = SourceDefinition(name='自定义 JSON API', site_url='https://example.com/',
    endpoint='https://example.com/api/search', description='按接口文档配置检索参数与返回字段。',
    field_map={'id':'id','title':'title','url':'url','content':'description'})


def connection_output(row):
    definition = SourceDefinition.model_validate(row.definition)
    present = bool(definition.auth_env and os.environ.get(definition.auth_env, '').strip())
    return SourceConnectionOutput(**definition.model_dump(), id=row.id,
        credential_present=present, ready=definition.enabled and (not definition.auth_required or present))


def configured_catalog(db):
    # Do not send endpoint details, credentials or environment names to the model.
    result = []
    for row in db.scalars(select(SourceConnection).order_by(SourceConnection.id)):
        source = connection_output(row)
        result.append({'connection_id':row.id, 'name':source.name, 'site_url':source.site_url,
            'scope':source.description, 'adapter':source.adapter, 'enabled':source.enabled, 'ready':source.ready,
            'sort_values':source.sort_values, 'default_sort':source.default_sort, 'max_results':source.max_results})
    return result


def validate_bindings(db, bindings):
    for binding in bindings:
        row = db.get(SourceConnection, binding.connection_id)
        if row is None:
            raise ValueError('SOURCE_NOT_FOUND')
        definition = SourceDefinition.model_validate(row.definition)
        if not definition.enabled:
            raise ValueError('SOURCE_DISABLED')
        if binding.limit > definition.max_results:
            raise ValueError('SOURCE_LIMIT_INVALID')
        if binding.sort and binding.sort not in definition.sort_values:
            raise ValueError('SOURCE_SORT_INVALID')


def collect_plan_sources(plan_id, run_id, topics, sessions, collector_factory=None):
    """A configuration is snapshotted once; failures never fall back to another website."""
    with sessions() as db:
        bindings = [SourceBinding.model_validate(row) for row in db.get(ResearchPlan,plan_id).source_bindings]
        definitions = {row.connection_id:db.get(SourceConnection,row.connection_id).definition for row in bindings}
    received = matched = inserted = 0
    reports, errors, stopped_hosts = [], [], set()
    for binding in bindings:
        definition = SourceDefinition.model_validate(definitions[binding.connection_id])
        worker = collector_factory() if collector_factory else ConfiguredSourceCollector()
        try:
            host = urlsplit(definition.endpoint).hostname
            if host in stopped_hosts:
                raise SourceCollectionError('SOURCE_ACCESS_STOPPED')
            batch = worker.collect(binding.connection_id,definition,binding,topics)
            report = batch.report
            site_inserted = 0
            with sessions() as db, db.begin():
                source = db.scalar(select(Source).where(Source.type=='custom_web',Source.url==definition.site_url))
                if source is None:
                    source = Source(name=definition.name,type='custom_web',url=definition.site_url,category='USER_RESEARCH',enabled=True)
                    db.add(source);db.flush()
                for index,page in enumerate(batch.items):
                    ident = page.external_id or f'configured:{binding.connection_id}:'+hashlib.sha256(page.url.encode()).hexdigest()
                    item = db.scalar(select(Item).where(Item.external_id==ident))
                    if item is None:
                        item = Item(source_id=source.id,external_id=ident,title=page.title,url=page.url,content=page.content,
                                    published_at=page.published_at,author=None)
                        db.add(item);db.flush();site_inserted += 1
                    if not db.scalar(select(ResearchRunItem.id).where(ResearchRunItem.run_id==run_id,ResearchRunItem.item_id==item.id)):
                        db.add(ResearchRunItem(run_id=run_id,item_id=item.id))
                    report['results'][index]['item_id'] = item.id
                    report['results'][index]['rank'] = index+1
            received += report['received']; matched += len(batch.items); inserted += site_inserted
        except Exception as error:
            code = error.code if isinstance(error,SourceCollectionError) else 'SOURCE_COLLECTION_FAILED'
            if code in ('SOURCE_ACCESS_DENIED','SOURCE_RATE_LIMITED'):
                stopped_hosts.add(urlsplit(definition.endpoint).hostname)
            report = worker.report or {'connection_id':binding.connection_id,'name':definition.name,
                'site_url':definition.site_url,'query':binding.query or ' '.join(topics),
                'sort':binding.sort or definition.default_sort,'limit':binding.limit,'results':[]}
            report.update(status=code)
            for snapshot in report.get('results',[]):
                snapshot.pop('item_id',None)
            report['selected'] = 0
            received += report.get('received',0)
            errors.append({'website':definition.name,'reason':code})
        reports.append(report)
    if reports:
        with sessions() as db, db.begin():
            db.add(ResearchSourceReport(run_id=run_id,reports=reports))
    return received, matched, inserted, errors, reports


def snapshots_from_reports(reports):
    return {row['item_id']:{**row,'observed_at':report.get('observed_at'),'sort':report.get('sort'),'source_name':report['name']}
            for report in reports for row in report.get('results',[]) if 'item_id' in row}


def dotted(value, path):
    for part in path.split('.') if path else []:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


class SourceCollectionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class SourceBatch:
    items: list[WebItem]
    report: dict


class ConfiguredSourceCollector:
    def __init__(self, transport=None):
        self.transport = transport
        self.report = {}

    def collect(self, connection_id: int, definition: SourceDefinition, binding: SourceBinding, topics):
        query = ' '.join(filter(None,[binding.query or ' '.join(topics),definition.query_suffix]))
        if len(query) > 256:
            raise SourceCollectionError('SOURCE_QUERY_TOO_LONG')
        limit = min(binding.limit, definition.max_results)
        order = binding.sort or definition.default_sort
        self.report = {'connection_id':connection_id, 'name':definition.name, 'site_url':definition.site_url,
            'adapter':definition.adapter, 'query':query, 'sort':order, 'limit':limit,
            'observed_at':datetime.now(timezone.utc).isoformat(), 'status':'PENDING',
            'scope':definition.description, 'received':0, 'selected':0, 'incomplete':False, 'results':[]}
        if not definition.enabled:
            raise SourceCollectionError('SOURCE_DISABLED')
        if definition.adapter == 'rss':
            pages = WebsiteCollector().collect(definition.endpoint)
            self.report['received'] = len(pages)
            terms = [binding.query] if binding.query else topics
            pages = [page for page in pages if any(topic.casefold() in (page.title+' '+page.content).casefold()
                                                   for topic in terms)][:limit]
            return self.finish(pages)
        headers = {'Accept':'application/json', 'User-Agent':'DSIH-Configured-Sources/1.0'}
        key = os.environ.get(definition.auth_env, '').strip() if definition.auth_env else ''
        if definition.auth_required and not key:
            raise SourceCollectionError('SOURCE_AUTH_MISSING')
        if key:
            headers['Authorization'] = 'Bearer ' + key
        params = dict(definition.params)
        if definition.query_param:
            params[definition.query_param] = query
        if order and definition.sort_param:
            params[definition.sort_param] = order
        if definition.limit_param:
            params[definition.limit_param] = str(limit)
        try:
            require_public_host(definition.endpoint)
            with httpx.Client(timeout=12, follow_redirects=False, trust_env=False, transport=self.transport) as client:
                with client.stream('GET', definition.endpoint, params=params, headers=headers) as response:
                    if response.status_code in (401,403):
                        raise SourceCollectionError('SOURCE_ACCESS_DENIED')
                    if response.status_code == 429:
                        raise SourceCollectionError('SOURCE_RATE_LIMITED')
                    if 300 <= response.status_code < 400:
                        raise SourceCollectionError('SOURCE_REDIRECT_REJECTED')
                    if response.status_code != 200:
                        raise SourceCollectionError('SOURCE_HTTP_FAILED')
                    if 'json' not in response.headers.get('content-type','').lower():
                        raise SourceCollectionError('SOURCE_FORMAT_CHANGED')
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 1_000_000:
                            raise SourceCollectionError('SOURCE_RESPONSE_TOO_LARGE')
            payload = json.loads(body)
            rows = dotted(payload, definition.items_path)
            if not isinstance(rows, list):
                raise SourceCollectionError('SOURCE_FORMAT_CHANGED')
            self.report['received'] = len(rows)
            self.report['incomplete'] = isinstance(payload, dict) and payload.get('incomplete_results') is True
            pages = []
            for row in rows[:limit]:
                page, snapshot = self.normalize(connection_id, definition, row)
                if page and page.external_id not in {value.external_id for value in pages}:
                    pages.append(page)
                    self.report['results'].append(snapshot)
            if rows and not pages:
                raise SourceCollectionError('SOURCE_FORMAT_CHANGED')
            if len(pages) < min(limit,len(rows)):
                self.report['incomplete'] = True
            return self.finish(pages)
        except SourceCollectionError:
            raise
        except httpx.TimeoutException:
            raise SourceCollectionError('SOURCE_TIMEOUT') from None
        except httpx.HTTPError:
            raise SourceCollectionError('SOURCE_NETWORK_FAILED') from None
        except Exception:
            raise SourceCollectionError('SOURCE_FORMAT_OR_ADDRESS_INVALID') from None

    def finish(self, pages):
        self.report['selected'] = len(pages)
        self.report['status'] = 'COMPLETED'
        if not self.report['results']:
            self.report['results'] = [{'title':page.title,'url':page.url,'content':page.content,
                'published_at':page.published_at.isoformat() if page.published_at else None} for page in pages]
        return SourceBatch(pages, self.report)

    @staticmethod
    def normalize(connection_id, definition, row):
        mapped = {key:dotted(row,path) if path else None for key,path in definition.field_map.items()}
        identity, title = mapped.get('id'), mapped.get('title')
        if not isinstance(identity,(str,int)) or isinstance(identity,bool) or not isinstance(title,str) or not title.strip():
            return None, None
        url = mapped.get('url') or (definition.url_prefix.rstrip('/')+'/'+quote(str(identity),safe='/') if definition.url_prefix else '')
        try:
            url = normalize_site_url(url)
            if any(name.lower()=='key' or any(term in name.lower() for term in ('token','secret','password','api_key','apikey','access_key'))
                   for name,_ in parse_qsl(urlsplit(url).query)):
                return None, None
        except (ValueError, AttributeError):
            return None, None
        content = mapped.get('content') if isinstance(mapped.get('content'),str) else ''
        published = None
        if isinstance(mapped.get('published_at'),str):
            try:
                published = datetime.fromisoformat(mapped['published_at'].replace('Z','+00:00'))
                if not published.tzinfo:published = None
            except ValueError:pass
        external_id = f'configured:{connection_id}:'+hashlib.sha256(str(identity).encode()).hexdigest()
        page = WebItem(title[:300], url, content[:4000], published, external_id)
        snapshot = {'external_id':external_id,'title':page.title,'url':page.url,'content':page.content,
                    'published_at':published.isoformat() if published else None}
        if type(mapped.get('stars')) is int and mapped['stars'] >= 0:
            snapshot['stars'] = mapped['stars']
        if isinstance(mapped.get('updated_at'),str):
            snapshot['updated_at'] = mapped['updated_at'][:40]
        return page, snapshot
