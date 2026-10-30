import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path, overrides={}) {
const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
}).outputText;
const exports={};new Function('require','exports',code)(name=>overrides[name] ?? require(name),exports);
return exports;
}
const api=load('../src/api/tibo.ts');
const {TiboFeed}=load('../src/pages/TiboUpdates.tsx',{'../api/tibo':api});
const {SubscriptionPreferences}=load('../src/pages/SubscriptionSettings.tsx',{'../api/tibo':api});
const data={account:'thsottiaux',enabled:true,browser_enabled:false,poll_minutes:5,last_polled_at:null,last_success_at:null,errors:[],posts:[{
  id:1,url:'https://x.com/thsottiaux/status/123',title_zh:'额度重置预告',translation_zh:'将于明天推出。',original_text:'Landing tomorrow.',
  reason_zh:'社区归类，原帖上下文待核对。',signal:'SCHEDULED_COMMUNITY',signal_label:'社区转录的重置预告',source_kind:'community_x_post',
  source_url:'https://codex-resets.com/',published_at:'2026-10-23T06:00:00Z',reported_at:null,delivery_statuses:['SENT']} ]};
test('Chinese update retains source, original link and scheduled uncertainty',()=>{
  const html=renderToStaticMarkup(React.createElement(TiboFeed,{data}));
  assert.ok(html.includes('将于明天推出')&&html.includes('社区转录的重置预告'));
  assert.ok(html.includes('https://x.com/thsottiaux/status/123')&&html.includes('https://codex-resets.com/'));
  assert.ok(html.includes('北京时间')&&html.includes('飞书已发送')&&html.includes('每 5 分钟'));
});
test('untranslated and uncertain delivery are not presented as a sent Chinese alert',()=>{
  const html=renderToStaticMarkup(React.createElement(TiboFeed,{data:{...data,posts:[{...data.posts[0],title_zh:null,translation_zh:null,delivery_statuses:['UNKNOWN']}]}}));
  assert.ok(html.includes('等待中文整理')&&html.includes('不会自动重复发送'));
  assert.ok(!html.includes('飞书已发送'));
});
test('two-hour subscription label and settings distinguish saved from applied',()=>{
  const feed=renderToStaticMarkup(React.createElement(TiboFeed,{data:{...data,poll_minutes:120}}));
  assert.ok(feed.includes('每 2 小时'));
  const values={enabled:true,poll_minutes:120,interval_options:[30,60,120,240,720,1440],
    applied_poll_minutes:120,next_run_time:'2026-10-23T09:00:00Z',scheduler_connected:true,pending:false};
  const props={data:values,minutes:120,onChange:()=>{},onSave:()=>{},busy:false};
  const html=renderToStaticMarkup(React.createElement(SubscriptionPreferences,props));
  assert.ok(html.includes('当前生效：每 2 小时')&&html.includes('北京时间')&&html.includes('保存不会立即采集'));
  assert.ok(html.includes('value="120" selected'));
  const pending=renderToStaticMarkup(React.createElement(SubscriptionPreferences,{...props,data:{...values,pending:true,applied_poll_minutes:5}}));
  assert.ok(pending.includes('等待调度服务应用')&&!pending.includes('当前生效'));
});
test('preference save sends only the selected interval to the backend',async()=>{
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async(url,options)=>{
      assert.equal(url,'http://127.0.0.1:8000/api/v1/tibo-monitor/settings');
      assert.equal(options.method,'POST');assert.deepEqual(JSON.parse(options.body),{poll_minutes:120});
      return {ok:true,json:async()=>({poll_minutes:120})};
    };
    assert.equal((await api.saveTiboSettings(120)).poll_minutes,120);
  } finally {globalThis.fetch=previous;}
});
test('settings deep link opens the automatic subscription tab',()=>{
  const previous=globalThis.window;
  try {
    globalThis.window={location:{pathname:'/settings',search:'?tab=subscriptions'}};
    const {Settings}=load('../src/pages/Settings.tsx',{
      './Research':{Research:()=>React.createElement('p',{},'Topic panel')},
      './Watchlist':{Watchlist:()=>React.createElement('p',{},'Watchlist panel')},
      './SubscriptionSettings':{SubscriptionSettings:()=>React.createElement('p',{},'Subscription panel')},
      './SourceConnections':{SourceConnections:()=>null},
    });
    const html=renderToStaticMarkup(React.createElement(Settings));
    assert.match(html,/aria-selected="true"[^>]*id="tab-subscriptions"/);
    assert.ok(html.includes('Subscription panel')&&!html.includes('Topic panel'));
  } finally {globalThis.window=previous;}
});
