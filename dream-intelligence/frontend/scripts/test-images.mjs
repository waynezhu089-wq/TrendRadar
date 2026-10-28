import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(path,overrides={}) {
  const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
    compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  }).outputText;
  const exports={};
  new Function('require','exports',code)(name=>name in overrides ? overrides[name] : name.startsWith('../api/') ? {} : require(name),exports);
  return exports;
}
const {ImageGallery,ImageResults,ImageEmptyState,VisualReferenceGroups}=load('../src/pages/ImageResults.tsx');
const image={id:1,title:'Misty forest',source_url:'https://example.com/original',image_url:'https://example.com/a.jpg',
  thumbnail_url:'https://example.com/thumb.jpg',creator:'Photographer',license:'by',license_url:'https://creativecommons.org/licenses/by/4.0/',
  attribution:'Photographer, CC BY 4.0',width:1920,height:1080,favorite:true,downloaded:false,recommended:true,
  reason:'标签与森林题材相关',usage_notes:'构图需看图确认'};

test('gallery preserves original source attribution and separates metadata advice from visual assessment',()=>{
  const html=renderToStaticMarkup(React.createElement(ImageGallery,{images:[image]}));
  assert.ok(html.includes('loading="lazy"')&&html.includes('referrerPolicy="no-referrer"'));
  assert.ok(html.includes('1920 × 1080')&&html.includes('Photographer, CC BY 4.0'));
  assert.ok(html.includes('元数据判断')&&html.includes('构图需看图确认'));
  assert.ok(html.includes('已收藏')&&html.includes('下载原图'));
  assert.ok(html.includes('href="https://example.com/original"'));
});
test('saved candidates remain visible when model selection fails',()=>{
  const html=renderToStaticMarkup(React.createElement(ImageResults,{run:{images:[{...image,recommended:false,reason:''}],image_summary:null}}));
  assert.ok(html.includes('Misty forest')&&html.includes('尚未进行看图判断'));
  assert.ok(!html.includes('这些图片线索可以怎样用'));
});
test('image source appears in a typed plan preview',()=>{
  const {PlanPreview}=load('../src/pages/PlanAssistant.tsx');
  const html=renderToStaticMarkup(React.createElement(PlanPreview,{proposal:{plan:{name:'Forest',topics:['forest'],purpose:'Scene reference',collection_type:'images',websites:['https://openverse.org/']},sources:[]}}));
  assert.ok(html.includes('图片参考素材')&&!html.includes('<dd>资讯研究</dd>'));
});
test('empty image search explains source scope and distinguishes failure',()=>{
  const empty=renderToStaticMarkup(React.createElement(ImageEmptyState,{run:{status:'NO_MATCHES',errors:[],image_summary:null}}));
  assert.ok(empty.includes('Openverse')&&empty.includes('不代表全网没有')&&empty.includes('历史结果'));
  const failed=renderToStaticMarkup(React.createElement(ImageEmptyState,{run:{status:'FAILED',errors:[{reason:'IMAGE_SOURCE_TIMEOUT'}]}}));
  assert.ok(failed.includes('检索未完成')&&!failed.includes('本次没有返回'));
});
test('factual search report is not presented as agent image analysis',()=>{
  const html=renderToStaticMarkup(React.createElement(ImageResults,{run:{status:'NO_MATCHES',images:[],errors:[],
    image_summary:{kind:'search',overview:'本次未找到候选。',limitations:'实际检索：「wuxia」：0 张可用候选'}}}));
  assert.ok(html.includes('本次检索情况')&&html.includes('实际检索'));
  assert.ok(!html.includes('素材助手')&&!html.includes('这些图片线索可以怎样用'));
});
test('film references retain attribution and are not presented as licensed downloads',()=>{
  const html=renderToStaticMarkup(React.createElement(ImageGallery,{images:[{...image,provider:'filmgrab',license:'',license_url:'',
    title:'Example Film · 参考帧 1',creator:'Director: Example',attribution:'FilmGrab · 原作授权待确认'}]}));
  assert.ok(html.includes('FilmGrab · 电影参考')&&html.includes('原站参考预览')&&html.includes('成片使用授权待确认'));
  assert.ok(!html.includes('下载原图'));
});
test('source picker exposes only available providers and preserves a legacy selection',()=>{
  const {ImageSourcePicker,ImageSourceEditor}=load('../src/pages/Research.tsx',{
    './ResearchResults':{ResearchResults:()=>null},'./PlanAssistant':{PlanAssistant:()=>null},
    './ImageResults':{ImageResults:()=>null},'./TiboUpdates':{TiboUpdates:()=>null},'./VideoResults':{VideoResults:()=>null,VideoScheduleSettings:()=>null}});
  const html=renderToStaticMarkup(React.createElement(ImageSourcePicker,{selected:['https://openverse.org/'],onChange:()=>{}}));
  assert.equal((html.match(/type="checkbox"/g)??[]).length,2);
  assert.equal((html.match(/checked=""/g)??[]).length,1);
  assert.ok(html.includes('电影画面')&&html.includes('带水印')&&html.includes('访问限制未接入'));
  const editor=renderToStaticMarkup(React.createElement(ImageSourceEditor,{plan:{id:4,websites:['https://openverse.org/']},onSaved:()=>{}}));
  assert.ok(editor.includes('调整参考来源')&&editor.includes('保存不会采集或调用模型'));
});
test('source edits send only a supported URL selection without running research',async()=>{
  const {updateImageSources}=load('../src/api/research.ts');
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async(url,options)=>{
      assert.equal(url,'http://127.0.0.1:8000/api/v1/research-plans/4/image-sources');
      assert.equal(options.method,'POST');assert.deepEqual(JSON.parse(options.body),{websites:['https://film-grab.com/']});
      return {ok:true,json:async()=>({id:4,websites:['https://film-grab.com/']})};
    };
    assert.deepEqual((await updateImageSources(4,['https://film-grab.com/'])).websites,['https://film-grab.com/']);
  } finally {globalThis.fetch=previous;}
});

test('pixel observations and category summaries stay separate from weak and unread candidates',()=>{
  const observation={image_id:1,readable:true,description:'蓝色侧光照亮室内走廊',scene:'室内',lighting:'侧光',
    colors:['蓝色'],composition:'透视线引导视线',category:'色彩与氛围',fit:'MATCH',purpose_relevance:'可借鉴城市夜景光色',
    suggestion:'尝试冷暖光对比',uncertainty:'静帧不能确认运镜',watermark:'UNCERTAIN'};
  const report={overview:'归纳实际可见的光色',analyzed_count:2,candidate_count:3,model:'test-qwen',
    analyzed_at:'2026-10-23T08:00:00Z',observations:[observation,{...observation,image_id:2,fit:'NOT_MATCH'}],
    groups:[{category:'色彩与氛围',summary:'共通的侧光与冷色',key_points:['用光分层'],suggested_action:'建立色彩草案',image_ids:[1]}]};
  const html=renderToStaticMarkup(React.createElement(VisualReferenceGroups,{report,
    images:[image,{...image,id:2,title:'Weak'},{...image,id:3,title:'Unread'}]}));
  assert.ok(html.includes('共通的侧光与冷色')&&html.includes('已看图 · 符合用途'));
  assert.ok(html.includes('蓝色侧光照亮室内走廊')&&html.includes('画面分析与用途'));
  assert.ok(html.includes('<summary>与当前用途关联较弱 · 1 张</summary>'));
  assert.ok(html.includes('<summary>尚未完成看图 · 1 张</summary>'));
  assert.ok(html.includes('已分析 2/3 张预览')&&html.includes('北京时间'));
  assert.equal((html.match(/已看图/g)??[]).length,2);
});

test('vision is an explicit post and provider rejection does not expose raw errors',async()=>{
  const {analyzeImageVision,getImageVisionStatus}=load('../src/api/research.ts');
  const previous=globalThis.fetch;let calls=0;
  try {
    globalThis.fetch=async(url,options)=>{
      calls++;
      if(calls===1){assert.ok(url.endsWith('/image-vision/status'));assert.ok(!options.method);
        return {ok:true,json:async()=>({configured:true,model:'test-qwen'})};}
      assert.ok(url.endsWith('/research-plans/5/runs/19/vision'));assert.equal(options.method,'POST');
      return {ok:false,json:async()=>({detail:'VISION_PROVIDER_HTTP_401',raw:'private provider body'})};
    };
    assert.equal((await getImageVisionStatus()).configured,true);
    await assert.rejects(analyzeImageVision(5,19),error=>error.message.includes('接口拒绝')&&!error.message.includes('private'));
    assert.equal(calls,2);
  } finally {globalThis.fetch=previous;}
});
