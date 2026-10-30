import { useEffect, useState, type FormEvent } from 'react';
import { createResearchPlan, disableResearchPlan, listResearchPlans, listResearchRuns,
  runResearchPlan, analyzeResearchRun, openDoubanLogin, updateImageSources, type ResearchPlan, type ResearchRun } from '../api/research';
import { ResearchResults } from './ResearchResults';
import { PlanAssistant } from './PlanAssistant';
import { ImageResults } from './ImageResults';
import { TiboUpdates } from './TiboUpdates';
import { VideoResults,VideoScheduleSettings } from './VideoResults';
import {listSourceConnections,savePlanSourceBindings,type SourceBinding,type SourceConnection} from '../api/sourceConnections';

function lines(value: string): string[] {
  return value.split(/[\n,，]+/).map(part => part.trim()).filter(Boolean);
}

function issueLabel(reason: string): string {
  if (reason === 'ZhihuLoginRequired') return '请先在 DSIH 专用浏览器登录知乎';
  if (reason === 'ZhihuAccessBlocked') return '知乎拒绝本次自动采集（HTTP 403）';
  if (reason === 'ZhihuBrowserUnavailable') return '专用浏览器不可用，请确认登录窗口已关闭';
  const bili: Record<string, string> = {
    SOURCE_AUTH_MISSING:'来源接口缺少本机凭据变量，请配置并重新加载 API',
    SOURCE_DISABLED:'该来源接口已停用，请调整方案来源',
    SOURCE_ACCESS_DENIED:'来源接口拒绝访问，请检查凭据或接口权限；本次已停止该主机的请求',
    SOURCE_RATE_LIMITED:'来源接口已限流，本次已停止该主机的请求',
    SOURCE_ACCESS_STOPPED:'同一主机此前已拒绝访问或限流，本次未继续请求',
    SOURCE_FORMAT_CHANGED:'来源返回结构与字段映射不符，请编辑接口配置',
    SOURCE_FORMAT_OR_ADDRESS_INVALID:'来源地址或返回格式不可用，请检查接口配置',
    SOURCE_NETWORK_FAILED:'无法连接来源接口，本次未取得结果',
    SOURCE_TIMEOUT:'来源接口超时，本次已停止请求',
    SOURCE_REDIRECT_REJECTED:'来源发生重定向，请核查实际接口地址后重新配置',
    SOURCE_HTTP_FAILED:'来源接口返回失败，本次未取得结果',
    SOURCE_RESPONSE_TOO_LARGE:'来源返回超过读取上限，请减少返回字段或条数',
    SOURCE_QUERY_TOO_LONG:'合并检索词过长，请为接口填写一个不超过 256 字的检索式',
    SOURCE_COLLECTION_FAILED:'来源采集未完成，已有结果保留',
    ImageSourceUnavailable: '图片检索来源暂时不可用或已限流，请稍后再试',
    IMAGE_SOURCE_TIMEOUT: '图片来源响应超时，本次已停止请求；这不是没有相关图片，请稍后重试',
    IMAGE_SOURCE_RATE_LIMITED: '图片来源暂时限流，本次已停止请求，请稍后再试',
    IMAGE_SOURCE_REJECTED: '图片来源拒绝了本次请求，本次已停止，请检查来源服务状态',
    IMAGE_SOURCE_NETWORK_ERROR: '无法连接图片来源，请检查网络后重试',
    IMAGE_SOURCE_FORMAT_CHANGED: '图片来源页面结构发生变化，暂时未能读取预览',
    IMAGE_QUERY_ANALYSIS_FAILED: '未能生成检索词，已按原话题尝试检索；可检查模型后重新分析',
    IMAGE_ANALYSIS_FAILED: '候选图片已保存，用途分析未完成，可点击“分析已有结果”重试',
    IMAGE_COLLECTION_FAILED: '图片收集未完成，请稍后重试',
    DoubanLoginRequired: '请点击“登录豆瓣”，在专用 Chrome 窗口登录后关闭该窗口，再运行方案',
    DoubanAccessBlocked: '豆瓣要求验证或限制访问，本次已停止继续请求；请在专用窗口查看',
    DoubanBrowserUnavailable: '豆瓣专用浏览器不可用，请确认 Chrome 已安装、专用窗口已关闭',
    DoubanBusy: '豆瓣专用浏览器正被使用，请关闭登录窗口或稍后重试',
    DoubanPageUnavailable: '豆瓣部分评论页面未能读取，已保留成功取得的资料',
    DoubanUnsupportedPage: '豆瓣目前只支持图书、电影首页搜索或具体作品条目，不支持小组和日记',
    DoubanTimeout: '豆瓣读取已超时，已停止继续请求并保留取得的资料',
    BilibiliUnavailable: '本机 B 站采集环境未就绪',
    BilibiliLoginRequired: 'B 站登录已失效，请先在专用浏览器重新登录',
    BilibiliBusy: 'B 站专用浏览器正在被另一项研究使用，请稍后重试',
    BilibiliTimeout: 'B 站采集超时，已停止本次采集',
    BilibiliCollectionFailed: 'B 站采集失败，请确认专用浏览器已关闭后重试',
    SUMMARY_FAILED: '汇总未通过校验，原始条目已保留',
    WeiboHotlistUnavailable: '微博公共热榜暂时不可用，请稍后重试',
    WeiboTopicSelectionFailed: '微博话题筛选未完成，热榜原始资料已保存；请检查模型配置后重试',
  };
  if (bili[reason]) return bili[reason];
  return reason;
}

const runLabels: Record<string, string> = { RUNNING: '正在运行', COMPLETED: '已完成',
  NO_MATCHES: '暂无匹配', PARTIAL: '部分完成', FAILED: '未完成', SUMMARY_FAILED: '资料已保存，分析未完成' };

const videoErrors:Record<string,string>={YOUTUBE_NOT_CONFIGURED:'YouTube 接口尚未配置',
  YOUTUBE_HTTP_403:'YouTube 权限或配额不足，本次已停止请求',YOUTUBE_HTTP_401:'YouTube 密钥未通过验证',
  YOUTUBE_HTTP_429:'YouTube 暂时限流',YOUTUBE_REQUEST_FAILED:'YouTube 连接失败，请检查本机网络',
  VIDEO_ORGANIZATION_FAILED:'视频已保存，中文整理未完成；后续再次收集到这些条目时会重试整理',
  VIDEO_COLLECTION_FAILED:'视频收集未完成，已保存的数据保留',VIDEO_INTERRUPTED:'上次运行曾中断'};

const imageSources=[
  {url:'https://film-grab.com/',name:'FilmGrab · 电影画面',scope:'按片名或主创寻找画面参考，保留预览与原链接。'},
  {url:'https://openverse.org/',name:'Openverse · 开放许可图片',scope:'寻找场景、物件等图片，保留作者和许可信息。'},
];
export function ConfiguredSourcePicker({connections,bindings,onChange}:{connections:SourceConnection[];bindings:SourceBinding[];onChange:(rows:SourceBinding[])=>void}) {
  return <fieldset className="configured-source-picker"><legend>已配置的来源接口</legend>
    {!connections.length&&<p className="notice">还没有来源接口。<a href="/settings?tab=sources">添加 GitHub 或其他接口 →</a></p>}
    {connections.map(source=>{const binding=bindings.find(row=>row.connection_id===source.id);
      return <div className="configured-source-choice" key={source.id}><label className="source-check"><input type="checkbox" checked={Boolean(binding)}
        disabled={!binding&&!source.ready} onChange={event=>onChange(event.target.checked?[...bindings,{connection_id:source.id,query:'',sort:source.default_sort,limit:Math.min(6,source.max_results)}]:bindings.filter(row=>row.connection_id!==source.id))}/>
        {source.name}{!source.enabled?'（已停用）':!source.ready?'（缺少凭据）':''}</label>
        {binding&&<div className="source-binding-options"><label>检索式（留空使用关注话题）<input maxLength={256} value={binding.query}
          onChange={event=>onChange(bindings.map(row=>row===binding?{...row,query:event.target.value}:row))}/></label>
          <label>排序<select value={binding.sort} onChange={event=>onChange(bindings.map(row=>row===binding?{...row,sort:event.target.value}:row))}>
            <option value="">接口默认</option>{source.sort_values.map(value=><option key={value} value={value}>{value==='stars'?'Star 数从高到低':value==='updated'?'最近更新':value}</option>)}</select></label>
          <label>最多条数<input type="number" min={1} max={source.max_results} required value={binding.limit}
            onChange={event=>onChange(bindings.map(row=>row===binding?{...row,limit:Number(event.target.value)}:row))}/></label></div>}
      </div>;
    })}<p className="notice">接口与下方网站合计最多 5 个。保存不会运行采集。</p>
  </fieldset>;
}

function PlanSourceEditor({plan,connections,onSaved}:{plan:ResearchPlan;connections:SourceConnection[];onSaved:(plan:ResearchPlan)=>void}) {
  const [bindings,setBindings]=useState(plan.source_bindings??[]),[busy,setBusy]=useState(false),[error,setError]=useState('');
  return <details className="source-binding-editor"><summary>调整来源接口</summary><ConfiguredSourcePicker connections={connections} bindings={bindings} onChange={setBindings}/>
    <button type="button" disabled={busy} onClick={()=>{setBusy(true);setError('');void savePlanSourceBindings(plan.id,bindings).then(onSaved)
      .catch(reason=>setError(reason instanceof Error?reason.message:'未保存。')).finally(()=>setBusy(false));}}>保存来源设置</button>
    <p className="notice">下次手动运行时生效，历史检索记录保留。</p>{error&&<p role="alert" className="feedback-error">{error}</p>}</details>;
}
export function ImageSourcePicker({selected,onChange,disabled=false}:{selected:string[];
  onChange:(values:string[])=>void;disabled?:boolean}) {
  return <fieldset className="image-source-picker"><legend>参考来源（至少一个）</legend>
    {imageSources.map(source=><label className="image-source-choice" key={source.url}>
      <input type="checkbox" checked={selected.includes(source.url)} disabled={disabled}
        onChange={event=>onChange(event.target.checked ? [...selected,source.url] : selected.filter(url=>url!==source.url))}/>
      <span><strong>{source.name}</strong><small>{source.scope}</small></span></label>)}
    <p className="notice">接受带水印的公开预览，保留原有水印。ArtStation 与花瓣暂因访问限制未接入。</p>
  </fieldset>;
}
export function ImageSourceEditor({plan,onSaved}:{plan:ResearchPlan;onSaved:(plan:ResearchPlan)=>void}) {
  const [selected,setSelected]=useState(plan.websites);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState('');
  const [error,setError]=useState('');
  async function save() {
    setBusy(true);setError('');setNotice('');
    try {onSaved(await updateImageSources(plan.id,selected));setNotice('来源已保存，下次运行生效。');}
    catch(reason){setError(reason instanceof Error ? reason.message : '来源未保存。');}
    finally {setBusy(false);}
  }
  return <details className="image-source-editor"><summary>调整参考来源</summary>
    <ImageSourcePicker selected={selected} onChange={setSelected} disabled={busy}/>
    <p className="notice">保存不会采集或调用模型，历史结果保留。若目的要求开放许可，新增来源仍需符合这个要求。</p>
    <button type="button" disabled={busy || selected.length===0} onClick={()=>void save()}>{busy ? '保存中…' : '保存来源'}</button>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="feedback-error">{error}</p>}
  </details>;
}

export function Research({ settings = false }: { settings?: boolean }) {
  const [plans, setPlans] = useState<ResearchPlan[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [runs, setRuns] = useState<Record<number, ResearchRun[]>>({});
  const [name, setName] = useState('');
  const [topics, setTopics] = useState('');
  const [websites, setWebsites] = useState('');
  const [purpose, setPurpose] = useState('');
  const [connections,setConnections]=useState<SourceConnection[]>([]);
  const [sourceBindings,setSourceBindings]=useState<SourceBinding[]>([]);
  const [collectionType, setCollectionType] = useState<'research' | 'images' | 'videos'>('research');
  const [selectedImageSources,setSelectedImageSources]=useState(imageSources.map(source=>source.url));
  const [busy, setBusy] = useState<number | 'create' | null>(null);
  const [error, setError] = useState('');
  const [showAssistant, setShowAssistant] = useState(() => settings && typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('assistant') === '1');
  const [savedNotice, setSavedNotice] = useState('');
  const [tiboSelected, setTiboSelected] = useState(() => !settings && typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('subscription') === 'tibo');

  useEffect(() => {
    const controller = new AbortController();
    listSourceConnections(controller.signal).then(setConnections).catch(()=>{if(!controller.signal.aborted)setError('来源接口未能加载，请检查 API。');});
    listResearchPlans(controller.signal).then(async rows => {
      setPlans(rows);
      const requestedId = Number(new URLSearchParams(window.location.search).get('plan'));
      setSelectedId(rows.find(row => row.id === requestedId)?.id ?? rows[0]?.id ?? null);
      if (settings) return;
      const histories = await Promise.all(rows.map(row =>
        listResearchRuns(row.id, controller.signal).then(value => [row.id, value] as const)));
      if (!controller.signal.aborted) setRuns(Object.fromEntries(histories));
    }).catch(() => { if (!controller.signal.aborted) setError('无法加载关注方案，请检查 API。'); });
    return () => controller.abort();
  }, [settings]);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('');
    const topicList = lines(topics);
    const siteList = collectionType === 'videos' ? ['https://www.youtube.com/'] : collectionType === 'images' ? selectedImageSources : lines(websites);
    if(collectionType==='images' && siteList.length===0){setError('请至少选择一个参考来源。');return;}
    if (topicList.length > 8) { setError(`关注话题最多 8 个，当前填写了 ${topicList.length} 个。`); return; }
    if (siteList.length > 5) { setError(`目标网站最多 5 个，当前填写了 ${siteList.length} 个。`); return; }
    if(collectionType==='research'&&siteList.length+sourceBindings.length>5){setError('来源接口与目标网站合计最多 5 个。');return;}
    setBusy('create');
    try {
      const created = await createResearchPlan({ name, topics: topicList,
        websites: siteList, purpose, collection_type: collectionType,
        ...(collectionType==='research'&&sourceBindings.length?{source_bindings:sourceBindings}:{}) });
      setPlans(current => [created, ...current]);
      setSelectedId(created.id);
      setShowAssistant(false);
      setName(''); setTopics(''); setWebsites(''); setPurpose(''); setCollectionType('research');
      setSourceBindings([]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : '方案保存失败，请重试。'); }
    finally { setBusy(null); }
  }

  async function onRun(plan: ResearchPlan) {
    setBusy(plan.id); setError('');
    try {
      const result = await runResearchPlan(plan.id);
      setRuns(current => ({ ...current, [plan.id]: [result, ...(current[plan.id] ?? [])].slice(0, 10) }));
    } catch (reason) { setError(reason instanceof Error?reason.message:`“${plan.name}”运行失败，请稍后重试。`); }
    finally { setBusy(null); }
  }

  async function onDisable(plan: ResearchPlan) {
    setBusy(plan.id); setError('');
    try { await disableResearchPlan(plan.id); setPlans(current => current.filter(row => row.id !== plan.id)); }
    catch { setError(`无法停用“${plan.name}”。`); }
    finally { setBusy(null); }
  }

  async function onAnalyze(plan: ResearchPlan, run: ResearchRun) {
    setBusy(plan.id); setError('');
    try {
      const result = await analyzeResearchRun(plan.id, run.id);
      setRuns(current => ({ ...current, [plan.id]: (current[plan.id] ?? []).map(row => row.id === result.id ? result : row) }));
    } catch { setError('分析未完成，已有结果已保留。请稍后重试。'); }
    finally { setBusy(null); }
  }
  async function onDoubanLogin() {
    setError('');
    try {
      await openDoubanLogin();
      setSavedNotice('请在专用 Chrome 窗口亲自登录豆瓣，完成后关闭该窗口，再点击“现在运行”。无需发送密码或 Cookie。');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '无法打开豆瓣登录窗口。'); }
  }
  const activePlan = plans.find(plan => plan.id === selectedId) ?? plans[0];
  const latest = activePlan ? runs[activePlan.id]?.[0] : undefined;

  const Container = settings ? 'div' : 'main';
  return <Container className={`research-page${settings ? ' research-settings' : ''}`}>
    {!settings && <><header><div className="brand">Dream Intelligence</div>
      <p className="notice">按自己的话题、公开网站和目的，建立一次次可追溯的研究。</p></header>
    <h1>研究工作台</h1>
    <p className="notice">深入查看跨日期的专题证据与综合分析。<a href="/settings">管理议题与来源 →</a>
      <a className="assistant-entry" href="/settings?assistant=1">让助手建立方案 →</a></p></>}
    <div className="research-workspace"><aside className="research-sidebar" aria-label="研究方案">
    <h2>我的关注方案 <small>{plans.length}</small></h2>
    <div className="plan-list">{plans.map(plan => <button type="button" key={plan.id}
      aria-pressed={!tiboSelected && activePlan?.id === plan.id} onClick={() => { setTiboSelected(false); setSelectedId(plan.id); if (settings) setShowAssistant(false); }}>
      <strong>{plan.name}</strong><span>{plan.collection_type === 'videos'?'视频灵感 · ':plan.collection_type === 'images' ? '图片素材 · ' : ''}{plan.topics.join(' · ')}</span>
    </button>)}</div>
    {!settings && <div className="plan-list tibo-subscription-entry"><h3>自动订阅</h3>
      <button type="button" aria-pressed={tiboSelected} onClick={()=>setTiboSelected(true)}>
        <strong>Tibo · Codex 动态</strong><span>中文更新 · 额度重置提醒</span></button></div>}
    {settings && <button type="button" className="assistant-launch" onClick={() => { setShowAssistant(true); setSavedNotice(''); }}>和助手建立方案</button>}
    {settings && <details className="new-plan"><summary>手动填写关注方案</summary>
    <form className="research-form" onSubmit={event => void onCreate(event)}>
      <label>收集类型<select value={collectionType} onChange={event => setCollectionType(event.target.value as 'research' | 'images' | 'videos')}>
        <option value="research">资讯研究</option><option value="images">图片参考</option><option value="videos">YouTube 视频灵感</option></select></label>
      <label>方案名称<input value={name} onChange={event => setName(event.target.value)} maxLength={100} required /></label>
      <label>关注话题（每行一个，最多 8 个）<textarea value={topics} onChange={event => setTopics(event.target.value)} required rows={3} /></label>
      {collectionType==='videos'?<div><p className="notice">来源：YouTube。可自行填写关键词，或先选一个方向，再补充话题与用途。</p>
        <div className="research-actions">{[['动物趣事','funny animals'],['动物互助与救援','animals helping each other'],['人类搞笑','funny human moments'],['温暖互助','acts of kindness']].map(([label,query])=>
          <button type="button" key={label} onClick={()=>{if(!lines(topics).includes(query))setTopics(current=>current?`${current}\n${query}`:query);}}>{label}</button>)}</div>
        <p className="notice">英文关键词有助于寻找海外内容；结果会整理成中文。保存链接和封面，不自动下载视频。</p></div>:
        collectionType === 'images' ? <ImageSourcePicker selected={selectedImageSources} onChange={setSelectedImageSources}/>
        : <><ConfiguredSourcePicker connections={connections} bindings={sourceBindings} onChange={setSourceBindings}/>
          <label>目标网站网址（已选接口时可留空）<textarea value={websites} onChange={event => setWebsites(event.target.value)} required={!sourceBindings.length} rows={3} placeholder={'www.bilibili.com\nhttps://example.com/feed.xml'} /><span className="notice">直接填写公开域名也可以，保存时会补全 https://。</span></label></>}
      {lines(websites).some(value => /^(?:https?:\/\/)?www\.bilibili\.com(?:\/|$)/i.test(value)) &&
        <p className="notice">B 站方案保存后可点击“现在运行”，每个话题最多读取 3 条视频的标题与简介，可能需要几分钟。需先在本机专用浏览器登录。</p>}
      <label>分析目的<textarea value={purpose} onChange={event => setPurpose(event.target.value)} required minLength={10} maxLength={1000} rows={3} placeholder="例如：跟踪 AI 视频工具，为 Dream Stream 选型提供线索" /></label>
      <button type="submit" disabled={busy !== null}>保存方案</button>
    </form></details>}</aside>
    <div className="research-content">
    {settings && showAssistant && <PlanAssistant onClose={() => setShowAssistant(false)} onCreated={result => {
      setPlans(current => [result.plan, ...current.filter(row => row.id !== result.plan.id)]);
      setSelectedId(result.plan.id); setShowAssistant(false);
      setSavedNotice(result.created ? '方案已创建，可进入研究工作台运行。' : '已找到完全相同的方案，已为你选中。');
    }} />}
    {savedNotice && <p className="assistant-saved" role="status">{savedNotice}</p>}
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {tiboSelected && <TiboUpdates/>}
    {!tiboSelected && !(settings && showAssistant) && (plans.length === 0 ? <p className="research-empty">{settings ? '可让助手整理需求，或在左侧手动填写关注方案。' : <>尚未建立关注方案。<a href="/settings">前往设置</a></>}</p> : [activePlan!].map(plan =>
      <section className="research-plan" key={plan.id}>
        <h3>{plan.name}</h3>
        {plan.collection_type === 'images' && <p className="eyebrow">视频灵感与图片参考 · 先预览，再收藏</p>}
        {plan.collection_type==='videos'&&<p className="eyebrow">YouTube 视频灵感 · 按题材收集、预览与收藏</p>}
        <p><b>话题：</b>{plan.topics.join('、')}</p>
        <p><b>目的：</b>{plan.purpose}</p>
        {plan.source_bindings?.map(binding=><p key={binding.connection_id}><b>来源接口：</b>{connections.find(row=>row.id===binding.connection_id)?.name??`#${binding.connection_id}`} · {binding.query||plan.topics.join(' ')} · {binding.sort||'默认排序'} · 最多 {binding.limit} 条</p>)}
        <p className="research-sites"><b>网站：</b>{plan.websites.map((url, index) =>
          <span key={url}>{index > 0 ? ' · ' : ''}<a href={url} target="_blank" rel="noopener noreferrer">{new URL(url).hostname}</a></span>)}</p>
        {plan.collection_type==='images' && <ImageSourceEditor plan={plan} onSaved={saved=>setPlans(current=>current.map(row=>row.id===saved.id?saved:row))}/>}
        {plan.collection_type==='videos'&&<VideoScheduleSettings key={plan.id} planId={plan.id}/>}
        {settings&&(!plan.collection_type||plan.collection_type==='research')&&<PlanSourceEditor key={plan.id} plan={plan} connections={connections} onSaved={saved=>setPlans(current=>current.map(row=>row.id===saved.id?saved:row))}/>}
        {plan.websites.some(url => ['weibo.com', 'www.weibo.com', 's.weibo.com'].includes(new URL(url).hostname)) &&
          <p className="notice">微博首页、热榜或登录跳转入口会读取 NewsNow 公共热榜，由 agent 按话题和目的筛选最多 12 条。依据仅为标题和链接，未阅读原帖；不会要求登录微博。</p>}
        {plan.websites.some(url => /^(?:www\.|movie\.|book\.)?douban\.com$/.test(new URL(url).hostname)) &&
          <p className="notice">豆瓣仅支持图书、电影评论。建议话题填写具体作品名；每个入口最多读取 2 部作品、每部 3 条短评和 1 篇长评节选。热门评论可能较旧，不代表最新舆情。 <button type="button" disabled={busy !== null} onClick={() => void onDoubanLogin()}>登录豆瓣</button></p>}
        <div className="research-actions">
          {!settings && <button type="button" disabled={busy !== null} onClick={() => void onRun(plan)}>{busy === plan.id ? '正在采集并汇总，可能需要几分钟…' : '现在运行'}</button>}
          {!settings && (latest?.items.length || latest?.images?.length) ? <button type="button" disabled={busy !== null} onClick={() => void onAnalyze(plan, latest!)}>分析已有结果</button> : null}
          {settings && <><a href={`/research?plan=${plan.id}`}>打开研究工作台 →</a><button type="button" disabled={busy !== null} onClick={() => void onDisable(plan)}>停用方案</button></>}
        </div>
        <p className="notice">{plan.collection_type==='videos'?'保存方案不会立即采集。需另行开启定时设置，或在工作台点击“现在运行”；不会发送飞书。':settings ? '保存方案不会自动采集。登录网站需要先在本机专用浏览器登录，再进入 Research 手动运行。' : '“现在运行”会采集新内容；“分析已有结果”只更新保存条目的分类与综合分析。'}</p>
      </section>))}
    {!settings && !tiboSelected && latest && <>
      <div className="research-run-bar"><span>最近结果 #{latest.id} · {runLabels[latest.status] ?? latest.status}</span>
        <span>获取 <b>{latest.received}</b> · 入选 <b>{latest.matched}</b> · <span title="新增保存的原始资料数，可包含未入选专题的热榜候选">新入库 <b>{latest.inserted}</b></span></span></div>
      {latest.errors.length > 0 && <p role="alert" className="feedback-error">{latest.errors.map(error => `${error.website ?? '汇总'}：${videoErrors[error.reason]??issueLabel(error.reason)}`).join('；')}</p>}
      {activePlan?.collection_type==='videos'?null:activePlan?.collection_type === 'images' ? <ImageResults key={latest.id} run={latest} /> : <ResearchResults run={latest} />}
    </>}
    {!settings&&!tiboSelected&&activePlan?.collection_type==='videos'&&<VideoResults key={activePlan.id} planId={activePlan.id} revision={latest?.id} report={latest?.video_search}/>}
    </div></div>
  </Container>;
}
