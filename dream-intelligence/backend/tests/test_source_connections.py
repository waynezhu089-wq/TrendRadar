import json
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db, initialize_database
from app.db.models import (SourceConnection, ResearchPlan, ResearchPlanSource, ResearchRun,
                           ResearchSourceReport, Item, Analysis)
from app.schemas.source_connections import SourceDefinition, SourceBinding
from app.research.source_connections import (GITHUB_TEMPLATE, JSON_TEMPLATE, ConfiguredSourceCollector,
    SourceCollectionError, configured_catalog, RSS_TEMPLATE)
from app.research.websites import WebItem
from app.research.collection import run_research_plan, reanalyze_research_run
from app.research.plan_assistant import propose_plan
from app.schemas.plan_assistant import PlanAssistantInput


def repository(index=1, stars=100, description='ComfyUI workflow tool'):
    return dict(id=index, full_name=f'owner/tool-{index}', html_url=f'https://github.com/owner/tool-{index}',
        description=description, stargazers_count=stars, created_at='2020-01-01T00:00:00Z', updated_at='2026-10-30T00:00:00Z')


class ConfiguredAdapterTests(unittest.TestCase):
    def call(self, handler, definition=GITHUB_TEMPLATE, binding=None):
        worker=ConfiguredSourceCollector(httpx.MockTransport(handler))
        with patch('app.research.source_connections.require_public_host'):
            return worker.collect(1,definition,binding or SourceBinding(connection_id=1,query='ComfyUI',sort='stars',limit=6),['ComfyUI'])

    def test_github_query_sort_limit_and_rank_snapshot_are_real_response_fields(self):
        calls=[]
        def handler(request):
            calls.append(request)
            self.assertEqual(dict(request.url.params),{'order':'desc','page':'1','q':'ComfyUI is:public','sort':'stars','per_page':'6'})
            self.assertEqual(request.headers['Authorization'],'Bearer unit-test-only')
            return httpx.Response(200,json={'items':[repository(n,100-n) for n in range(1,7)],'incomplete_results':True})
        with patch.dict('os.environ',{'GITHUB_TOKEN':'unit-test-only'}):
            batch=self.call(handler)
        self.assertEqual(len(calls),1)
        self.assertEqual(len(batch.items),6)
        self.assertEqual(batch.report['results'][0]['stars'],99)
        self.assertEqual(batch.report['results'][0]['published_at'],'2020-01-01T00:00:00+00:00')
        self.assertTrue(batch.report['incomplete'])
        self.assertNotIn('unit-test-only',json.dumps(batch.report))

    def test_other_json_api_uses_configuration_without_a_site_branch(self):
        definition=JSON_TEMPLATE.model_copy(update=dict(endpoint='https://models.example/api/models',
            site_url='https://models.example/',query_param='search',items_path='data.entries',
            field_map={'id':'key','title':'card.title','content':'card.summary'},
            url_prefix='https://models.example/models/',sort_values=['downloads'],default_sort='downloads'))
        def handler(request):
            self.assertEqual(request.url.params['search'],'ComfyUI')
            self.assertEqual(request.url.params['sort'],'downloads')
            return httpx.Response(200,json={'data':{'entries':[{'key':'owner/model','card':{'title':'Model','summary':'Description'}}]}})
        batch=self.call(handler,definition,SourceBinding(connection_id=1,query='ComfyUI'))
        self.assertEqual(batch.items[0].url,'https://models.example/models/owner/model')
        self.assertIsNone(batch.items[0].published_at)

    def test_redirect_errors_limits_and_malformed_responses_do_not_retry_or_echo_bodies(self):
        cases=[(httpx.Response(302,headers={'location':'http://127.0.0.1/'}),'SOURCE_REDIRECT_REJECTED'),
            (httpx.Response(401,text='secret-provider-body'),'SOURCE_ACCESS_DENIED'),
            (httpx.Response(403,text='secret-provider-body'),'SOURCE_ACCESS_DENIED'),
            (httpx.Response(429,text='secret-provider-body'),'SOURCE_RATE_LIMITED'),
            (httpx.Response(500,text='secret-provider-body'),'SOURCE_HTTP_FAILED'),
            (httpx.Response(200,text='html'),'SOURCE_FORMAT_CHANGED'),
            (httpx.Response(200,json={'unexpected':[]}),'SOURCE_FORMAT_CHANGED'),
            (httpx.Response(200,json={'items':[{'invalid':True}]}),'SOURCE_FORMAT_CHANGED'),
            (httpx.Response(200,content=b' '*1_000_001,headers={'content-type':'application/json'}),'SOURCE_RESPONSE_TOO_LARGE')]
        for response,code in cases:
            calls=[]
            def handler(request):calls.append(request);return response
            with self.subTest(code=code),self.assertRaises(SourceCollectionError) as caught:self.call(handler)
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn('secret-provider-body',str(caught.exception))
            self.assertEqual(len(calls),1)

    def test_missing_required_credential_prevents_network_and_disabled_source_cannot_run(self):
        for updates,code in [({'auth_required':True},'SOURCE_AUTH_MISSING'),({'enabled':False},'SOURCE_DISABLED')]:
            handler=Mock()
            with patch.dict('os.environ',{},clear=True),self.assertRaises(SourceCollectionError) as caught:
                self.call(handler,GITHUB_TEMPLATE.model_copy(update=updates))
            self.assertEqual(caught.exception.code,code);handler.assert_not_called()

    def test_duplicate_ids_deduplicate_and_unknown_dates_stay_unknown(self):
        row=repository();row['created_at']='2026-10-30T00:00:00'
        batch=self.call(lambda request:httpx.Response(200,json={'items':[row,row]}))
        self.assertEqual(len(batch.items),1);self.assertIsNone(batch.items[0].published_at)

    def test_empty_array_is_success_but_not_an_analysis(self):
        batch=self.call(lambda request:httpx.Response(200,json={'items':[]}))
        self.assertEqual(batch.report['status'],'COMPLETED');self.assertEqual(batch.items,[])

    def test_rss_adapter_uses_explicit_binding_filter_without_a_json_request(self):
        worker=ConfiguredSourceCollector()
        pages=[WebItem('AI news','https://example.com/ai','AI update'),WebItem('Workflow guide','https://example.com/guide','Workflow tools')]
        with patch('app.research.source_connections.WebsiteCollector.collect',return_value=pages),patch('app.research.source_connections.httpx.Client') as api:
            result=worker.collect(1,RSS_TEMPLATE,SourceBinding(connection_id=1,query='workflow',limit=6),['AI'])
        api.assert_not_called();self.assertEqual([row.title for row in result.items],['Workflow guide'])
        self.assertEqual(result.report['received'],2);self.assertEqual(result.report['selected'],1)


class SourceConnectionAPITests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        self.db=Session(self.engine);app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close();app.dependency_overrides.clear();self.db.close();self.engine.dispose()

    def source(self, **updates):
        row=SourceConnection(definition=GITHUB_TEMPLATE.model_dump()|updates)
        self.db.add(row);self.db.commit();return row

    def plan(self, source):
        response=self.client.post('/api/v1/research-plans',json=dict(name='ComfyUI 项目观察',topics=['ComfyUI'],websites=[],
            purpose='研究可用于视频工作流与工具选型的公开项目',source_bindings=[dict(connection_id=source.id,query='ComfyUI',sort='stars',limit=6)]))
        self.assertEqual(response.status_code,201,response.text);return response.json()

    def test_template_and_save_read_only_do_not_collect_analyze_or_seed(self):
        with patch('app.research.source_connections.ConfiguredSourceCollector.collect') as collect,patch('app.research.plan_assistant.OpenAICompatibleClient') as model:
            self.assertEqual(self.client.get('/api/v1/source-connections').json(),[])
            templates=self.client.get('/api/v1/source-connections/templates').json()
            self.assertEqual(len(templates),3)
            response=self.client.post('/api/v1/source-connections',json=templates[0]['definition'])
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(self.client.get('/api/v1/source-connections/catalog').json()[0]['sort_values'],['stars','updated'])
            collect.assert_not_called();model.assert_not_called()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Item)),0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ResearchPlan)),0)

    def test_credentials_are_references_and_never_echoed_in_validation_or_catalog(self):
        secret='sentinel-never-return-this'
        with patch.dict('os.environ',{'GITHUB_TOKEN':secret}):
            response=self.client.post('/api/v1/source-connections',json=GITHUB_TEMPLATE.model_dump())
            self.assertTrue(response.json()['credential_present']);self.assertNotIn(secret,response.text)
            catalog=self.client.get('/api/v1/source-connections/catalog')
            self.assertNotIn('GITHUB_TOKEN',catalog.text);self.assertNotIn(secret,catalog.text)
        response=self.client.post('/api/v1/source-connections',json=GITHUB_TEMPLATE.model_dump()|{'auth_env':secret})
        self.assertEqual(response.status_code,422);self.assertNotIn(secret,response.text)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SourceConnection)),1)

    def test_reject_private_urls_credential_parameters_code_and_unbounded_counts(self):
        updates=[{'endpoint':'http://127.0.0.1/private'}, {'endpoint':'https://user:pass@example.com/api'},
            {'endpoint':'https://api.github.com/search/repositories?token=sensitive'},
            {'params':{'api_key':'sensitive'}},{'params':{'key':'sensitive'}},{'auth_env':'DSIH_LLM_API_KEY'},
            {'endpoint':'https://evil.example/api','auth_env':'GITHUB_TOKEN'},
            {'items_path':'items[0]'},{'max_results':13},{'params':{'q':'collision'}},
            {'default_sort':'execute'}, {'unexpected_script':'print(secret)'}]
        for change in updates:
            with self.subTest(change=change):
                response=self.client.post('/api/v1/source-connections',json=GITHUB_TEMPLATE.model_dump()|change)
                self.assertEqual(response.status_code,422);self.assertNotIn('sensitive',response.text)

    def test_bind_create_confirm_and_update_are_separate_from_execution(self):
        source=self.source();plan=self.plan(source)
        self.assertEqual(plan['source_bindings'][0]['limit'],6)
        confirm=self.client.post('/api/v1/research-plan-assistant/create',json={'plan':{k:v for k,v in plan.items() if k not in ('id','created_at')},'confirmed':True})
        self.assertEqual(confirm.status_code,200,confirm.text);self.assertFalse(confirm.json()['created'])
        for limit in (3,5):
            response=self.client.post(f"/api/v1/research-plans/{plan['id']}/source-bindings",json={'bindings':[dict(connection_id=source.id,query='topic:comfyui',sort='stars',limit=limit)]})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['source_bindings'][0]['limit'],limit)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ResearchPlanSource)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ResearchRun)),0)
        self.assertEqual(self.client.post(f"/api/v1/research-plans/{plan['id']}/source-bindings",json={'bindings':[]}).status_code,422)

    def test_invalid_binding_and_disabled_source_are_not_silently_substituted(self):
        source=self.source();plan=self.plan(source)
        for binding in [dict(connection_id=999),dict(connection_id=source.id,sort='invented'),dict(connection_id=source.id,limit=13)]:
            response=self.client.post(f"/api/v1/research-plans/{plan['id']}/source-bindings",json={'bindings':[binding]})
            self.assertEqual(response.status_code,422)
        self.client.post(f'/api/v1/source-connections/{source.id}',json=source.definition|{'enabled':False})
        self.db.expire_all()
        with patch('app.research.source_connections.httpx.Client') as network:
            ident=run_research_plan(plan['id'],self.sessions)
        network.assert_not_called()
        self.db.expire_all();run=self.db.get(ResearchRun,ident)
        self.assertEqual(run.status,'FAILED');self.assertEqual(run.errors[0]['reason'],'SOURCE_DISABLED')

    def test_catalog_drives_assistant_and_rejects_invented_or_disabled_ids(self):
        source=self.source();catalog=configured_catalog(self.db)
        request=PlanAssistantInput(messages=[{'role':'user','content':'帮我关注 GitHub 上 ComfyUI star 前6的项目，用于工具选型'}])
        plan=dict(name='ComfyUI',topics=['ComfyUI'],websites=[],purpose='选择可用于视频制作工作流的公开项目',source_bindings=[dict(connection_id=source.id,query='ComfyUI',sort='stars',limit=6)])
        fake=Mock();fake.analyze.return_value=json.dumps(dict(status='draft_ready',message='按已配置的 GitHub 接口生成草案。',questions=[],plan=plan))
        result=propose_plan(request,fake,source_catalog=catalog)
        context=json.loads(fake.analyze.call_args.args[0][1]['content'])
        self.assertEqual(context['configured_sources'][0]['connection_id'],source.id)
        self.assertNotIn('auth_env',context['configured_sources'][0])
        self.assertEqual(result.sources[0].connection_id,source.id)
        for unavailable in [[],[catalog[0]|{'enabled':False}]]:
            with self.assertRaises(ValueError):propose_plan(request,fake,source_catalog=unavailable)

    def test_runs_deduplicate_items_but_preserve_each_rank_and_content_snapshot(self):
        source=self.source();plan=self.plan(source)
        version={'stars':100,'content':'first snapshot'}
        def handler(request):return httpx.Response(200,json={'items':[repository(stars=version['stars'],description=version['content'])]})
        def factory():return ConfiguredSourceCollector(httpx.MockTransport(handler))
        payloads=[]
        def answer(messages):
            payload=json.loads(messages[-1]['content']);payloads.append(payload)
            ids=[row['item_id'] for row in payload['items']]
            return json.dumps(dict(overview='公开仓库检索快照',findings=[dict(item_id=ids[0],insight='公开描述中的工具线索',purpose_relevance='可能适合工作流选型',suggested_action='核对项目文档')],limitations='只依据公开描述与本次排名，未执行项目。',
                sections=[dict(category='工具与插件',summary='候选项目待进一步验证',key_points=['依据接口快照'],suggested_action='打开原仓库核实',item_ids=ids)]))
        fake=Mock();fake.analyze.side_effect=answer
        with patch('app.research.source_connections.require_public_host'):
            first=run_research_plan(plan['id'],self.sessions,client=fake,configured_collector_factory=factory)
            version.update(stars=110,content='second snapshot')
            second=run_research_plan(plan['id'],self.sessions,client=fake,configured_collector_factory=factory)
            reanalyze_research_run(plan['id'],first,self.sessions,client=fake)
        self.db.expire_all()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Item)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Analysis)),0)
        self.assertEqual(self.db.get(ResearchSourceReport,first).reports[0]['results'][0]['stars'],100)
        self.assertEqual(self.db.get(ResearchSourceReport,second).reports[0]['results'][0]['stars'],110)
        self.assertEqual([payload['items'][0]['content'] for payload in payloads],['first snapshot','second snapshot','first snapshot'])
        self.assertEqual(self.db.get(ResearchRun,second).status,'COMPLETED')

    def test_source_report_survives_summary_failure(self):
        source=self.source();plan=self.plan(source);fake=Mock();fake.analyze.side_effect=RuntimeError('private provider output')
        factory=lambda:ConfiguredSourceCollector(httpx.MockTransport(lambda request:httpx.Response(200,json={'items':[repository()]})))
        with patch('app.research.source_connections.require_public_host'):
            ident=run_research_plan(plan['id'],self.sessions,client=fake,configured_collector_factory=factory)
        self.db.expire_all()
        run=self.client.get(f"/api/v1/research-plans/{plan['id']}/runs").json()[0]
        self.assertEqual(run['status'],'SUMMARY_FAILED')
        self.assertEqual(run['source_reports'][0]['results'][0]['stars'],100)
        self.assertNotIn('private provider output',json.dumps(run))

    def test_access_failure_stops_other_connections_on_the_same_host(self):
        first=self.source();second=self.source(name='GitHub 第二配置')
        plan=ResearchPlan(name='Two sources',topics=['ComfyUI'],websites=[],purpose='Review public workflow tools',
            source_bindings=[ResearchPlanSource(connection_id=source.id,query='ComfyUI',sort='stars',limit=6) for source in (first,second)])
        self.db.add(plan);self.db.commit();calls=[]
        def handler(request):calls.append(request);return httpx.Response(429,text='private response')
        factory=lambda:ConfiguredSourceCollector(httpx.MockTransport(handler))
        with patch('app.research.source_connections.require_public_host'):
            ident=run_research_plan(plan.id,self.sessions,configured_collector_factory=factory)
        self.db.expire_all();run=self.db.get(ResearchRun,ident)
        self.assertEqual(len(calls),1)
        self.assertEqual([row['reason'] for row in run.errors],['SOURCE_RATE_LIMITED','SOURCE_ACCESS_STOPPED'])

    def test_historical_output_uses_saved_url_and_title_after_api_changes(self):
        source=self.source();plan=self.plan(source)
        payload=repository();factory=lambda:ConfiguredSourceCollector(httpx.MockTransport(lambda request:httpx.Response(200,json={'items':[payload]})))
        fake=Mock();fake.analyze.side_effect=RuntimeError('skip model')
        with patch('app.research.source_connections.require_public_host'):
            first=run_research_plan(plan['id'],self.sessions,client=fake,configured_collector_factory=factory)
            payload.update(full_name='owner/renamed',html_url='https://github.com/owner/renamed',created_at=None)
            second=run_research_plan(plan['id'],self.sessions,client=fake,configured_collector_factory=factory)
        self.db.expire_all()
        runs={row['id']:row for row in self.client.get(f"/api/v1/research-plans/{plan['id']}/runs").json()}
        self.assertEqual(runs[first]['items'][0]['url'],'https://github.com/owner/tool-1')
        self.assertEqual(runs[second]['items'][0]['url'],'https://github.com/owner/renamed')
        self.assertEqual(runs[second]['items'][0]['title'],'owner/renamed')
        self.assertIsNone(runs[second]['items'][0]['published_at'])

    def test_configuration_edits_are_blocked_while_a_manual_run_is_active(self):
        from app.api.v1.research import manual_run_lock
        source=self.source()
        with manual_run_lock:
            response=self.client.post(f'/api/v1/source-connections/{source.id}',json=source.definition|{'name':'Changed'})
        self.assertEqual(response.status_code,409)
        self.db.expire_all();self.assertNotEqual(self.db.get(SourceConnection,source.id).definition['name'],'Changed')

    def test_additive_initialization_keeps_legacy_plan_without_seeding_sources(self):
        legacy=ResearchPlan(name='Legacy',topics=['AI'],websites=['https://example.com/'],purpose='Track useful public AI tools')
        self.db.add(legacy);self.db.commit();ident=legacy.id
        initialize_database(self.engine)
        self.db.expire_all();self.assertEqual(self.db.get(ResearchPlan,ident).source_bindings,[])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SourceConnection)),0)
