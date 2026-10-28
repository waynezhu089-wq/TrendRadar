import json
import unittest
import httpx
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db, initialize_database
from app.db.models import (Analysis, Item, NotificationDelivery, ResearchImage,
    ResearchImageSummary, ResearchPlan, ResearchRun, ResearchRunImage)
from app.main import app
from app.research.images import (ImageDownloadFailed, ImageSourceUnavailable,
    OpenverseImageCollector, download_image, normalize_image, run_image_plan, reanalyze_images,
    collect_candidates, broader_queries)
from app.research.plan_assistant import propose_plan
from app.schemas.plan_assistant import PlanAssistantInput
from app.schemas.research import ResearchPlanInput


def candidate(ident='image-1'):
    return normalize_image({'id':ident,'title':'Misty forest','foreign_landing_url':'https://example.com/photo/1',
        'url':'https://example.com/original.jpg','thumbnail':'https://example.com/thumb.jpg',
        'creator':'Photographer','license':'by','license_url':'https://creativecommons.org/licenses/by/4.0/',
        'width':1920,'height':1080,'tags':[{'name':'forest'}],'attribution':'Author, CC BY 4.0'})


def fake_client(invalid=False):
    client=Mock()
    client.analyze.side_effect=[json.dumps({'queries':['misty forest']}),json.dumps({
        'overview':'根据标签建议作为森林参考，实际构图需看图确认。','limitations':'未查看图片像素。',
        'selections':[{'external_id':'invented' if invalid else 'image-1','reason':'标题与森林题材相关',
                       'usage_notes':'可尝试场景参考，先核对实际画面及许可。'}]})]
    return client


class ImageResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        with self.sessions() as db,db.begin():
            plan=ResearchPlan(name='森林参考',topics=['雾中森林'],websites=['https://openverse.org/'],
                purpose='为奇幻短片的场景设计寻找森林参考图',collection_type='images')
            db.add(plan);db.flush();self.plan_id=plan.id
        self.db=self.sessions();app.dependency_overrides[get_db]=lambda:self.db
        self.api=TestClient(app)

    def tearDown(self):
        self.api.close();app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def collector(self):
        collector=Mock();collector.collect.return_value=[candidate(),candidate('image-2')]
        return collector

    def test_raw_images_dedup_and_remain_outside_intelligence(self):
        for _ in range(2):run_image_plan(self.plan_id,self.sessions,self.collector(),fake_client())
        with self.sessions() as db:
            runs=db.scalars(select(ResearchRun).order_by(ResearchRun.id)).all()
            self.assertEqual([(r.status,r.received,r.matched,r.inserted) for r in runs],
                             [('COMPLETED',2,1,2),('COMPLETED',2,1,0)])
            for model in (Item,Analysis,NotificationDelivery):
                self.assertEqual(db.scalar(select(func.count()).select_from(model)),0)
        response=self.api.get(f'/api/v1/research-plans/{self.plan_id}/runs')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()[0]
        self.assertEqual(len(data['images']),2);self.assertFalse(data['items'])
        self.assertIsNone(data['summary']);self.assertIn('未查看',data['image_summary']['limitations'])
        self.assertTrue(data['images'][0]['recommended']);self.assertNotIn('local_path',str(data))

    def test_bad_model_reference_preserves_candidates_and_previous_analysis(self):
        rid=run_image_plan(self.plan_id,self.sessions,self.collector(),fake_client(invalid=True))
        with self.sessions() as db:
            self.assertEqual(db.get(ResearchRun,rid).status,'SUMMARY_FAILED')
            self.assertEqual(db.scalar(select(func.count()).select_from(ResearchRunImage)),2)
        good=fake_client()  # Skip query planning for saved-data analysis.
        good.analyze();reanalyze_images(self.plan_id,rid,self.sessions,good)
        with self.sessions() as db:previous=db.get(ResearchImageSummary,rid).overview
        bad=fake_client(invalid=True);bad.analyze()
        with self.assertRaises(ValueError):reanalyze_images(self.plan_id,rid,self.sessions,bad)
        with self.sessions() as db:self.assertEqual(db.get(ResearchImageSummary,rid).overview,previous)

    def test_query_provider_error_does_not_retry_model_and_keeps_raw(self):
        model=Mock();model.analyze.side_effect=RuntimeError('private provider body')
        collector=self.collector()
        rid=run_image_plan(self.plan_id,self.sessions,collector,model)
        model.analyze.assert_called_once()
        collector.collect.assert_called_once_with('雾中森林')
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual(run.status,'SUMMARY_FAILED');self.assertEqual(run.inserted,2)
            self.assertNotIn('private',str(run.errors))

    def test_one_failed_source_does_not_repeat_requests(self):
        collector=Mock();collector.collect.side_effect=ImageSourceUnavailable()
        rid=run_image_plan(self.plan_id,self.sessions,collector,fake_client())
        collector.collect.assert_called_once()
        with self.sessions() as db:self.assertEqual(db.get(ResearchRun,rid).status,'FAILED')

    def test_empty_queries_are_broadened_once_and_recorded(self):
        collector=Mock();collector.collect.side_effect=[[],[candidate()]]
        client=fake_client();client.analyze.side_effect=[
            json.dumps({'queries':['misty forest landscape reference']}),
            json.dumps({'overview':'依标题提供森林线索','limitations':'未查看像素。',
                        'selections':[{'external_id':'image-1','reason':'标题相关','usage_notes':'待看图核对。'}]})]
        rid=run_image_plan(self.plan_id,self.sessions,collector,client)
        self.assertEqual([call.args[0] for call in collector.collect.call_args_list],
                         ['misty forest landscape reference','misty forest'])
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual((run.status,run.received,run.inserted),('COMPLETED',1,1))
            report=db.get(ResearchImageSummary,rid)
            self.assertIn('「misty forest landscape reference」：0',report.limitations)
            self.assertIn('「misty forest」：1',report.limitations)
        self.assertEqual(client.analyze.call_count,2)  # No extra model call for broadening.

    def test_empty_results_have_factual_search_report_not_fake_analysis(self):
        collector=Mock();collector.collect.return_value=[]
        rid=run_image_plan(self.plan_id,self.sessions,collector,fake_client())
        response=self.api.get(f'/api/v1/research-plans/{self.plan_id}/runs').json()[0]
        self.assertEqual(response['status'],'NO_MATCHES')
        self.assertEqual(response['image_summary']['kind'],'search')
        self.assertIn('其他网站',response['image_summary']['overview'])
        self.assertIn('misty forest',response['image_summary']['limitations'])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Analysis)),0)
            self.assertEqual(db.get(ResearchRun,rid).errors,[])

    def test_source_timeout_stops_fallback_and_preserves_earlier_candidates(self):
        collector=Mock();collector.collect.side_effect=[[candidate()],ImageSourceUnavailable('IMAGE_SOURCE_TIMEOUT')]
        client=fake_client();client.analyze.side_effect=[
            json.dumps({'queries':['misty forest','cloudy forest']}),
            json.dumps({'overview':'已取得部分候选','limitations':'未查看像素。','selections':[]})]
        rid=run_image_plan(self.plan_id,self.sessions,collector,client)
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual(run.status,'PARTIAL');self.assertEqual(run.inserted,1)
            self.assertEqual(run.errors,[{'website':'openverse.org','reason':'IMAGE_SOURCE_TIMEOUT'}])
        self.assertEqual(collector.collect.call_count,2)

    def test_query_expansion_is_bounded_and_does_not_slice_chinese_sentences(self):
        self.assertEqual(broader_queries(['雾中森林参考图片','misty forest']),[])
        collector=Mock();collector.collect.return_value=[]
        _,_,searches,errors=collect_candidates(collector,[
            'misty forest landscape illustration','ancient Chinese costume illustration'])
        self.assertEqual(len(searches),4);self.assertEqual(errors,[])
        self.assertEqual([query for query,_ in searches][-2:],['misty forest','ancient Chinese'])

    def test_typed_source_failure_is_visible_without_body_or_retries(self):
        for error,reason in [
            (httpx.ReadTimeout('private body'),'IMAGE_SOURCE_TIMEOUT'),
            (httpx.ConnectError('private body'),'IMAGE_SOURCE_NETWORK_ERROR')]:
            with patch('app.research.images.httpx.get',side_effect=error) as fetch:
                with self.assertRaises(ImageSourceUnavailable) as caught:OpenverseImageCollector().collect('forest')
                self.assertEqual(caught.exception.reason,reason);self.assertNotIn('private',str(caught.exception))
                fetch.assert_called_once()
        for status,reason in [(429,'IMAGE_SOURCE_RATE_LIMITED'),(403,'IMAGE_SOURCE_REJECTED')]:
            response=httpx.Response(status,request=httpx.Request('GET','https://api.openverse.org/v1/images/'))
            with patch('app.research.images.httpx.get',return_value=response) as fetch:
                with self.assertRaises(ImageSourceUnavailable) as caught:OpenverseImageCollector().collect('forest')
                self.assertEqual(caught.exception.reason,reason);fetch.assert_called_once()

    def test_read_and_favorite_do_not_fetch_images_or_call_models(self):
        run_image_plan(self.plan_id,self.sessions,self.collector(),fake_client())
        with self.sessions() as db:ident=db.scalar(select(ResearchImage.id))
        with patch('app.research.images.httpx.get') as fetch,patch('app.research.images.OpenAICompatibleClient') as model:
            self.api.get(f'/api/v1/research-plans/{self.plan_id}/runs')
            self.assertTrue(self.api.post(f'/api/v1/research-images/{ident}/favorite').json()['favorite'])
            self.assertFalse(self.api.delete(f'/api/v1/research-images/{ident}/favorite').json()['favorite'])
            fetch.assert_not_called();model.assert_not_called()
        self.assertEqual(self.api.get(f'/api/v1/research-images/{ident}/file').status_code,404)

    def test_favorites_remain_available_after_a_different_run(self):
        run_image_plan(self.plan_id,self.sessions,self.collector(),fake_client())
        with self.sessions() as db:ident=db.scalar(select(ResearchImage.id).order_by(ResearchImage.id))
        self.api.post(f'/api/v1/research-images/{ident}/favorite')
        empty=Mock();empty.collect.return_value=[]
        run_image_plan(self.plan_id,self.sessions,empty,fake_client())
        response=self.api.get(f'/api/v1/research-plans/{self.plan_id}/favorite-images')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([row['id'] for row in response.json()],[ident])
        self.api.delete(f'/api/v1/research-images/{ident}/favorite')
        self.assertEqual(self.api.get(f'/api/v1/research-plans/{self.plan_id}/favorite-images').json(),[])

    def test_image_plan_not_presented_as_daily_news(self):
        response=self.api.get('/api/v1/daily-brief')
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('森林参考',response.text)

    def test_assistant_and_manual_schema_preserve_modes(self):
        plan={'name':'森林参考','topics':['雾中森林'],'websites':['https://openverse.org/'],
              'purpose':'为奇幻短片的场景设计寻找森林参考图','collection_type':'images'}
        model=Mock();model.analyze.return_value=json.dumps({'status':'draft_ready','message':'可先看候选',
            'questions':[],'plan':plan})
        result=propose_plan(PlanAssistantInput(messages=[{'role':'user','content':'为奇幻短片找雾中森林参考图'}]),model)
        self.assertEqual(result.plan.collection_type,'images');self.assertIn('元数据',result.sources[0].scope)
        with self.assertRaises(ValueError):ResearchPlanInput(**(plan|{'websites':['https://invented.example/']}))
        legacy=ResearchPlanInput(**(plan|{'websites':['https://example.com/'],'collection_type':'research'}))
        self.assertEqual(legacy.collection_type,'research')


class ImageDownloadTests(unittest.TestCase):
    def image(self,**extra):
        return SimpleNamespace(id=1,local_path=None,sha256=None,image_url='https://example.com/a.png',
            license='by',license_url='https://creativecommons.org/licenses/by/4.0/',**extra)

    def response(self,content=b'\x89PNG\r\n\x1a\nimage'):
        response=MagicMock();response.__enter__.return_value=response;response.status_code=200
        response.headers={'content-type':'image/png'};response.iter_bytes.return_value=[content]
        return response

    def test_download_signature_size_hash_and_existing_file(self):
        with TemporaryDirectory() as folder:
            client=MagicMock();client.__enter__.return_value=client
            client.stream.return_value=self.response()
            with patch('app.research.images.httpx.Client',return_value=client),patch('app.research.images.require_public_host'):
                path,digest=download_image(self.image(),Path(folder))
                self.assertEqual(path.suffix,'.png');self.assertEqual(len(digest),64)
                image=self.image();image.local_path=str(path);image.sha256=digest
                self.assertEqual(download_image(image,Path(folder)),(path,digest))
                self.assertEqual(client.stream.call_count,1)

    def test_private_redirect_rejected_and_partial_files_removed(self):
        client=MagicMock();client.__enter__.return_value=client
        redirect=self.response();redirect.status_code=302;redirect.headers={'location':'http://127.0.0.1/private'}
        client.stream.return_value=redirect
        with TemporaryDirectory() as folder,patch('app.research.images.httpx.Client',return_value=client),patch(
                'app.research.images.require_public_host'):
            with self.assertRaises(ImageDownloadFailed):download_image(self.image(),Path(folder))
            self.assertFalse(list(Path(folder).iterdir()))
            self.assertEqual(client.stream.call_count,1)
        for response in (self.response(b'<html>not image</html>'),self.response(b'\x89PNG\r\n\x1a\n' + b'x'*50)):
            client.stream.return_value=response
            with TemporaryDirectory() as folder,patch('app.research.images.httpx.Client',return_value=client),patch(
                    'app.research.images.require_public_host'),patch('app.research.images.MAX_DOWNLOAD_BYTES',20):
                with self.assertRaises(ImageDownloadFailed):download_image(self.image(),Path(folder))
                self.assertFalse(list(Path(folder).iterdir()))

    def test_source_errors_are_sanitized_and_normalization_rejects_private_links(self):
        raw={'id':'1','title':'<script>bad</script>Forest','foreign_landing_url':'http://127.0.0.1/',
             'url':'https://example.com/a.jpg','thumbnail':'https://example.com/t.jpg'}
        self.assertIsNone(normalize_image(raw))
        with patch('app.research.images.httpx.get',side_effect=ValueError('secret body')):
            with self.assertRaises(ImageSourceUnavailable) as caught:OpenverseImageCollector().collect('forest')
            self.assertNotIn('secret',str(caught.exception))


class ImageMigrationTests(unittest.TestCase):
    def test_legacy_plans_preserved_and_migration_idempotent(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'old.db';engine=create_engine(f'sqlite:///{path.as_posix()}')
            Base.metadata.create_all(engine)
            with engine.begin() as db:
                db.execute(text("INSERT INTO research_plans (id,name,topics,websites,purpose,enabled,created_at) VALUES (7,'Existing','[]','[]','Existing research',1,'2026-10-23')"))
                db.execute(text('ALTER TABLE research_plans DROP COLUMN collection_type'))
            initialize_database(engine);initialize_database(engine)
            with engine.connect() as db:
                self.assertEqual(db.execute(text('SELECT id,name,collection_type FROM research_plans')).fetchall(),[(7,'Existing','research')])
            self.assertEqual(len(list(Path(folder).glob('*.bak'))),1)
            engine.dispose()
