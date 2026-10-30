import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.v1 import daily
from app.db.database import Base, get_db
from app.db.models import Source, Item, Analysis, ResearchPlan, ResearchRun, ResearchRunItem


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        # TestClient's lifespan must never initialize the developer's real database.
        startup = patch('app.main.initialize_database')
        startup.start()
        self.addCleanup(startup.stop)
        self.db = Session(self.engine)
        self.directory = TemporaryDirectory()
        self.cache = patch.object(daily, 'CACHE_DIR', Path(self.directory.name))
        self.cache.start()
        self.now = datetime(2026,10,23,3,tzinfo=timezone.utc)
        self.source = Source(name='公开资讯', type='rss', category='AI')
        self.db.add(self.source); self.db.flush()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.cache.stop(); self.directory.cleanup(); self.db.close(); self.engine.dispose()

    def item(self, title, date, analyzed=True):
        item = Item(source_id=self.source.id, external_id=title, title=title,
            url=f'https://example.com/{title}', content='素材', published_at=date,
            captured_at=self.now)
        self.db.add(item); self.db.flush()
        if analyzed:
            self.db.add(Analysis(item_id=item.id, category='AI', summary='已分析摘要',
                why_it_matters='相关线索', importance=60, novelty=60, credibility=60,
                personal_relevance=60, dreamstream_relevance=60, actionability=60,
                priority=70, tags=[], recommended_action='READ', analyzer_version='test',analyzed_at=self.now))
        self.db.flush()
        return item

    def test_today_includes_newly_collected_old_and_unknown_dates_but_not_raw(self):
        first = self.item('midnight', datetime(2026,10,22,16))
        newest = self.item('newest', datetime(2026,10,23,2))
        yesterday = self.item('old-collected-today', datetime(2026,10,22,15,59))
        unknown = self.item('unknown', None)
        self.item('future', datetime(2026,10,24))
        self.item('raw', datetime(2026,10,23,1), analyzed=False)
        view = daily.build_daily(self.db, now=self.now)
        self.assertEqual([i.id for i in view.topics[0].items], [newest.id, first.id, yesterday.id, unknown.id])
        self.assertEqual(view.start.isoformat(), '2026-10-22T16:00:00+00:00')
        self.assertEqual(view.unknown_dates, 1)
        self.assertIsNone(view.topics[0].items[-1].published_at)
        self.assertEqual(view.topics[0].items[-1].included_at, self.now)

    def test_period_uses_capture_or_analysis_and_excludes_stale_knowledge(self):
        old = datetime(2026,10,20,1)
        stale = self.item('stale', old)
        stale.captured_at = old
        self.db.scalar(select(Analysis).where(Analysis.item_id==stale.id)).analyzed_at = old
        reanalyzed = self.item('old-but-analyzed-today', old)
        reanalyzed.captured_at = old
        self.db.flush()
        today = daily.build_daily(self.db, now=self.now)
        self.assertEqual([i.id for i in today.topics[0].items], [reanalyzed.id])
        week = daily.build_daily(self.db, 7, self.now)
        self.assertEqual({i.id for i in week.topics[0].items}, {stale.id, reanalyzed.id})

    def test_plan_only_includes_analyzed_evidence_not_old_run_overview(self):
        current = self.item('current', datetime(2026,10,23,1), False)
        old = self.item('old', datetime(2026,10,1), False)
        raw = self.item('uncovered', datetime(2026,10,23,2), False)
        plan = ResearchPlan(name='我的视频方向', topics=['视频'], websites=['https://example.com'], purpose='选择适合的工作流')
        self.db.add(plan); self.db.flush()
        run = ResearchRun(plan_id=plan.id, status='COMPLETED', started_at=self.now, finished_at=self.now, summary={
            'overview':'不能冒充今日总结的跨日期结论',
            'findings':[{'item_id':current.id,'insight':'本条有依据的分析'}],
            'sections':[{'item_ids':[current.id,old.id]}]})
        self.db.add(run); self.db.flush()
        for item in (current, old, raw):
            self.db.add(ResearchRunItem(run_id=run.id,item_id=item.id))
        self.db.flush()
        # A newer failed run does not erase the earlier analyzed material.
        self.db.add(ResearchRun(plan_id=plan.id,status='PARTIAL',started_at=self.now,summary=None)); self.db.flush()
        view = daily.build_daily(self.db,now=self.now)
        self.assertEqual(view.topics[0].title, plan.name)
        self.assertEqual([i.id for i in view.topics[0].items], [current.id, old.id])
        self.assertEqual(view.topics[0].items[0].summary, '本条有依据的分析')
        self.assertNotIn('跨日期结论', view.model_dump_json())
        self.assertIsNone(view.analysis)

    def report(self, view):
        return {'overview':['范围内的新线索'], 'topics':[{'topic_id':t.id,
            'summary':'共同变化与目的关联', 'key_points':['证据有限'], 'suggested_action':'查看原文核实',
            'item_ids':[i.id for i in t.items]} for t in view.topics if t.items]}

    def test_explicit_analysis_cache_scope_no_global_analysis_mutation(self):
        self.item('news', datetime(2026,10,23,1))
        view = daily.build_daily(self.db,now=self.now)
        count = self.db.scalar(select(func.count()).select_from(Analysis))
        client = Mock(); client.analyze.return_value = json.dumps(self.report(view),ensure_ascii=False)
        result = daily.analyze_daily(view, client)
        client.analyze.assert_called_once()
        self.assertIsNotNone(result.analysis)
        again = daily.build_daily(self.db,now=self.now)
        self.assertIsNotNone(again.analysis)
        self.assertIsNone(daily.build_daily(self.db,7,self.now).analysis)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Analysis)), count)
        # Same period with a newly arrived item gets its own analysis scope.
        self.item('new-arrival', datetime(2026,10,23,2))
        self.assertIsNone(daily.build_daily(self.db,now=self.now).analysis)

    def test_bad_evidence_rejected_without_cache(self):
        self.item('news', datetime(2026,10,23,1))
        view = daily.build_daily(self.db,now=self.now)
        report = self.report(view); report['topics'][0]['item_ids'] = [99999]
        client = Mock(); client.analyze.return_value=json.dumps(report)
        with self.assertRaises(ValueError): daily.analyze_daily(view, client)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_get_is_read_only_and_empty_analysis_avoids_provider(self):
        app.dependency_overrides[get_db] = lambda:self.db
        with patch.object(daily,'OpenAICompatibleClient') as provider:
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/v1/daily-brief').status_code,200)
                self.assertEqual(client.get('/api/v1/daily-brief?days=1').status_code,200)
                self.assertEqual(client.get('/api/v1/daily-brief?days=7').json()['days'],7)
                self.assertEqual(client.get('/api/v1/daily-brief?days=2').status_code,422)
                for period in ('1','7'):
                    result=client.post(f'/api/v1/daily-brief/analyze?days={period}')
                    self.assertEqual(result.status_code,422)
                    self.assertEqual(result.json()['detail'],'No current analyzed evidence')
            provider.assert_not_called()
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_topic_order_and_preview_bound(self):
        for n in range(16): self.item(f'news-{n}',datetime(2026,10,23,1,n))
        view = daily.build_daily(self.db,now=self.now)
        self.assertEqual(view.topics[0].total,16)
        self.assertEqual(len(view.topics[0].items),12)
        self.assertEqual(view.topics[0].items[0].title,'news-15')

    def test_provider_failure_is_safe_and_lock_released(self):
        self.item('news',datetime(2026,10,23,1))
        view=daily.build_daily(self.db,now=self.now)
        app.dependency_overrides[get_db]=lambda:self.db
        with patch.object(daily,'build_daily',return_value=view), patch.object(daily,'analyze_daily',side_effect=RuntimeError('private data')):
            with TestClient(app) as client:
                result=client.post('/api/v1/daily-brief/analyze')
                self.assertEqual(result.status_code,502)
                self.assertNotIn('private data',result.text)
        self.assertFalse(daily.analysis_lock.locked())

    def test_pending_api_writes_only_real_analysis_then_summary_and_reuses_cache(self):
        raw = self.item('AI workflow raw',datetime(2026,10,23,1),False)
        raw_id = raw.id
        self.db.commit()
        original_build = daily.build_daily
        fixed_now = self.now
        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)
        fake = Mock()
        valid = dict(category='AI',summary='原始资料支持的分析',why_it_matters='可能有帮助',
            importance=60,novelty=60,credibility=60,personal_relevance=60,
            dreamstream_relevance=60,actionability=60,tags=['AI'],recommended_action='READ')
        def answer(messages):
            if 'Evaluate one item' in messages[0]['content']:
                return json.dumps(valid,ensure_ascii=False)
            payload=json.loads(messages[-1]['content'])
            return json.dumps({'overview':['本期收录的线索，原始日期独立标注'],
                'topics':[dict(topic_id=t['id'],summary='有依据的共同变化',key_points=['需要核对原文'],
                    suggested_action='进一步验证',item_ids=[i['id'] for i in t['items']]) for t in payload['topics']]},ensure_ascii=False)
        fake.analyze.side_effect=answer
        app.dependency_overrides[get_db]=lambda:self.db
        def frozen(db,days=1):return original_build(db,days,self.now)
        with patch('app.db.models.datetime',FixedClock), patch.object(daily,'datetime',FixedClock), patch.object(daily,'build_daily',side_effect=frozen), patch.object(daily,'OpenAICompatibleClient',return_value=fake), patch.object(daily.LLMSettings,'from_env',return_value=daily.LLMSettings('https://example.com/v1','test-only','test-model')):
            with TestClient(app) as client:
                preview=client.get('/api/v1/daily-brief').json()
                self.assertEqual(preview['pending_candidates'],1)
                self.assertIsNone(self.db.scalar(select(Analysis).where(Analysis.item_id==raw_id)))
                result=client.post('/api/v1/daily-brief/analyze?include_pending=true')
                self.assertEqual(result.status_code,200,result.text)
                body=result.json()
                self.assertEqual(body['processing']['analyzed'],1)
                self.assertIsNotNone(body['analysis'])
                self.assertEqual(fake.analyze.call_count,2)
                repeated=client.post('/api/v1/daily-brief/analyze?include_pending=true')
                self.assertEqual(repeated.status_code,200)
                self.assertEqual(fake.analyze.call_count,2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Analysis)),1)
        self.assertEqual(self.db.get(Item,raw_id).content,'素材')

    def test_pending_provider_failure_stops_before_daily_summary(self):
        from app.llm.base import LLMError
        # Keep the API's seven-day candidate window aligned with the fixed fixtures.
        fixed_now = self.now
        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now.astimezone(tz) if tz else fixed_now.replace(tzinfo=None)
        self.item('AI raw 1',datetime(2026,10,23,1),False)
        self.item('AI raw 2',datetime(2026,10,23,1),False)
        self.db.commit()
        fake=Mock();fake.analyze.side_effect=LLMError('Provider HTTP 401')
        app.dependency_overrides[get_db]=lambda:self.db
        with patch.object(daily,'datetime',FixedClock), patch.object(daily,'OpenAICompatibleClient',return_value=fake), patch.object(daily.LLMSettings,'from_env',return_value=daily.LLMSettings('https://example.com/v1','test-only','test-model')), patch.object(daily,'analyze_daily') as summary:
            with TestClient(app) as client:
                result=client.post('/api/v1/daily-brief/analyze?include_pending=true')
                self.assertEqual(result.status_code,200,result.text)
                self.assertTrue(result.json()['processing']['provider_unavailable'])
                self.assertTrue(result.json()['notices'])
            fake.analyze.assert_called_once()
            summary.assert_not_called()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Analysis)),0)

    def test_research_reanalysis_time_is_used_without_changing_collection_time(self):
        item=self.item('old research',datetime(2026,10,1),False)
        item.captured_at=datetime(2026,10,1)
        plan=ResearchPlan(name='Study',topics=['AI'],websites=['https://example.com'],purpose='Follow relevant changes')
        self.db.add(plan);self.db.flush()
        run=ResearchRun(plan_id=plan.id,status='COMPLETED',started_at=datetime(2026,10,1),finished_at=datetime(2026,10,1),summary={
            '_analyzed_at':self.now.isoformat(),'sections':[{'item_ids':[item.id]}]})
        self.db.add(run);self.db.flush()
        self.db.add(ResearchRunItem(run_id=run.id,item_id=item.id));self.db.flush()
        view=daily.build_daily(self.db,now=self.now)
        self.assertEqual(view.topics[0].items[0].included_at,self.now)
        self.assertEqual(run.finished_at,datetime(2026,10,1))
