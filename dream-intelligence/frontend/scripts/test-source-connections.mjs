import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path,overrides={}) {
  const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
    compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  }).outputText;
  const exports={};
  new Function('require','exports',code)(name=>name in overrides?overrides[name]:name.startsWith('../api/')?{}:require(name),exports);
  return exports;
}
const definition={name:'GitHub 项目搜索',site_url:'https://github.com/',adapter:'json_api',endpoint:'https://api.github.com/search/repositories',
  description:'检索公开项目；排名只针对检索式。',enabled:true,auth_env:'GITHUB_TOKEN',auth_required:false,query_param:'q',query_suffix:'is:public',items_path:'items',
  field_map:{id:'id',title:'full_name',url:'html_url',content:'description',stars:'stargazers_count'},url_prefix:'',params:{order:'desc',page:'1'},
  sort_param:'sort',sort_values:['stars','updated'],default_sort:'stars',limit_param:'per_page',max_results:12};
const source={...definition,id:2,credential_present:false,ready:true};
const binding={connection_id:2,query:'ComfyUI',sort:'stars',limit:6};
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));

test('configuration form names credentials without accepting key values or running a check',()=>{
  const {SourceDefinitionForm}=load('../src/pages/SourceConnections.tsx');
  const html=render(SourceDefinitionForm,{initial:definition,onSave:async()=>{},onCancel:()=>{},busy:false});
  assert.ok(html.includes('凭据环境变量名（不填密钥）')&&html.includes('GITHUB_TOKEN'));
  assert.ok(html.includes('字段映射')&&html.includes('固定参数')&&html.includes('请求地址'));
  assert.ok(html.includes('保存接口')&&html.includes('不会采集、调用模型或启动定时任务'));
  assert.ok(!html.includes('测试连接')&&!html.includes('现在运行'));
});

test('source status separates configuration and credentials from real connection validation',()=>{
  const {SourceConnectionCard}=load('../src/pages/SourceConnections.tsx');
  const html=render(SourceConnectionCard,{source,onEdit:()=>{}});
  assert.ok(html.includes('尚未联网验收')&&html.includes('可尝试匿名请求'));
  assert.ok(!html.includes('连接成功'));
  const missing=render(SourceConnectionCard,{source:{...source,auth_required:true,ready:false},onEdit:()=>{}});
  assert.ok(missing.includes('缺少凭据变量'));
});

test('manual plans select reusable sources with query sort and result bound',()=>{
  const {ConfiguredSourcePicker}=load('../src/pages/Research.tsx',{
    './ResearchResults':{ResearchResults:()=>null},'./PlanAssistant':{PlanAssistant:()=>null},
    './ImageResults':{ImageResults:()=>null},'./TiboUpdates':{TiboUpdates:()=>null},'./VideoResults':{VideoResults:()=>null,VideoScheduleSettings:()=>null}});
  const html=render(ConfiguredSourcePicker,{connections:[source],bindings:[binding],onChange:()=>{}});
  assert.ok(html.includes('GitHub 项目搜索')&&html.includes('ComfyUI')&&html.includes('Star 数从高到低'));
  assert.ok(html.includes('value="6"')&&html.includes('保存不会运行采集'));
  const empty=render(ConfiguredSourcePicker,{connections:[],bindings:[],onChange:()=>{}});
  assert.ok(empty.includes('/settings?tab=sources'));
});

test('assistant preview retains configured source binding even when websites is empty',()=>{
  const {PlanPreview}=load('../src/pages/PlanAssistant.tsx');
  const html=render(PlanPreview,{proposal:{status:'draft_ready',plan:{name:'ComfyUI 前六',topics:['ComfyUI'],websites:[],
    purpose:'筛选工作流工具',source_bindings:[binding]},sources:[{connection_id:2,name:source.name,url:source.site_url,scope:source.description}]}});
  assert.ok(html.includes('GitHub 项目搜索')&&html.includes('ComfyUI')&&html.includes('stars')&&html.includes('最多 6 条'));
  assert.ok(html.includes('href="https://github.com/"'));
});

test('search evidence preserves API rank star snapshot and incomplete coverage',()=>{
  const {SourceSearchEvidence}=load('../src/pages/ResearchResults.tsx');
  const report={connection_id:2,name:'GitHub',site_url:'https://github.com/',query:'ComfyUI',sort:'stars',limit:6,
    observed_at:'2026-10-30T06:00:00Z',status:'COMPLETED',received:2,selected:2,incomplete:true,
    results:[{item_id:3,title:'Highest stars',url:'https://github.com/a/high',content:'First',stars:100},
      {item_id:1,title:'Lower stars',url:'https://github.com/a/low',content:'Second',stars:50}]};
  const html=render(SourceSearchEvidence,{reports:[report]});
  assert.ok(html.indexOf('Highest stars')<html.indexOf('Lower stars'));
  assert.ok(html.includes('★ 100')&&html.includes('结果不完整')&&html.includes('当次观测值'));
  assert.ok(html.includes('仓库建立时间不等于版本发布时间'));
  const failed=render(SourceSearchEvidence,{reports:[{...report,status:'SOURCE_RATE_LIMITED',results:[]}]});
  assert.ok(failed.includes('不能视为没有匹配结果'));
});

test('saving a source and its plan binding never invokes collection endpoints',async()=>{
  const {saveSourceConnection,savePlanSourceBindings}=load('../src/api/sourceConnections.ts');
  const previous=globalThis.fetch,calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url,method:options.method,body:JSON.parse(options.body)});return {ok:true,json:async()=>source};};
  try {
    await saveSourceConnection(definition);
    await saveSourceConnection({...definition,enabled:false},2);
    await savePlanSourceBindings(4,[binding]);
    assert.ok(calls[0].url.endsWith('/source-connections'));
    assert.ok(calls[1].url.endsWith('/source-connections/2'));
    assert.ok(calls[2].url.endsWith('/research-plans/4/source-bindings'));
    assert.deepEqual(calls[0].body,definition);assert.deepEqual(calls[2].body,{bindings:[binding]});
    assert.ok(calls.every(row=>row.method==='POST'&&!row.url.endsWith('/run')));
  }finally{globalThis.fetch=previous;}
});

test('settings sources deep link opens configuration rather than subscription controls',()=>{
  const previous=globalThis.window;globalThis.window={location:{pathname:'/settings',search:'?tab=sources'}};
  try {
    const {Settings}=load('../src/pages/Settings.tsx',{'./Research':{Research:()=>null},'./Watchlist':{Watchlist:()=>null},
      './SubscriptionSettings':{SubscriptionSettings:()=>React.createElement('p',{},'Subscription')},
      './SourceConnections':{SourceConnections:()=>React.createElement('p',{},'Source configuration')}});
    const html=render(Settings,{});assert.ok(html.includes('Source configuration')&&!html.includes('>Subscription<'));
    assert.match(html,/aria-selected="true"[^>]*id="tab-sources"/);
  }finally{if(previous===undefined)delete globalThis.window;else globalThis.window=previous;}
});
