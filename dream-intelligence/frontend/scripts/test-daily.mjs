import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path, overrides={}) {
  const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
    compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  }).outputText;
  const exports={};
  new Function('require','exports',code)(name=>name in overrides ? overrides[name]
    : name.startsWith('../api/') ? {} : require(name),exports);
  return exports;
}
const { TodayContent }=load('../src/pages/Today.tsx');
const entry=(id,title,date)=>({id,title,published_at:date,url:`https://example.com/${id}`,source:'Test',summary:'条目分析',priority:null,captured_at:'2026-10-23T00:00:00Z',analyzed_at:'2026-10-23T00:30:00Z',included_at:'2026-10-23T00:30:00Z'});
const data={days:1,start:'2026-10-22T16:00:00Z',end:'2026-10-23T03:00:00Z',unknown_dates:2,fingerprint:'test',analysis:null,pending_candidates:0,notices:[],processing:null,
  topics:[{id:'plan-1',title:'视频技术',purpose:'为工具选型提供线索',href:'/research?plan=1',total:4,
    items:[entry(1,'Newest news','2026-10-23T02:00:00Z'),entry(2,'Second news','2026-10-23T01:00:00Z'),
      entry(3,'Third news','2026-10-23T00:00:00Z'),entry(4,'Not expanded','2026-10-22T16:00:00Z')]}]};
const render=props=>renderToStaticMarkup(React.createElement(TodayContent,props));

test('daily topic cards show three latest headlines and a research deep link',()=>{
  const html=render({data});
  assert.ok(html.includes('视频技术')&&html.includes('为工具选型提供线索'));
  assert.equal((html.match(/<time /g)??[]).length,3);
  assert.ok(html.indexOf('Newest news')<html.indexOf('Second news'));
  assert.ok(!html.includes('Not expanded'));
  assert.ok(html.includes('href="/research?plan=1"')&&html.includes('共 4 条'));
  assert.ok(html.includes('生成本期分析')&&html.includes('发布时间未知'));
  assert.ok(!html.includes('Watchlist'));
});
test('empty today does not reuse an older research summary or offer a model call',()=>{
  const html=render({data:{...data,topics:[{...data.topics[0],total:0,items:[]}]}});
  assert.ok(html.includes('今日暂无新增')&&html.includes('查看近 7 天'));
  assert.ok(!html.includes('生成本期分析')&&!html.includes('条目分析'));
});
test('seven-day report stays labelled and long advice is initially collapsed',()=>{
  const html=render({data:{...data,days:7,analysis:{overview:['范围内的重要变化'],topics:[{topic_id:'plan-1',summary:'同类归纳',key_points:['有依据的线索'],suggested_action:'下一步建议',item_ids:[1,2,3,4]}]}}});
  assert.ok(html.includes('近 7 天简报')&&html.includes('同类归纳'));
  assert.ok(html.includes('<details>')&&!html.includes('<details open'));
  assert.ok(!html.includes('生成本期分析'));
});
test('Today is home, Watchlist moves to Settings and old URLs still work',()=>{
  const names=['Today','Settings','Market','Research','Commissions'];
  const overrides=Object.fromEntries(names.map(name=>[`./pages/${name}`,{[name]:()=>React.createElement('p',{},`Page:${name}`)}]));
  const {default:App}=load('../src/App.tsx',overrides);
  try {
    for(const [path,name] of [['/','Today'],['/today','Today'],['/settings','Settings'],['/watchlist','Settings'],['/market','Market'],['/research','Research'],['/commissions','Commissions']]) {
      globalThis.window={location:{pathname:path}};
      const html=renderToStaticMarkup(React.createElement(App));
      assert.ok(html.includes(`Page:${name}`));
      assert.equal((html.match(/aria-current="page"/g)??[]).length,1);
      assert.ok(!html.includes('Watchlist')&&!html.includes('总览'));
    }
  }finally{delete globalThis.window;}
});
test('plan creation belongs to Settings, not the Research reading workspace',()=>{
  const {Research}=load('../src/pages/Research.tsx',{'./ResearchResults':{ResearchResults:()=>null},'./PlanAssistant':{PlanAssistant:()=>null},'./ImageResults':{ImageResults:()=>null},'./TiboUpdates':{TiboUpdates:()=>null},'./VideoResults':{VideoResults:()=>null,VideoScheduleSettings:()=>null}});
  const normal=renderToStaticMarkup(React.createElement(Research));
  const settings=renderToStaticMarkup(React.createElement(Research,{settings:true}));
  assert.ok(!normal.includes('<form')&&normal.includes('管理议题与来源'));
  assert.ok(settings.includes('<form')&&settings.includes('分析目的'));
  assert.ok(!settings.includes('<main'));
});
test('daily read and explicit analysis reach the backend rather than Vite',async()=>{
  const {getDaily,analyzeDaily}=load('../src/api/daily.ts');
  const original=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>data};};
  try {
    await getDaily(1); await getDaily(7); await analyzeDaily(7); await analyzeDaily(1,true);
    assert.deepEqual(calls.map(c=>c.url),[
      'http://127.0.0.1:8000/api/v1/daily-brief?days=1',
      'http://127.0.0.1:8000/api/v1/daily-brief?days=7',
      'http://127.0.0.1:8000/api/v1/daily-brief/analyze?days=7',
      'http://127.0.0.1:8000/api/v1/daily-brief/analyze?days=1&include_pending=true']);
    assert.equal(calls[2].options.method,'POST');
    assert.equal(calls[0].options.method,undefined);
  }finally{globalThis.fetch=original;}
});

test('old publication is labelled, unknown publication is not replaced by capture time',()=>{
  const html=render({data:{...data,topics:[{...data.topics[0],items:[entry(1,'Older','2026-10-01T00:00:00Z'),entry(2,'Undated',null)]}]}});
  assert.ok(html.includes('较早发布 · 本期收录/分析'));
  assert.ok(html.includes('发布时间未知'));
  assert.equal((html.match(/<time /g)??[]).length,1);
});
test('raw-only candidates can be explicitly analyzed and partial failure stays visible',()=>{
  const html=render({data:{...data,topics:[],pending_candidates:2,processing:{analyzed:1,skipped:0,failed:1},notices:['部分条目分析未通过校验']}});
  assert.ok(html.includes('分析并更新简报')&&html.includes('每次最多 6 条'));
  assert.ok(html.includes('失败 1 条')&&html.includes('部分条目分析未通过校验'));
});
