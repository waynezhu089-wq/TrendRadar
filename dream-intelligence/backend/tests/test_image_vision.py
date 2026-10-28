import base64
import hashlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.db.models import (ResearchPlan, ResearchRun, ResearchImage, ResearchRunImage,
    ResearchImageVisualReport, Analysis, Item, NotificationDelivery)
from app.llm.base import LLMError
from app.llm.openai_compatible import LLMSettings, ConfigurationError
from app.llm.vision import QwenVisionClient, vision_settings
from app.research.image_vision import (Preview, VisionError, analyze_run_images,
    fetch_preview, validate_report)

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII=')
PREVIEW=Preview('data:image/png;base64,'+base64.b64encode(PNG).decode(),hashlib.sha256(PNG).hexdigest(),len(PNG))


def report(ids,readable=True):
    return {'overview':'从可见画面归纳创作线索，关联弱的候选不推荐。','observations':[
        {'image_id':ident,'readable':readable,'description':'一张测试画面','scene':'室内场景','lighting':'侧面光线',
         'colors':['蓝色'],'composition':'主体位于画面一侧','category':'色彩与氛围',
         'fit':'MATCH' if pos==0 else 'NOT_MATCH','purpose_relevance':'测试用途关联','suggestion':'可借鉴侧光层次',
         'uncertainty':'低清预览限制细节判断','watermark':'UNCERTAIN'} for pos,ident in enumerate(ids)],
        'groups':[{'category':'色彩与氛围','summary':'归纳可见的冷色和侧光','key_points':['色彩层次'],
                   'suggested_action':'制作色彩探索草案','image_ids':[ids[0]]}] if readable else []}


class VisionTransportTests(unittest.TestCase):
    def test_request_really_contains_image_bytes_and_safe_usage_only(self):
        client=QwenVisionClient(LLMSettings('https://qwen.example/v1','test-secret','test-qwen'))
        messages=[{'role':'user','content':[{'type':'text','text':'Describe image 1'},
                  {'type':'image_url','image_url':{'url':PREVIEW.data_url}}]}]
        response={'choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}],
                  'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'private':'not exposed'}}
        with patch.object(client.opener,'open',return_value=io.BytesIO(json.dumps(response).encode())) as request:
            result=client.analyze(messages)
        self.assertEqual(result,'{"ok":true}')
        payload=json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['messages'][0]['content'][1]['image_url']['url'],PREVIEW.data_url)
        self.assertFalse(payload['enable_thinking']);self.assertEqual(payload['model'],'test-qwen')
        self.assertEqual(client.last_usage,{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15})
        self.assertNotIn('test-secret',repr(client.settings))

    def test_config_uses_only_explicit_key_reference(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'vision.json'
            path.write_text(json.dumps({'base_url':'https://qwen.example/v1','model':'test-qwen','api_key_env':'TEST_VISION_KEY'}))
            with patch.dict('os.environ',{'TEST_VISION_KEY':'test-only'},clear=True):
                self.assertEqual(vision_settings(path).model,'test-qwen')
            with patch.dict('os.environ',{'VNEXT_QWEN_API_KEY':'not-authorized-by-this-config'},clear=True):
                with self.assertRaises(ConfigurationError):vision_settings(path)
            path.write_text(json.dumps({'base_url':'https://key:secret@qwen.example/v1','model':'test-qwen','api_key_env':'TEST_VISION_KEY'}))
            with patch.dict('os.environ',{'TEST_VISION_KEY':'test-only'},clear=True):
                with self.assertRaises(ConfigurationError):vision_settings(path)

    def response(self,data=PNG,media='image/png',status=200):
        response=MagicMock();response.__enter__.return_value=response
        response.status_code=status;response.headers={'content-type':media}
        response.iter_bytes.return_value=[data]
        return response

    def test_preview_is_bounded_and_bad_types_private_redirects_are_rejected(self):
        client=MagicMock();client.__enter__.return_value=client
        with patch('app.research.image_vision.httpx.Client',return_value=client),patch('app.research.image_vision.require_public_host'):
            client.stream.return_value=self.response()
            self.assertEqual(fetch_preview('https://example.com/preview.png').sha256,PREVIEW.sha256)
            client.stream.return_value=self.response(b'<html>not an image</html>','image/png')
            with self.assertRaises(VisionError):fetch_preview('https://example.com/preview.png')
            client.stream.return_value=self.response()
            with patch('app.research.image_vision.MAX_PREVIEW_BYTES',3):
                with self.assertRaises(VisionError):fetch_preview('https://example.com/preview.png')
            redirect=self.response(status=302);redirect.headers={'location':'http://127.0.0.1/private'}
            client.stream.return_value=redirect;client.stream.reset_mock()
            with self.assertRaises(VisionError):fetch_preview('https://example.com/preview.png')
            self.assertEqual(client.stream.call_count,1)


class ImageVisionTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        with self.sessions() as db,db.begin():
            plan=ResearchPlan(name='视觉参考测试',topics=['城市视觉参考'],websites=['https://film-grab.com/'],
                purpose='为短片寻找可借鉴的光影与构图参考',collection_type='images')
            db.add(plan);db.flush();self.plan_id=plan.id
            run=ResearchRun(plan_id=plan.id,status='COMPLETED',errors=[])
            db.add(run);db.flush();self.run_id=run.id
            self.ids=[]
            for pos in range(3):
                image=ResearchImage(provider='filmgrab',external_id=str(pos),title='Metadata title must not bias vision',
                    source_url='https://film-grab.com/example/',image_url='https://example.com/original.jpg',
                    thumbnail_url=f'https://example.com/preview-{pos}.png',creator='',license='',license_url='',attribution='',tags=[])
                db.add(image);db.flush();self.ids.append(image.id)
                db.add(ResearchRunImage(run_id=run.id,image_id=image.id,position=pos))
        self.model=Mock();self.model.settings=LLMSettings('https://qwen.example/v1','test-secret','test-qwen')
        self.model.last_usage={'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}
        self.model.analyze.return_value=json.dumps(report(self.ids))
        self.fetcher=Mock(return_value=PREVIEW)
        self.db=self.sessions();app.dependency_overrides[get_db]=lambda:self.db
        self.api=TestClient(app)

    def tearDown(self):
        self.api.close();app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def analyze(self):
        return analyze_run_images(self.plan_id,self.run_id,self.sessions,self.model,self.fetcher)

    def test_pixel_report_is_separate_persistent_and_read_does_not_call_models(self):
        result=self.analyze()
        self.assertEqual((result.analyzed_count,result.candidate_count),(3,3))
        self.assertEqual(len(result.groups),1);self.assertEqual(result.groups[0].image_ids,[self.ids[0]])
        messages=self.model.analyze.call_args.args[0]
        content=messages[1]['content']
        self.assertEqual(len([part for part in content if part['type']=='image_url']),3)
        self.assertNotIn('Metadata title',json.dumps(messages))
        self.assertTrue(all('preview-' in call.args[0] for call in self.fetcher.call_args_list))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ResearchImageVisualReport)),1)
            for cls in [Analysis,Item,NotificationDelivery]:self.assertEqual(db.scalar(select(func.count()).select_from(cls)),0)
            self.assertEqual(db.get(ResearchRun,self.run_id).status,'COMPLETED')
        with patch('app.research.image_vision.fetch_preview') as fetch,patch('app.research.image_vision.QwenVisionClient') as model:
            output=self.api.get(f'/api/v1/research-plans/{self.plan_id}/runs').json()[0]
            self.assertEqual(output['visual_analysis']['analyzed_count'],3)
            self.assertTrue(output['visual_analysis']['analyzed_at'].endswith('Z'))
            model.assert_not_called();fetch.assert_not_called()

    def test_identical_images_and_purpose_reuse_saved_report(self):
        first=self.analyze();second=self.analyze()
        self.assertTrue(second.cached);self.assertEqual(first.input_hash,second.input_hash)
        self.model.analyze.assert_called_once()
        with self.sessions() as db,db.begin():db.get(ResearchPlan,self.plan_id).purpose='为另一支短片寻找室内色彩与层次参考'
        third=self.analyze();self.assertFalse(third.cached);self.assertNotEqual(third.input_hash,first.input_hash)
        self.assertEqual(self.model.analyze.call_count,2)

    def test_invalid_citations_or_failed_provider_preserve_previous_report(self):
        previous=self.analyze()
        malformed=report(self.ids);malformed['groups'][0]['image_ids']=[9999]
        for bad in [malformed,report(self.ids[:-1]),report([*self.ids[:-1],self.ids[0]])]:
            with self.assertRaises(VisionError):validate_report(json.dumps(bad),self.ids)
        # Change a preview digest so explicit reanalysis does not hit the cache.
        self.fetcher.return_value=Preview(PREVIEW.data_url,'changed',PREVIEW.size)
        self.model.analyze.return_value=json.dumps(malformed)
        with self.assertRaises(VisionError):self.analyze()
        self.model.analyze.side_effect=LLMError('Provider HTTP 401')
        with self.assertRaises(VisionError) as caught:self.analyze()
        self.assertEqual(caught.exception.code,'VISION_PROVIDER_HTTP_401')
        with self.sessions() as db:self.assertEqual(db.get(ResearchImageVisualReport,self.run_id).input_hash,previous.input_hash)

    def test_preview_failure_keeps_other_images_but_never_marks_failed_one_as_seen(self):
        self.fetcher.side_effect=[PREVIEW,VisionError('VISION_PREVIEW_UNAVAILABLE'),PREVIEW]
        self.model.analyze.return_value=json.dumps(report([self.ids[0],self.ids[2]]))
        result=self.analyze()
        self.assertEqual(result.analyzed_count,2)
        self.assertEqual(result.errors,[{'image_id':self.ids[1],'reason':'VISION_PREVIEW_UNAVAILABLE'}])
        self.assertNotIn(self.ids[1],[row.image_id for row in result.observations])

    def test_unreadable_model_output_is_not_labelled_visual_analysis(self):
        self.model.analyze.return_value=json.dumps(report(self.ids,readable=False))
        with self.assertRaises(VisionError) as caught:self.analyze()
        self.assertEqual(caught.exception.code,'VISION_NOT_OBSERVED')
        with self.sessions() as db:self.assertIsNone(db.get(ResearchImageVisualReport,self.run_id))

    def test_missing_config_fails_before_preview_fetch_or_model(self):
        with patch('app.research.image_vision.vision_settings',side_effect=ConfigurationError('VISION_NOT_CONFIGURED')):
            with self.assertRaises(ConfigurationError):analyze_run_images(self.plan_id,self.run_id,self.sessions,fetcher=self.fetcher)
        self.fetcher.assert_not_called();self.model.analyze.assert_not_called()

    def test_empty_run_and_running_run_are_not_analyzed(self):
        with self.sessions() as db,db.begin():db.get(ResearchRun,self.run_id).status='RUNNING'
        with self.assertRaises(VisionError) as caught:self.analyze()
        self.assertEqual(caught.exception.code,'VISION_RUN_BUSY')
        self.model.analyze.assert_not_called()
        with self.sessions() as db,db.begin():
            db.get(ResearchRun,self.run_id).status='COMPLETED'
            db.query(ResearchRunImage).filter_by(run_id=self.run_id).delete()
        with self.assertRaises(VisionError) as caught:self.analyze()
        self.assertEqual(caught.exception.code,'VISION_NO_IMAGES')
        self.model.analyze.assert_not_called();self.fetcher.assert_not_called()

    def test_api_returns_safe_error_without_private_provider_body(self):
        with patch('app.research.image_vision.analyze_run_images',side_effect=RuntimeError('test-secret private body')):
            response=self.api.post(f'/api/v1/research-plans/{self.plan_id}/runs/{self.run_id}/vision')
        self.assertEqual(response.status_code,502);self.assertEqual(response.json()['detail'],'VISION_FAILED')
        self.assertNotIn('secret',response.text)
