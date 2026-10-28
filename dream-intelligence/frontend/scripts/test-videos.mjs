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
const {VideoGallery,VideoResults,VideoScheduleSettings,VideoSearchDetails}=load('../src/pages/VideoResults.tsx');
const row={id:1,external_id:'abcdefghijk',title:'Original video',title_zh:'动物互助',summary_zh:'标题提到动物互动，实际画面仍需观看确认。',
  category:'动物互助与救援',channel:'Public channel',url:'https://www.youtube.com/watch?v=abcdefghijk',
  thumbnail_url:'https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg',published_at:'2026-10-24T00:00:00Z',favorite:true};

test('video reference preserves source Chinese metadata and evidence boundary',()=>{
  const html=renderToStaticMarkup(React.createElement(VideoGallery,{rows:[row],onFavorite:()=>{},onPreview:()=>{}}));
  assert.ok(html.includes('动物互助')&&html.includes('未观看完整视频')&&html.includes('Public channel'));
  assert.ok(html.includes('2026/10/24 08:00:00')&&html.includes('北京时间'));
  assert.ok(html.includes('已收藏')&&html.includes('YouTube 原视频')&&html.includes('▶ 预览视频'));
  assert.ok(!html.includes('<iframe')&&!html.includes('下载'));
});
test('untranslated video is labelled pending rather than fake Chinese analysis',()=>{
  const html=renderToStaticMarkup(React.createElement(VideoGallery,{rows:[{...row,title_zh:null,summary_zh:null}],onFavorite:()=>{},onPreview:()=>{}}));
  assert.ok(html.includes('Original video')&&html.includes('中文整理尚未完成'));
});
test('search explanation displays actual coverage and does not invent legacy provenance',()=>{
  const report={candidate_count:40,candidate_channel_count:20,selected_count:12,selected_channel_count:10,max_per_channel:2,
    queries:[{topic:'animal rescue 动物救援',query:'animal rescue',order:'relevance',returned:10,status:'OK'}]};
  const html=renderToStaticMarkup(React.createElement(VideoSearchDetails,{report}));
  assert.ok(html.includes('40 个候选 / 20 个频道')&&html.includes('12 条 / 10 个频道'));
  assert.ok(html.includes('animal rescue')&&html.includes('按相关度')&&html.includes('原话题'));
  assert.ok(html.includes('同频道最多 2 条'));
  const old=renderToStaticMarkup(React.createElement(VideoSearchDetails,{report:null}));
  assert.ok(old.includes('历史结果未记录检索过程')&&!old.includes('40 个候选'));
});
test('empty video library and schedule defaults do not promise active automation',()=>{
  const html=renderToStaticMarkup(React.createElement(VideoResults,{planId:1}));
  assert.ok(html.includes('尚未收集到视频')&&html.includes('近 30 天')&&html.includes('每区先展示两条'));
  const settings=renderToStaticMarkup(React.createElement(VideoScheduleSettings,{planId:1}));
  assert.ok(settings.includes('每天一次')&&settings.includes('每 2 小时')&&!settings.includes('checked=""'));
  assert.ok(settings.includes('保存设置不会立即采集'));
});
test('read and explicit schedule/favorite writes use separate endpoints without collection',async()=>{
  const {listVideos,getVideoSchedule,saveVideoSchedule,favoriteVideo}=load('../src/api/videos.ts');
  const previous=globalThis.fetch;const calls=[];
  try{globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({})};};
    await listVideos(6,true);await getVideoSchedule(6);await saveVideoSchedule(6,false,1440);await favoriteVideo(6,1,true);
    assert.ok(calls[0].url.endsWith('/6/videos?favorites=true')&&!calls[0].options);
    assert.ok(calls[1].url.endsWith('/6/video-schedule')&&!calls[1].options);
    assert.deepEqual(JSON.parse(calls[2].options.body),{enabled:false,interval_minutes:1440});
    assert.equal(calls[3].options.method,'POST');assert.ok(calls.every(call=>!call.url.endsWith('/run')));
  }finally{globalThis.fetch=previous;}
});
