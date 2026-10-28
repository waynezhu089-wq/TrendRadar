import json
import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.connectors.newsnow import NewsNowConnector
from app.db.database import Base
from app.db.models import Item, Source, Analysis, ResearchPlan, ResearchRun, ResearchRunItem
from app.llm.base import LLMError
from app.research.collection import run_research_plan
from app.research.websites import WebItem
from app.research.weibo import (WeiboHotlistCollector, WeiboHotlistUnavailable,
    WeiboTopicSelectionFailed, is_weibo_hot_site, select_weibo_topics)


LOGIN_URL = 'https://weibo.com/newlogin?tabtype=weibo&url=https://weibo.com/'


def connector():
    value = NewsNowConnector()
    value._fetch = Mock(return_value={'status':'success', 'items':[
        {'title':title, 'url':f'https://s.weibo.com/weibo?q=example{index}'}
        for index,title in enumerate(['学校食堂管理引讨论','年轻人讨论婚姻登记',
                                      '某男团新海报','AI视频模型更新'],1)]})
    return value


class PurposeClient:
    def __init__(self):
        self.calls = []

    def analyze(self, messages):
        payload = json.loads(messages[1]['content'])
        self.calls.append(payload)
        if payload['items'] and 'index' in payload['items'][0]:
            return json.dumps({'selected_indices':[1,2]})
        items = payload['items']
        return json.dumps({'overview':'学校与婚恋公共讨论可作为选题线索，尚未核实。',
            'findings':[{'item_id':items[0]['item_id'],'insight':'标题涉及公共讨论',
                'purpose_relevance':'可作为视频号选题线索','suggested_action':'阅读原帖核实'}],
            'sections':[{'category':'教育与成长' if index==0 else '情感与生活',
                'summary':'单条热榜标题，证据有限','key_points':['未阅读原帖'],
                'suggested_action':'先核对原始来源','item_ids':[item['item_id']]}
                for index,item in enumerate(items)],
            'limitations':'仅依据热榜标题和链接，不代表事实核查或完整报道。'},ensure_ascii=False)


class WeiboResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db, db.begin():
            plan=ResearchPlan(name='网络热点',topics=['社会话题','男女情感','教育话题'],
                websites=[LOGIN_URL],purpose='寻找社会热点，为以后的视频号寻找素材')
            db.add(plan);db.flush();self.pid=plan.id

    def tearDown(self):
        self.engine.dispose()

    def test_login_url_routes_only_to_weibo_public_api(self):
        transport=connector()
        collector=WeiboHotlistCollector(transport)
        pages=collector.collect(LOGIN_URL)
        transport._fetch.assert_called_once_with('weibo')
        self.assertEqual(collector.received,4)
        self.assertTrue(pages[0].external_id.startswith('newsnow:'))
        self.assertIsNone(pages[0].published_at)
        for site in ('https://weibo.com/',LOGIN_URL,'https://s.weibo.com/top/summary'):
            self.assertTrue(is_weibo_hot_site(site))
        for site in ('https://weibo.com.evil.example/newlogin','https://weibo.com/123/456','https://example.com/'):
            self.assertFalse(is_weibo_hot_site(site))
        with self.assertRaises(ValueError):transport.collect_platform('unknown')

    def test_semantic_topic_selection_not_literal_match_and_dedup_raw_boundary(self):
        transport=connector();client=PurposeClient()
        first=run_research_plan(self.pid,self.sessions,client=client,
                               weibo_collector=WeiboHotlistCollector(transport))
        second=run_research_plan(self.pid,self.sessions,client=client,
                                weibo_collector=WeiboHotlistCollector(transport))
        self.assertEqual(client.calls[0]['topics'],['社会话题','男女情感','教育话题'])
        self.assertIn('未读取原帖',client.calls[0]['evidence_scope'])
        with self.sessions() as db:
            a,b=db.get(ResearchRun,first),db.get(ResearchRun,second)
            self.assertEqual((a.status,a.received,a.matched,a.inserted),('COMPLETED',4,2,4))
            self.assertEqual((b.matched,b.inserted),(2,0))
            self.assertEqual(db.scalar(select(func.count()).select_from(Item)),4)
            self.assertEqual(db.scalar(select(func.count()).select_from(Source)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Analysis)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(ResearchRunItem)),4)
            self.assertEqual({s['category'] for s in a.summary['sections']},{'教育与成长','情感与生活'})
            self.assertTrue(all(item.external_id.startswith('newsnow:') for item in db.scalars(select(Item))))
        self.assertTrue(all('微博来自 NewsNow' in payload['evidence_scope'] for payload in client.calls if 'item_count' in payload))

    def test_provider_failure_preserves_all_raw_candidates_and_reports_failure(self):
        fake=Mock();fake.analyze.side_effect=LLMError('Provider HTTP 401')
        rid=run_research_plan(self.pid,self.sessions,client=fake,
                             weibo_collector=WeiboHotlistCollector(connector()))
        fake.analyze.assert_called_once()
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual(run.status,'FAILED')
            self.assertEqual(run.errors[0]['reason'],'WeiboTopicSelectionFailed')
            self.assertEqual(db.scalar(select(func.count()).select_from(Item)),4)
            self.assertEqual(db.scalar(select(func.count()).select_from(Analysis)),0)
            self.assertIsNone(run.summary)

    def test_bad_selection_is_bounded_and_invalid_references_rejected(self):
        pages=[WebItem('Title','https://example.com/a','')]
        for invalid in ([2],[1,1],['1'],[0]):
            fake=Mock();fake.analyze.return_value=json.dumps({'selected_indices':invalid})
            with self.assertRaises(WeiboTopicSelectionFailed):select_weibo_topics(pages,['教育'],'Find material',fake)
            self.assertEqual(fake.analyze.call_count,2)
        fake=Mock();fake.analyze.return_value='{"selected_indices":[]}'
        self.assertEqual(select_weibo_topics(pages,['教育'],'Find material',fake),[])
        self.assertEqual(select_weibo_topics([],['教育'],'Find material',fake),[])
        self.assertEqual(fake.analyze.call_count,1)

    def test_one_malformed_selection_can_repair_without_another_fetch(self):
        fake=Mock();fake.analyze.side_effect=['bad JSON','{"selected_indices":[1]}']
        pages=[WebItem('食堂议题','https://example.com/a','')]
        self.assertEqual(select_weibo_topics(pages,['教育话题'],'Find material',fake),pages)
        self.assertEqual(fake.analyze.call_count,2)

    def test_hotlist_is_bounded_to_thirty_titles(self):
        transport=connector()
        raw=transport._fetch.return_value['items']
        transport._fetch.return_value={'status':'success','items':raw*10}
        collector=WeiboHotlistCollector(transport)
        self.assertEqual(len(collector.collect(LOGIN_URL)),30)
        self.assertEqual(len(collector.batch.items),30)

    def test_hotlist_failure_does_not_block_another_website(self):
        with self.sessions() as db,db.begin():
            plan=db.get(ResearchPlan,self.pid)
            plan.topics=['教育']
            plan.websites=[LOGIN_URL,'https://example.com/']
        transport=connector();transport._fetch.side_effect=RuntimeError('private error text')
        other=Mock();other.collect.return_value=[WebItem('教育政策观察','https://example.com/1','公开摘录')]
        rid=run_research_plan(self.pid,self.sessions,collector=other,client=PurposeClient(),
                             weibo_collector=WeiboHotlistCollector(transport))
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual(run.status,'PARTIAL')
            self.assertEqual(run.matched,1)
            self.assertEqual(run.errors,[{'website':'weibo.com','reason':'WeiboHotlistUnavailable'}])
            self.assertNotIn('private error text',str(run.errors))
