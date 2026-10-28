import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path){const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const exports={};new Function('require','exports',code)(name=>name.startsWith('../api/')?{}:require(name),exports);return exports;}
const {CommissionCard,CommissionContent}=load('../src/pages/Commissions.tsx');
const row={id:1,title:'AI视频制作需求',url:'https://square.aigcsdm.com/demands/1',source:'sdm',source_name:'AigcSDM',
  description:'委托制作AI视频，预算及合同需核实。',budget:null,deadline:null,publisher:null,published_on:null,
  source_status:'OPEN',status:'OPEN',category:'视频与广告',region:'MAINLAND_CLUE',region_evidence:'广东公司',
  checked_at:'2026-10-24T00:00:00Z',captured_at:'2026-10-24T00:00:00Z'};
const data={leads:[row,{...row,id:2,title:'待核实的需求',region:'UNKNOWN'},
  {...row,id:3,title:'过期的需求',status:'EXPIRED'}],sources:[],latest:null};
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));

test('shows only mainland clues by default and separates unknown and expired opportunities',()=>{
  const html=render(CommissionContent,{data});
  assert.ok(html.includes('AI视频制作需求')&&!html.includes('待核实的需求')&&!html.includes('过期的需求'));
  const pending=render(CommissionContent,{data,scope:'pending'});
  assert.ok(pending.includes('待核实的需求')&&!pending.includes('AI视频制作需求'));
  assert.ok(render(CommissionContent,{data,showClosed:true}).includes('过期的需求'));
});
test('missing commercial details are not invented and source evidence is explicit',()=>{
  const html=render(CommissionCard,{row});
  assert.ok(html.includes('未披露')&&html.includes('未知')&&html.includes('广东公司'));
  assert.ok(html.includes('未核验发布方身份')&&html.includes('查看原始需求'));
  assert.ok(!html.includes('已验证甲方')&&!html.includes('优质商单'));
});
test('keeps each area compact with remaining opportunities collapsed',()=>{
  const html=render(CommissionContent,{data:{...data,leads:[row,{...row,id:4},{...row,id:5}]}});
  assert.ok(html.includes('展开其余 1 条')&&html.includes('commission-more'));
});
test('unavailable sources are not presented as a successful search with no work',()=>{
  const html=render(CommissionContent,{data:{...data,latest:{status:'PARTIAL',sources:[
    {source:'manju',name:'漫剧工场',url:'https://www.manjugongchang.com/demand',status:'FAILED',checked:0,accepted:0,errors:['SOURCE_UNAVAILABLE']}]}}});
  assert.ok(html.includes('不能据此判断没有商单')&&html.includes('读取失败')&&html.includes('AI视频制作需求'));
});
test('marketplace selection isolates sources and preserves limited discovery explanation',()=>{
  const state={...data,leads:[row,{...row,id:9,source:'zbj',source_name:'猪八戒',title:'猪八戒 AI视频'}],
    latest:{status:'COMPLETED',sources:[{source:'zbj',name:'猪八戒',url:'https://www.zbj.com/xq/example.html',
      status:'OK',checked:3,accepted:3,errors:[],coverage:'有限发现：公开详情及相似需求，并非全站搜索。'}]}};
  const html=render(CommissionContent,{data:state,source:'zbj'});
  assert.ok(html.includes('猪八戒 AI视频')&&!html.includes('AI视频制作需求'));
  assert.ok(html.includes('有限发现')&&html.includes('并非全站搜索'));
});
test('registration deadline and awarded state are distinct from delivery deadline',()=>{
  const html=render(CommissionCard,{row:{...row,source:'tahou',source_name:'塔猴',status:'CLOSED',
    source_status_text:'已定标',deadline_kind:'REGISTRATION',deadline_at:'2026-10-28T14:00:00+08:00',
    delivery_deadline:'2026/11/05 00:00:00'}});
  assert.ok(html.includes('已定标')&&html.includes('已停止招募')&&html.includes('报名截止'));
  assert.ok(html.includes('14:00:00')&&html.includes('2026/11/05 00:00:00'));
});
test('read never starts collection and explicit update uses POST',async()=>{
  const {getCommissions,collectCommissions}=load('../src/api/commissions.ts');
  const previous=globalThis.fetch;const calls=[];
  try{globalThis.fetch=async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({})};};
    await getCommissions();await collectCommissions();
    assert.ok(calls[0].url.endsWith('/commissions')&&!calls[0].options.method);
    assert.ok(calls[1].url.endsWith('/commissions/collect'));assert.equal(calls[1].options.method,'POST');
  }finally{globalThis.fetch=previous;}
});
