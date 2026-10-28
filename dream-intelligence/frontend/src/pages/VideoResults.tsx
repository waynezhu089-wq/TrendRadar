import { useEffect,useState } from 'react';
import { listVideos,getVideoSchedule,saveVideoSchedule,favoriteVideo,type VideoReference,type VideoSchedule } from '../api/videos';
import type {ResearchRun} from '../api/research';

const date=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
export function VideoScheduleSettings({planId}:{planId:number}) {
  const [data,setData]=useState<VideoSchedule|null>(null);
  const [enabled,setEnabled]=useState(false),[minutes,setMinutes]=useState(1440);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{let active=true;getVideoSchedule(planId).then(value=>{if(active){setData(value);setEnabled(value.enabled);setMinutes(value.interval_minutes);}})
    .catch(()=>{if(active)setMessage('暂时无法读取定时设置。');});return()=>{active=false;};},[planId]);
  async function save(){setBusy(true);setMessage('');try{
    const result=await saveVideoSchedule(planId,enabled,minutes);setData(result);
    setMessage(result.enabled?(result.scheduler_connected&&result.scheduler_configured?'定时收集已设置。':'设置已保存，等待定时服务加载新功能与接口配置。'):'已关闭定时收集。');
  }catch(error){setMessage(error instanceof Error?error.message:'保存未完成。');}finally{setBusy(false);}}
  return <details className="video-schedule"><summary>定时收集设置</summary>
    <p className="notice">保存设置不会立即采集。通常在到期后约 5 分钟内执行，繁忙或电脑休眠时会延后；电脑需开机且服务运行。</p>
    {data&&!data.configured&&<p className="notice">YouTube 接口尚未配置。需要在本机设置 DSIH_YOUTUBE_API_KEY；不要在页面或聊天里填写密钥。</p>}
    <div className="research-actions"><label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>自动收集</label>
      <label>收集频率<select value={minutes} onChange={e=>setMinutes(Number(e.target.value))}>
        {(data?.interval_options??[120,360,720,1440]).map(value=><option key={value} value={value}>{value===1440?'每天一次':`每 ${value/60} 小时`}</option>)}</select></label>
      <button type="button" disabled={busy||!data} onClick={()=>void save()}>保存定时设置</button></div>
    {data?.enabled&&<p className="notice">{data.scheduler_connected&&data.scheduler_configured?'定时服务已连接':'定时服务尚未就绪，当前不会自动执行'} · 下次计划：{data.next_run_at?`${date(data.next_run_at)}（北京时间）`:'尚未安排'}</p>}
    {message&&<p role="status" className="notice">{message}</p>}</details>;
}

export function VideoGallery({rows,onFavorite,onPreview,busy=false}:{rows:VideoReference[];
  onFavorite:(row:VideoReference)=>void;onPreview:(row:VideoReference)=>void;busy?:boolean}) {
  return <div className="image-reference-grid">{rows.map(row=><article className="image-reference-card" key={row.id}>
    <button className="video-preview" type="button" onClick={()=>onPreview(row)} aria-label={`预览：${row.title_zh??row.title}`}>
      <img src={row.thumbnail_url} alt={row.title_zh??row.title} loading="lazy" referrerPolicy="no-referrer"/><span>▶ 预览视频</span></button>
    <div className="image-reference-body"><p className="notice">{row.channel} · {date(row.published_at)}（北京时间）</p>
      <h4>{row.title_zh??row.title}</h4><p>{row.summary_zh??'原始条目已保存，中文整理尚未完成。'}</p>
      <p className="notice">依据：标题与简介 · 未观看完整视频</p><div className="research-actions">
        <button type="button" aria-pressed={row.favorite} disabled={busy} onClick={()=>onFavorite(row)}>{row.favorite?'已收藏':'收藏'}</button>
        <a href={row.url} target="_blank" rel="noopener noreferrer">YouTube 原视频 ↗</a></div></div></article>)}</div>;
}

function VideoRegion({category,rows,onFavorite,onPreview,busy}:{category:string;rows:VideoReference[];
  onFavorite:(row:VideoReference)=>void;onPreview:(row:VideoReference)=>void;busy:boolean}){
  const [expanded,setExpanded]=useState(false);
  return <section className="visual-reference-region"><header><span className="eyebrow">{rows.length} 条视频</span><h3>{category}</h3></header>
    <VideoGallery rows={expanded?rows:rows.slice(0,2)} onFavorite={onFavorite} onPreview={onPreview} busy={busy}/>
    {rows.length>2&&<button className="visual-expand" type="button" onClick={()=>setExpanded(!expanded)}>{expanded?'收起本区':`展开其余 ${rows.length-2} 条`}</button>}</section>;
}

export function VideoSearchDetails({report}:{report:ResearchRun['video_search']}) {
  if(!report)return <p className="notice">此历史结果未记录检索过程；新一轮采集后可查看检索词与来源分布。</p>;
  return <details className="research-evidence"><summary>本次检索：{report.candidate_count} 个候选 / {report.candidate_channel_count} 个频道 → 入选 {report.selected_count} 条 / {report.selected_channel_count} 个频道</summary>
    <p className="notice">每次入选同频道最多 {report.max_per_channel} 条，多个话题轮流取样。数量不足时保留真实结果，不保证一定找到多个来源。历史视频和收藏不会因此删除。</p>
    <ul>{report.queries.map((row,index)=><li key={index}>{row.query} · {row.order==='relevance'?'按相关度':'按时间'} · {row.status==='OK'?`${row.returned} 个候选`:'未完成'}{row.query!==row.topic?`（原话题：${row.topic}）`:''}</li>)}</ul></details>;
}

export function VideoResults({planId,revision=0,report}:{planId:number;revision?:number;report?:ResearchRun['video_search']}) {
  const [rows,setRows]=useState<VideoReference[]>([]),[favorites,setFavorites]=useState(false);
  const [preview,setPreview]=useState<VideoReference|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let active=true;listVideos(planId,favorites).then(value=>{if(active){setRows(value);setError('');}})
    .catch(()=>{if(active)setError('暂时无法读取视频库。');});return()=>{active=false;};},[planId,revision,favorites]);
  async function toggle(row:VideoReference){setBusy(true);setError('');try{await favoriteVideo(planId,row.id,!row.favorite);
    setRows(current=>current.map(value=>value.id===row.id?{...value,favorite:!row.favorite}:value).filter(value=>!favorites||value.favorite));
  }catch(reason){setError(reason instanceof Error?reason.message:'收藏未完成。');}finally{setBusy(false);}}
  const sorted=[...rows].sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at)||b.id-a.id);
  const categories=[...new Set(sorted.map(row=>row.category))];
  return <section className="video-results" aria-label="视频灵感库">
    <div className="section-heading"><div><span className="eyebrow">YouTube · 视频灵感</span><h2>按题材发现值得收藏的视频</h2></div>
      <button type="button" aria-pressed={favorites} onClick={()=>setFavorites(!favorites)}>{favorites?'全部视频':'本方案收藏'}</button></div>
    <p className="notice">展示最近 100 条，按发布时间从新到旧排列，每区先展示两条。每话题读取最多 10 个近 30 天候选，多话题均衡选入最多12条，每频道每次最多2条；分类与中文简介依据标题和简介，未观看完整视频。</p>
    <VideoSearchDetails report={report}/>
    {error&&<p role="alert">{error}</p>}
    {preview&&<div className="video-player"><button type="button" onClick={()=>setPreview(null)}>关闭预览</button>
      <iframe title={preview.title_zh??preview.title} src={`https://www.youtube-nocookie.com/embed/${preview.external_id}`} allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/>
      <p className="notice">使用 YouTube 播放器预览，部分视频可能不允许嵌入；可打开原视频。</p></div>}
    {categories.map(category=><VideoRegion key={category} category={category} rows={sorted.filter(row=>row.category===category)}
      onFavorite={row=>void toggle(row)} onPreview={setPreview} busy={busy}/>)}
    {!rows.length&&<p className="research-empty">{favorites?'还没有收藏视频。':'尚未收集到视频。配置 YouTube 接口后可点击“现在运行”，也可在设置中开启定时收集。'}</p>}
  </section>;
}
