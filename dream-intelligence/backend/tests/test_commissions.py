import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.connectors.commissions import Candidate, candidates, detail, CommissionConnector, fetch_public
from app.db.database import Base, get_db
from app.db.models import CommissionLead, CommissionCollection, Item, Analysis, NotificationDelivery
from app.research.commissions import collect_leads, list_leads, lead_output
from app.main import app

LIST = '''<a href="/demands/98"><h3>寻高质量AI教育宣传片制作团队</h3><span>招标中</span></a>'''
DETAIL = '''<main><div><div><h1>寻高质量AI教育宣传片制作团队</h1><span>招标中</span></div>
<span>2026年10月8日 发布</span></div><div><p>预算</p><p>¥5,000—¥20,000</p></div>
<div><p>截止日期</p><p>2026年11月10日</p></div><section><h2>需求描述</h2><p>需要AI视频，提供剧本与IP，接受有偿试稿。</p></section>
<aside><h2>需求方信息</h2><p>广东***</p></aside></main>'''


def card(ident, title, description, kind='找承制方', extra=''):
    return f'''<article><div class="truncate">发布用户</div><div><h3>{title}</h3><span>{kind} 招募中 {extra}</span></div>
    <p>{description}</p><dl><div><dt>预算 / 合作方式</dt><dd>面议</dd></div></dl>
    <span>最近确认 2026/10/6</span><span>截止 2026/10/18</span><a href="/demand/{ident}">查看需求</a></article>'''


class ParserTests(unittest.TestCase):
    def test_fixed_transport_rejects_arbitrary_urls_and_proxy_credentials(self):
        for url in ('http://square.aigcsdm.com/demands','https://127.0.0.1/demands',
                'https://square.aigcsdm.com/login','https://square.aigcsdm.com/demands?token=secret'):
            with self.assertRaises(ValueError):fetch_public(url)
        with patch('app.connectors.commissions.require_public_host'),patch('app.connectors.commissions.getproxies',return_value={'https':'http://user:secret@proxy.example:8080'}):
            with self.assertRaises(ValueError):fetch_public('https://square.aigcsdm.com/demands')

    def test_sdm_extracts_only_actual_fields_and_public_masked_publisher(self):
        row = detail('sdm', candidates('sdm', LIST)[0], DETAIL)
        self.assertEqual((row['budget'], row['deadline'], row['published_on']),
            ('¥5,000—¥20,000', '2026-11-10', '2026-10-08'))
        self.assertEqual(row['publisher'], '广东***')
        self.assertEqual(row['region'], 'MAINLAND_CLUE')
        self.assertIn('广东', row['region_evidence'])
        self.assertEqual(row['category'], '视频与广告')

    def test_missing_fields_stay_unknown_instead_of_inventing_dates_or_budget(self):
        html = '<h1>寻找AI绘图</h1><section><h2>需求描述</h2><p>需要AI图片制作</p></section>'
        row = detail('sdm', Candidate('https://square.aigcsdm.com/demands/1', '标题'), html)
        for field in ('budget', 'deadline', 'published_on', 'publisher', 'region_evidence'):
            self.assertIsNone(row[field])
        self.assertEqual(row['region'], 'UNKNOWN')
        self.assertEqual(row['source_status'], 'UNKNOWN')

    def test_excludes_suppliers_recruitment_overseas_and_non_ai_content(self):
        html = card(1,'AI漫剧团队承接全流程','可承接：分镜制作')
        html += card(2,'AI视频导演','需要作品','招聘人才')
        html += card(3,'Overseas AI video','AI短剧制作')
        html += card(4,'找AI绘图师','广州公司委托图片制作')
        rows = candidates('manju',html)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].budget,'面议')
        html = '<h1>找软件外包</h1><section><h3>需求详情</h3><p>AI代码自动化</p></section>'
        self.assertIsNone(detail('manju',rows[0],html))

    def test_format_change_is_a_failure_not_an_empty_success(self):
        for html in ('<h1>请登录</h1>', '<a href="/demands/98">新版页面</a>'):
            with self.assertRaises(ValueError): candidates('sdm',html)
        self.assertEqual(candidates('sdm','<p>共 0 个需求</p>'),[])

    def test_links_are_bounded_and_cannot_fetch_arbitrary_hosts(self):
        html = LIST+'<a href="https://evil.example/demands/3"><h3>AI视频</h3></a>'
        self.assertEqual(len(candidates('sdm',html)),1)
        html = ''.join(LIST.replace('/98',f'/{i}') for i in range(30))
        self.assertEqual(len(candidates('sdm',html)),10)

    def test_closed_and_deadline_are_independent_from_listing_badges(self):
        row = detail('sdm', candidates('sdm',LIST)[0],DETAIL.replace('招标中','已关闭'))
        self.assertEqual(row['source_status'],'CLOSED')
        entity = CommissionLead(id=1,url=row['url'],payload=row,
            captured_at=datetime.now(timezone.utc),checked_at=datetime.now(timezone.utc))
        self.assertEqual(lead_output(entity,date(2026,11,11))['status'],'EXPIRED')

    def test_detail_failure_isolated_and_redirects_rejected(self):
        fetch=Mock(side_effect=[('https://square.aigcsdm.com/demands',LIST.encode(),'text/html'),ValueError()])
        rows,report=CommissionConnector(fetch).collect_source('sdm')
        self.assertEqual(rows,[]);self.assertEqual(report['status'],'PARTIAL')
        self.assertEqual(report['errors'],['DETAIL_UNAVAILABLE'])
        fetch=Mock(return_value=('https://example.com/',b'', 'text/html'))
        with self.assertRaises(ValueError):CommissionConnector(fetch).collect_source('sdm')

    def test_manju_publication_uses_header_not_last_confirmation(self):
        row=Candidate('https://www.manjugongchang.com/demand/357','title',confirmed_on='2026-10-15')
        html='<div><h1>AI漫剧制作需求</h1><span>找承制方 招募中 发布于 10/6/2026</span></div><section><h3>需求详情</h3><p>需要AI漫剧制作</p></section>'
        result=detail('manju',row,html)
        self.assertEqual(result['published_on'],'2026-10-06')
        self.assertEqual(result['confirmed_on'],'2026-10-15')


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(app)
        self.row=detail('sdm',candidates('sdm',LIST)[0],DETAIL)

    def tearDown(self):
        app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def connector(self):
        connector=Mock()
        connector.collect_source.side_effect=lambda source:([self.row],dict(source=source,name=source,url='https://example.com',status='OK',checked=1,accepted=1,errors=[])) if source=='sdm' else ([],dict(source=source,name=source,url='https://example.com',status='OK',checked=0,accepted=0,errors=[]))
        return connector

    def test_repeated_collection_updates_status_without_duplicate_or_fake_analysis(self):
        first=collect_leads(self.db,self.connector())
        self.row=dict(self.row,source_status='CLOSED')
        second=collect_leads(self.db,self.connector())
        self.assertEqual(first['latest']['inserted'],1)
        self.assertEqual((second['latest']['inserted'],second['latest']['updated']),(0,1))
        self.assertEqual(second['leads'][0]['source_status'],'CLOSED')
        self.assertEqual(len(second['leads']),1)
        for model in (Item,Analysis,NotificationDelivery):
            self.assertEqual(self.db.scalar(select(func.count()).select_from(model)),0)

    def test_one_source_failure_keeps_other_and_previous_records(self):
        connector=self.connector();original=connector.collect_source.side_effect
        def fetch(source):
            if source=='manju':raise ValueError('private error detail')
            return original(source)
        connector.collect_source.side_effect=fetch
        result=collect_leads(self.db,connector)
        self.assertEqual(result['latest']['status'],'PARTIAL')
        self.assertEqual(len(result['leads']),1)
        self.assertNotIn('private error',str(result))

    def test_read_api_never_collects_and_busy_lock_stops_post(self):
        with patch('app.api.v1.commissions.collect_leads') as collect:
            self.assertEqual(self.client.get('/api/v1/commissions').status_code,200)
            collect.assert_not_called()
            with patch('app.api.v1.commissions.manual_run_lock') as lock:
                lock.acquire.return_value=False
                self.assertEqual(self.client.post('/api/v1/commissions/collect').status_code,409)
                collect.assert_not_called()

    def test_list_sorts_publication_not_capture_and_preserves_unknown(self):
        for i,published in enumerate(('2026-10-05',None,'2026-10-23')):
            self.db.add(CommissionLead(url=f'https://example.com/{i}',payload=dict(self.row,published_on=published)))
        self.db.commit()
        self.assertEqual([r['published_on'] for r in list_leads(self.db)['leads']],['2026-10-23','2026-10-05',None])

if __name__=='__main__':unittest.main()
