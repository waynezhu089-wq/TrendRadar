import json
import unittest
from unittest.mock import Mock, patch

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import Base, get_db
from app.db.models import ResearchPlan, ResearchRun, ResearchImage, Analysis, Item, NotificationDelivery
from app.research.filmgrab import FilmGrabImageCollector, film_links, gallery_images
from app.research.images import ImageSourceUnavailable, run_image_plan, reanalyze_images
from app.research.plan_assistant import propose_plan
from app.schemas.plan_assistant import PlanAssistantInput
from app.schemas.research import ResearchPlanInput
from test_image_research import candidate

PAGE='https://film-grab.com/2020/01/01/example/'
SEARCH=f'<h2 class="entry-title"><a href="{PAGE}">Example</a></h2>'
GALLERY='''<h1 class="entry-title">Example Film</h1><div class="entry-content">
<p>Director: Example Director</p><p>Director of Photography: Example D.P.</p><p>Year: 2020</p>
<a class="bwg_lightbox" href="https://film-grab.com/wp-content/uploads/one.jpg?bwg=1"><img src="https://film-grab.com/thumb-one.jpg"/></a>
<a class="bwg_lightbox" href="https://film-grab.com/wp-content/uploads/two.jpg"><img src="https://film-grab.com/thumb-two.jpg"/></a>
<a class="bwg_lightbox" href="https://film-grab.com/wp-content/uploads/three.jpg"><img src="https://film-grab.com/thumb-three.jpg"/></a>
</div>'''


def selection(rows):
    return json.dumps({'overview':'基于影片信息，建议进一步查看本片的视觉表达；单帧尚未看图核验。',
        'limitations':'参考预览授权待确认。', 'selections':[{'external_id':rows[0].external_id,
        'reason':'本片信息提供了进一步探索的线索，未查看该帧。','usage_notes':'打开原站看图核对。'}]})


class FilmGrabParserTests(unittest.TestCase):
    def test_only_real_same_site_film_links_are_followed(self):
        html=SEARCH+f'<h2 class="entry-title"><a href="{PAGE}">duplicate</a></h2>'+'''
        <h2 class="entry-title"><a href="https://evil.example/2020/01/01/film/">Bad</a></h2>
        <h2 class="entry-title"><a href="http://127.0.0.1/2020/01/01/film/">Private</a></h2>
        <h2 class="entry-title"><a href="https://film-grab.com/about/">About</a></h2>'''
        self.assertEqual(film_links(html),[PAGE])

    def test_gallery_preserves_source_identity_credit_and_unknown_license(self):
        rows=gallery_images(GALLERY,PAGE)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0].provider,'filmgrab');self.assertEqual(rows[0].license,'')
        self.assertEqual(rows[0].source_url,PAGE)
        self.assertIn('Example D.P.',rows[0].creator)
        # Tracking/cache changes cannot create a new identity for the same frame.
        self.assertEqual(rows[0].external_id,gallery_images(GALLERY.replace('bwg=1','bwg=2'),PAGE)[0].external_id)
        self.assertEqual(len({row.external_id for row in rows}),3)

    def test_split_colon_credits_and_explicit_rights_notice_are_retained(self):
        html=GALLERY.replace('Director: Example Director','<span>Director</span>: Example Director')
        html=html.replace('</div>','<p>Images are not permitted for commercial use.</p></div>')
        row=gallery_images(html,PAGE)[0]
        self.assertIn('Director: Example Director',row.creator)
        self.assertIn('not permitted for commercial use',row.attribution)

    def test_collector_caches_gallery_and_bounds_pages(self):
        collector=FilmGrabImageCollector()
        with patch.object(collector,'get_html',side_effect=[SEARCH,GALLERY,SEARCH]) as fetch:
            self.assertEqual(len(collector.collect('Example Film')),3)
            self.assertEqual(len(collector.collect('Example Director')),3)
            self.assertEqual(fetch.call_count,3)

    def test_blocking_and_cross_site_redirect_stop_without_retry(self):
        for response,reason in [
            (httpx.Response(403,request=httpx.Request('GET',PAGE)),'IMAGE_SOURCE_REJECTED'),
            (httpx.Response(429,request=httpx.Request('GET',PAGE)),'IMAGE_SOURCE_RATE_LIMITED'),
            (httpx.Response(302,headers={'location':'https://evil.example/'}),'IMAGE_SOURCE_REJECTED')]:
            with patch('app.research.filmgrab.httpx.get',return_value=response) as request:
                with self.assertRaises(ImageSourceUnavailable) as caught:FilmGrabImageCollector().get_html(PAGE)
                self.assertEqual(caught.exception.reason,reason);request.assert_called_once()

    def test_changed_markup_and_private_preview_are_not_successful_empty_galleries(self):
        for html in ['<html>Changed</html>',GALLERY.replace('https://film-grab.com/', 'http://127.0.0.1/')]:
            with self.assertRaises(ImageSourceUnavailable):gallery_images(html,PAGE)

    def test_page_failure_keeps_the_first_gallery_and_stops_the_source(self):
        collector=FilmGrabImageCollector()
        search=SEARCH+SEARCH.replace('/example/','/other/')
        with patch.object(collector,'get_html',side_effect=[search,GALLERY,ImageSourceUnavailable('IMAGE_SOURCE_TIMEOUT')]):
            rows=collector.collect('Example')
        self.assertEqual(len(rows),3);self.assertEqual(collector.provider_errors,['IMAGE_SOURCE_TIMEOUT'])


class MultiSourceImageTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        with self.sessions() as db,db.begin():
            plan=ResearchPlan(name='视频灵感',topics=['雨夜城市'],purpose='为短片寻找城市视觉参考，接受带水印预览。',
                websites=['https://film-grab.com/','https://openverse.org/'],collection_type='images')
            db.add(plan);db.flush();self.ident=plan.id
        self.db=self.sessions();app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(app);self.frames=gallery_images(GALLERY,PAGE)

    def tearDown(self):
        self.client.close();app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def test_supported_source_schema_and_assistant_scope_are_server_owned(self):
        plan=ResearchPlanInput(name='视频灵感',topics=['城市'],purpose='为短片寻找电影场景与色彩参考',
            websites=['https://film-grab.com/'],collection_type='images')
        model=Mock();model.analyze.return_value=json.dumps({'status':'draft_ready','message':'可先探索电影画面。',
            'questions':[],'plan':plan.model_dump()})
        proposal=propose_plan(PlanAssistantInput(messages=[{'role':'user','content':'为城市短片寻找画面参考'}]),model)
        self.assertEqual(proposal.sources[0].name,'FilmGrab 电影画面参考')
        self.assertIn('单帧未看图识别',proposal.sources[0].scope)
        with self.assertRaises(ValueError):ResearchPlanInput(**(plan.model_dump()|{'websites':['https://www.artstation.com/']}))

    def test_one_source_failure_does_not_discard_other_source_or_fake_intelligence(self):
        model=Mock();model.analyze.side_effect=[json.dumps({'filmgrab':['Example Film'],'openverse':['city night']}),selection(self.frames)]
        film=Mock();film.collect.return_value=self.frames
        other=Mock();other.collect.side_effect=ImageSourceUnavailable('IMAGE_SOURCE_RATE_LIMITED')
        rid=run_image_plan(self.ident,self.sessions,{'filmgrab':film,'openverse':other},model)
        with self.sessions() as db:
            run=db.get(ResearchRun,rid)
            self.assertEqual((run.status,run.inserted),('PARTIAL',3))
            self.assertEqual(run.errors,[{'website':'openverse.org','reason':'IMAGE_SOURCE_RATE_LIMITED'}])
            for cls in [Analysis,Item,NotificationDelivery]:self.assertEqual(db.scalar(select(func.count()).select_from(cls)),0)
        self.assertEqual(model.analyze.call_count,2);other.collect.assert_called_once()
        output=self.client.get(f'/api/v1/research-plans/{self.ident}/runs').json()[0]
        self.assertTrue(all(row['provider']=='filmgrab' and row['license']=='' for row in output['images']))
        self.assertIn('FilmGrab',output['image_summary']['limitations'])
        # Saved-film metadata remains re-analyzable and favorites preserve the provider label.
        again=Mock();again.analyze.return_value=selection(self.frames)
        reanalyze_images(self.ident,rid,self.sessions,again)
        image_id=output['images'][0]['id'];self.client.post(f'/api/v1/research-images/{image_id}/favorite')
        favorite=self.client.get(f'/api/v1/research-plans/{self.ident}/favorite-images').json()[0]
        self.assertEqual(favorite['provider'],'filmgrab')
        with patch('app.research.images.httpx.Client') as fetch:
            self.assertEqual(self.client.post(f'/api/v1/research-images/{image_id}/download').status_code,502)
            fetch.assert_not_called()

    def test_two_sources_have_fair_space_and_duplicate_runs_do_not_duplicate_images(self):
        film=Mock();film.collect.return_value=self.frames
        other=Mock();other.collect.return_value=[candidate(str(index)) for index in range(12)]
        for _ in range(2):
            model=Mock();model.analyze.side_effect=[json.dumps({'filmgrab':['Example Film'],'openverse':['city']}),selection(self.frames)]
            rid=run_image_plan(self.ident,self.sessions,{'filmgrab':film,'openverse':other},model)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ResearchImage)),9)
            self.assertEqual(db.get(ResearchRun,rid).inserted,0)
            self.assertEqual(set(db.scalars(select(ResearchImage.provider))),{'filmgrab','openverse'})

    def test_recollection_refreshes_film_credits_without_replacing_favorites(self):
        with self.sessions() as db,db.begin():db.get(ResearchPlan,self.ident).websites=['https://film-grab.com/']
        film=Mock();film.collect.return_value=self.frames
        def model():
            value=Mock();value.analyze.side_effect=[json.dumps({'filmgrab':['Example Film']}),selection(self.frames)]
            return value
        run_image_plan(self.ident,self.sessions,film,model())
        with self.sessions() as db,db.begin():
            image=db.scalar(select(ResearchImage).order_by(ResearchImage.id))
            image.creator='';image.favorite=True;ident=image.id
        rid=run_image_plan(self.ident,self.sessions,film,model())
        with self.sessions() as db:
            self.assertEqual(db.get(ResearchImage,ident).creator,self.frames[0].creator)
            self.assertTrue(db.get(ResearchImage,ident).favorite)
            self.assertEqual(db.get(ResearchRun,rid).inserted,0)

    def test_changing_sources_does_not_collect_or_touch_existing_purpose(self):
        with patch('app.research.images.run_image_plan') as run,patch('app.research.images.model_client') as model:
            response=self.client.post(f'/api/v1/research-plans/{self.ident}/image-sources',
                json={'websites':['https://film-grab.com/']})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['purpose'],'为短片寻找城市视觉参考，接受带水印预览。')
            run.assert_not_called();model.assert_not_called()
        for values in [[],['https://huaban.com/'],['https://film-grab.com/']*2]:
            self.assertEqual(self.client.post(f'/api/v1/research-plans/{self.ident}/image-sources',
                json={'websites':values}).status_code,422)
        with self.sessions() as db,db.begin():db.add(ResearchRun(plan_id=self.ident,status='RUNNING',errors=[]))
        self.assertEqual(self.client.post(f'/api/v1/research-plans/{self.ident}/image-sources',
            json={'websites':['https://openverse.org/']}).status_code,409)
