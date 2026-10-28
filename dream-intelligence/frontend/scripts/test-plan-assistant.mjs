import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path) {
  const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
    compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  }).outputText;
  const exports={};
  new Function('require','exports',code)(name=>name.startsWith('../api/') ? {} : require(name),exports);
  return exports;
}
const {PlanPreview,PlanAssistant}=load('../src/pages/PlanAssistant.tsx');
const plan={name:'教育素材观察',topics:['教育话题','亲子沟通'],websites:['https://weibo.com/'],purpose:'为视频号寻找值得核实和深入阅读的教育素材'};
const proposal={status:'draft_ready',message:'建议先从微博热榜看',questions:[],plan,
  sources:[{url:'https://weibo.com/',name:'微博公共热榜',scope:'只有标题和链接，未读取原帖'}]};

test('assistant is a quiet request composer, not an automatic collection action',()=>{
  const html=renderToStaticMarkup(React.createElement(PlanAssistant,{onCreated:()=>{},onClose:()=>{}}));
  assert.ok(html.includes('说说你想关注什么')&&html.includes('你的需求'));
  assert.ok(!html.includes('创建这个方案')&&!html.includes('现在运行'));
});
test('draft preview includes purpose and source limits without claiming creation',()=>{
  const html=renderToStaticMarkup(React.createElement(PlanPreview,{proposal}));
  assert.ok(html.includes('待创建的关注方案')&&html.includes(plan.purpose));
  assert.ok(html.includes('教育话题 · 亲子沟通')&&html.includes('未读取原帖'));
  assert.ok(!html.includes('已创建'));
});
test('an available-source draft clearly lists omitted sites without blocking preview',()=>{
  const value={...proposal,deferred_sources:[{name:'豆瓣',reason:'尚未接入，暂不加入'}]};
  const html=renderToStaticMarkup(React.createElement(PlanPreview,{proposal:value}));
  assert.ok(html.includes('待创建的关注方案')&&html.includes('暂未加入')&&html.includes('豆瓣'));
  assert.ok(!html.includes('href="https://www.douban.com'));
});
test('editing website updates preview and invalid input does not crash or become a script link',()=>{
  const edited={...proposal,plan:{...plan,websites:['www.example.com','javascript:alert(1)','https://']}};
  const html=renderToStaticMarkup(React.createElement(PlanPreview,{proposal:edited}));
  assert.ok(html.includes('example.com')&&!html.includes('微博公共热榜'));
  assert.ok(!html.includes('href="javascript:')&&html.includes('手动调整的来源'));
});
test('draft API is separate from explicitly confirmed creation',async()=>{
  const {draftPlan,confirmPlan}=load('../src/api/planAssistant.ts');
  const original=globalThis.fetch;const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>proposal};};
  try {
    await draftPlan([{role:'user',content:'我想找教育素材'}],null);
    assert.equal(calls.length,1);
    assert.ok(calls[0].url.endsWith('/research-plan-assistant/draft'));
    assert.equal(calls[0].body.confirmed,undefined);
    await confirmPlan(plan);
    assert.ok(calls[1].url.endsWith('/research-plan-assistant/create'));
    assert.equal(calls[1].body.confirmed,true);
    assert.deepEqual(calls[1].body.plan,plan);
  }finally{globalThis.fetch=original;}
});
test('long conversations retain the original goal and the latest source approval',()=>{
  const {conversationForRequest}=load('../src/api/planAssistant.ts');
  const first={role:'user',content:'研究家庭教育，为视频号寻找素材，优先知乎和豆瓣'};
  const history=[first,...Array.from({length:18},(_,index)=>({role:index%2?'user':'assistant',content:'中间讨论'.repeat(220)})),
    {role:'assistant',content:'是否允许补充微博和B站？'},{role:'user',content:'允许'}];
  const bounded=conversationForRequest(history);
  assert.deepEqual(bounded[0],first);
  assert.equal(bounded.at(-1).content,'允许');
  assert.equal(bounded.at(-2).content,'是否允许补充微博和B站？');
  assert.ok(bounded.length<=10&&bounded.reduce((n,row)=>n+row.content.length,0)<=12000);
});
test('current tab preserves unfinished planning and clears it on reset',()=>{
  const {readAssistantSession,saveAssistantSession,clearAssistantSession}=load('../src/api/assistantSession.ts');
  const original=globalThis.window;const store=new Map();
  globalThis.window={sessionStorage:{getItem:key=>store.get(key)??null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)}};
  try {
    assert.equal(readAssistantSession(),null);
    const state={messages:[{role:'user',content:'教育素材方向'},{role:'assistant',content:'已整理草案'}],proposal,draft:plan,input:'允许',topicText:plan.topics.join('\n'),websiteText:plan.websites.join('\n')};
    saveAssistantSession(state);
    assert.deepEqual(readAssistantSession(),state);
    saveAssistantSession({...state,messages:[...state.messages,{role:'user',content:'请改成别的方向'}]});
    assert.equal(readAssistantSession().proposal,null);
    clearAssistantSession();assert.equal(readAssistantSession(),null);
    store.set('dsih.plan-assistant.session.v1','bad JSON');assert.equal(readAssistantSession(),null);
  }finally{if(original===undefined)delete globalThis.window;else globalThis.window=original;}
});
