import json
import os
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.connectors.youtube import YouTubeConnector,YouTubeError,normalize,search_query,diversified_selection
from dataclasses import replace
from app.db.database import Base,get_db
from app.db.models import ResearchPlan,ResearchRun,ResearchVideo,VideoSchedule,Item,Analysis,NotificationDelivery
from app.main import app
from app.research.videos import run_video_plan,list_videos,organize
from app.research.video_schedule import run_due_video_plans
from app.schemas.research import ResearchPlanInput

NOW=datetime(2026,10,24,tzinfo=timezone.utc)
ROW={'id':{'videoId':'abcdefghijk'},'snippet':{'title':'Cat &amp; dog','description':'Public description',
    'publishedAt':'2026-10-23T00:00:00Z','channelTitle':'Public channel'}}

class ConnectorTests(unittest.TestCase):
    def test_normalization_stable_id_canonical_preview_and_bad_records(self):
        row=normalize(ROW)
        self.assertEqual(row.title,'Cat & dog');self.assertEqual(row.external_id,'abcdefghijk')
        self.assertTrue(row.published_at.tzinfo);self.assertEqual(normalize(ROW),row)
        for bad in [{},dict(ROW,id={'videoId':'https://evil.local'}),dict(ROW,snippet={})]:self.assertIsNone(normalize(bad))

    def test_search_bounds_dedup_and_secret_header(self):
        response=Mock(status_code=200,is_redirect=False,content=b'{}');response.json.return_value={'items':[ROW,ROW]}
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-secret'}),patch('app.connectors.youtube.httpx.Client') as factory:
            client=factory.return_value.__enter__.return_value;client.get.return_value=response
            rows,errors=YouTubeConnector().collect(['funny animals','cats'],NOW)
        self.assertEqual((len(rows),errors),(1,[]));self.assertEqual(client.get.call_count,2)
        call=client.get.call_args
        self.assertEqual(call.kwargs['params']['maxResults'],10);self.assertNotIn('key',call.kwargs['params'])
        self.assertEqual(call.kwargs['headers']['X-Goog-Api-Key'],'test-secret')

    def test_bilingual_gloss_is_separated_but_chinese_searches_preserved(self):
        self.assertEqual(search_query('animals helping each other 动物互助'),'animals helping each other')
        self.assertEqual(search_query('animal rescue 动物救援真实记录'),'animal rescue')
        self.assertEqual(search_query('动物互助'),'动物互助')
        self.assertEqual(search_query('ComfyUI 教程'),'ComfyUI 教程')

    def test_channel_cap_uses_stable_id_not_display_name_and_balances_topics(self):
        base=normalize(ROW)
        batch1=[replace(base,external_id=str(i),channel='Renamed '+str(i),channel_id='same') for i in range(10)]
        batch2=[replace(base,external_id='other'+str(i),channel='Other',channel_id='other'+str(i)) for i in range(10)]
        result=diversified_selection([batch1,batch2])
        self.assertEqual(len(result),12);self.assertEqual(sum(row.channel_id=='same' for row in result),2)
        self.assertEqual(result[1].external_id,'other0')
        self.assertEqual(len({row.external_id for row in diversified_selection([batch1,batch1])}),2)

    def test_search_report_records_actual_queries_and_deduplicates_gloss_variants(self):
        response=Mock(status_code=200,is_redirect=False,content=b'{}');response.json.return_value={'items':[ROW]}
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-only'}),patch('app.connectors.youtube.httpx.Client') as factory:
            client=factory.return_value.__enter__.return_value;client.get.return_value=response
            connector=YouTubeConnector();connector.collect(['animal rescue 动物救援','animal rescue 救助'],NOW)
        client.get.assert_called_once();report=connector.search_report
        self.assertEqual(report['queries'][0]['query'],'animal rescue');self.assertEqual(report['candidate_channel_count'],1)
        self.assertEqual(report['selected_channel_count'],1)

    def test_permission_failure_stops_remaining_topics(self):
        response=Mock(status_code=403,is_redirect=False,text='private response')
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-secret'}),patch('app.connectors.youtube.httpx.Client') as factory:
            client=factory.return_value.__enter__.return_value;client.get.return_value=response
            rows,errors=YouTubeConnector().collect(['one','two'],NOW)
        self.assertEqual(rows,[]);self.assertEqual(errors[0]['reason'],'YOUTUBE_HTTP_403');client.get.assert_called_once()

    def test_missing_configuration_does_not_send(self):
        with patch.dict(os.environ,{},clear=True),patch('app.connectors.youtube.httpx.Client') as client:
            with self.assertRaises(YouTubeError):YouTubeConnector().collect(['cats'])
        client.assert_not_called()

class VideoTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        with self.sessions() as db,db.begin():
            plan=ResearchPlan(name='Video test',topics=['funny animals'],purpose='寻找趣味动物视频作为故事创作灵感',
                websites=['https://www.youtube.com/'],collection_type='videos');db.add(plan);db.flush();self.plan=plan.id
        self.connector=Mock();self.connector.collect.return_value=([normalize(ROW)],[])
        self.client=Mock();self.client.analyze.return_value=json.dumps({'videos':[{'id':'abcdefghijk','title_zh':'猫与狗',
            'summary_zh':'标题提到猫与狗，可作为互动题材线索，未观看视频。','category':'动物趣事'}]})
        self.db=self.sessions();app.dependency_overrides[get_db]=lambda:self.db;self.api=TestClient(app)

    def tearDown(self):
        self.api.close();app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def run_video(self):return run_video_plan(self.plan,self.sessions,self.connector,self.client,NOW)

    def test_two_runs_dedup_translation_reuse_and_intelligence_isolation(self):
        first=self.run_video();second=self.run_video()
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ResearchVideo)),1)
            self.assertEqual(db.get(ResearchRun,first).inserted,1);self.assertEqual(db.get(ResearchRun,second).inserted,0)
            rows=list_videos(db,self.plan);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title_zh'],'猫与狗')
            for cls in [Item,Analysis,NotificationDelivery]:self.assertEqual(db.scalar(select(func.count()).select_from(cls)),0)
        self.client.analyze.assert_called_once()

    def test_bad_translation_keeps_raw_without_fake_chinese(self):
        self.client.analyze.return_value='{"videos":[]}'
        ident=self.run_video()
        with self.sessions() as db:
            self.assertEqual(db.get(ResearchRun,ident).status,'PARTIAL');self.assertIsNone(list_videos(db,self.plan)[0]['summary_zh'])

    def test_actual_search_provenance_is_saved_and_read_without_external_calls(self):
        self.connector.search_report={'queries':[{'topic':'animal rescue 动物救援','query':'animal rescue','order':'relevance','returned':1,'status':'OK'}],
            'candidate_count':1,'candidate_channel_count':1,'selected_count':1,'selected_channel_count':1,'max_per_channel':2,'limit':12}
        self.run_video()
        with patch('app.connectors.youtube.YouTubeConnector.collect') as collector:
            output=self.api.get(f'/api/v1/research-plans/{self.plan}/runs').json()[0]
            self.assertEqual(output['video_search'],self.connector.search_report);collector.assert_not_called()

    def test_exact_translation_citations_and_allowed_categories(self):
        for output in [{'videos':[]},{'videos':[{'id':'fabricated'}]}, {'videos':[{'id':'abcdefghijk','title_zh':'猫','summary_zh':'简介','category':'invented'}]}]:
            self.client.analyze.return_value=json.dumps(output)
            with self.assertRaises(ValueError):organize([normalize(ROW)],['cats'],'creative purpose',self.client)

    def test_source_failure_and_partial_success_are_distinct_from_no_matches(self):
        self.connector.collect.return_value=([],[{'website':'YouTube','reason':'YOUTUBE_HTTP_403'}]);ident=self.run_video()
        with self.sessions() as db:self.assertEqual(db.get(ResearchRun,ident).status,'FAILED')
        self.client.analyze.assert_not_called()
        self.connector.collect.return_value=([normalize(ROW)],[{'website':'YouTube','reason':'YOUTUBE_REQUEST_FAILED'}]);ident=self.run_video()
        with self.sessions() as db:self.assertEqual((db.get(ResearchRun,ident).status,len(list_videos(db,self.plan))),('PARTIAL',1))

    def test_lease_blocks_overlapping_manual_and_scheduled_runs(self):
        with self.sessions() as db,db.begin():db.add(VideoSchedule(plan_id=self.plan,lease_until=NOW+timedelta(minutes=10)))
        with self.assertRaises(RuntimeError):self.run_video()
        self.connector.collect.assert_not_called();self.client.analyze.assert_not_called()

    def test_missing_key_api_creates_no_run_and_refuses_enabling_schedule(self):
        with patch.dict(os.environ,{},clear=True):
            response=self.api.post(f'/api/v1/research-plans/{self.plan}/run')
            self.assertEqual(response.status_code,409);self.assertEqual(response.json()['detail'],'YOUTUBE_NOT_CONFIGURED')
            self.assertEqual(self.api.post(f'/api/v1/research-plans/{self.plan}/video-schedule',json={'enabled':True,'interval_minutes':120}).status_code,409)
        with self.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(ResearchRun)),0)

    def test_schedule_save_and_get_do_not_run_business_jobs(self):
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-key'}),patch('app.research.videos.run_video_plan') as runner:
            response=self.api.post(f'/api/v1/research-plans/{self.plan}/video-schedule',json={'enabled':True,'interval_minutes':120})
            self.assertEqual(response.status_code,200);self.assertTrue(response.json()['enabled']);self.assertEqual(datetime.fromisoformat(response.json()['next_run_at']).utcoffset(),timedelta(0))
            self.assertEqual(self.api.get(f'/api/v1/research-plans/{self.plan}/video-schedule').status_code,200);runner.assert_not_called()
        self.assertEqual(self.api.post(f'/api/v1/research-plans/{self.plan}/video-schedule',json={'enabled':False,'interval_minutes':1}).status_code,422)

    def test_favorites_survive_runs_and_published_time_has_timezone(self):
        self.run_video()
        with self.sessions() as db:video=db.scalar(select(ResearchVideo)).id
        url=f'/api/v1/research-plans/{self.plan}/videos/{video}/favorite'
        self.assertEqual(self.api.post(url).status_code,200);self.assertEqual(self.api.post(url).status_code,200)
        self.run_video();rows=self.api.get(f'/api/v1/research-plans/{self.plan}/videos?favorites=true').json()
        self.assertEqual(len(rows),1);self.assertTrue(rows[0]['favorite']);self.assertEqual(datetime.fromisoformat(rows[0]['published_at']).utcoffset(),timedelta(0))
        self.api.delete(url);self.assertEqual(self.api.get(f'/api/v1/research-plans/{self.plan}/videos?favorites=true').json(),[])

    def test_due_plans_exclude_disabled_future_and_leased_and_isolate_failures(self):
        with self.sessions() as db,db.begin():
            for pos in range(4):
                plan=ResearchPlan(name=str(pos),topics=['test'],purpose='test purpose',websites=['https://www.youtube.com/'],collection_type='videos')
                db.add(plan);db.flush();db.add(VideoSchedule(plan_id=plan.id,enabled=pos!=1,
                    next_run_at=NOW+timedelta(minutes=10) if pos==2 else NOW-timedelta(minutes=1),lease_until=NOW+timedelta(minutes=3) if pos==3 else None))
            db.add(VideoSchedule(plan_id=self.plan,enabled=True,next_run_at=NOW-timedelta(minutes=1)))
        runner=Mock(side_effect=[RuntimeError('private'),123])
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-key'}):result=run_due_video_plans(self.sessions,runner,NOW)
        self.assertEqual(runner.call_count,2);self.assertEqual(len(result['runs']),2);self.assertNotIn('private',json.dumps(result))

    def test_plan_validation_only_supports_youtube(self):
        values={'name':'name','topics':['animals'],'purpose':'find inspiration for future videos','websites':['www.youtube.com'],'collection_type':'videos'}
        self.assertEqual(ResearchPlanInput(**values).websites,['https://www.youtube.com/'])
        with self.assertRaises(ValueError):ResearchPlanInput(**(values|{'websites':['https://example.com/']}))

    def test_future_schedule_is_claimed_once_and_advanced_without_duplicate_collection(self):
        with self.sessions() as db,db.begin():db.add(VideoSchedule(plan_id=self.plan,enabled=True,interval_minutes=120,next_run_at=NOW-timedelta(minutes=1)))
        def runner(ident,**kwargs):return run_video_plan(ident,connector=self.connector,client=self.client,**kwargs)
        with patch.dict(os.environ,{'DSIH_YOUTUBE_API_KEY':'test-only'}):
            first=run_due_video_plans(self.sessions,runner,NOW);second=run_due_video_plans(self.sessions,runner,NOW)
        self.assertEqual(len(first['runs']),1);self.assertEqual(second['runs'],[]);self.connector.collect.assert_called_once()

    def test_favorite_cannot_reference_video_from_another_plan(self):
        self.run_video()
        with self.sessions() as db,db.begin():
            video=db.scalar(select(ResearchVideo)).id
            plan=ResearchPlan(name='Unrelated',topics=['travel'],purpose='find travel inspiration',websites=['https://www.youtube.com/'],collection_type='videos')
            db.add(plan);db.flush();other=plan.id
        self.assertEqual(self.api.post(f'/api/v1/research-plans/{other}/videos/{video}/favorite').status_code,404)
        self.assertEqual(self.api.get(f'/api/v1/research-plans/{other}/videos').json(),[])

    def test_assistant_video_draft_uses_integrated_source_and_does_not_run_collector(self):
        from app.research.plan_assistant import propose_plan
        from app.schemas.plan_assistant import PlanAssistantInput
        model=Mock();model.analyze.return_value=json.dumps({'status':'draft_ready','message':'视频灵感草案','questions':[],
            'plan':{'name':'Animal clips','topics':['funny animals'],'websites':['https://www.youtube.com/'],
                'purpose':'find funny animal inspiration for future videos','collection_type':'videos'},'deferred_sources':[]})
        with patch('app.connectors.youtube.YouTubeConnector.collect') as collect:
            result=propose_plan(PlanAssistantInput(messages=[{'role':'user','content':'从 YouTube 收集有趣动物视频，寻找创作灵感'}]),model)
            collect.assert_not_called()
        self.assertEqual(result.plan.collection_type,'videos');self.assertIn('YouTube',result.sources[0].name)
