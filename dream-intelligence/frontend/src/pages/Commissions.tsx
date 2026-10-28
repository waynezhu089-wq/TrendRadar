import { useEffect, useState } from 'react';
import { getCommissions, collectCommissions, type CommissionLead, type CommissionView } from '../api/commissions';

const labels:Record<string,string>={OPEN:'原站招募中',CLOSED:'已停止招募',EXPIRED:'已过截止日',UNKNOWN:'状态待核实',
  OK:'读取成功',PARTIAL:'部分读取',FAILED:'读取失败',COMPLETED:'已完成',RUNNING:'运行中'};
function timeLabel(value:string) {return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});}

export function CommissionCard({row}:{row:CommissionLead}) {
  const old=(Date.now()-Date.parse(row.checked_at))>86400000;
  return <article className="commission-card">
    <div className="commission-meta"><span>{row.source_name}</span><span>{row.source_status_text?`${row.source_status_text} · `:''}{labels[row.status] ?? '状态待核实'}{old?' · 需重新核实':''}</span></div>
    <h3><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title}</a></h3>
    <p className="commission-excerpt">{row.description.slice(0,170)}{row.description.length>170?'…':''}</p>
    <dl className="commission-facts"><div><dt>原帖预算</dt><dd>{row.budget || '未披露'}</dd></div>
      <div><dt>{row.deadline_kind==='REGISTRATION'?'报名截止':row.deadline_kind==='DELIVERY'?'期望完成':'截止日期'}</dt><dd>{row.deadline_at?`${timeLabel(row.deadline_at)}（北京时间）`:row.deadline || '未披露'}</dd></div>
      <div><dt>发布方</dt><dd>{row.publisher || '未披露'}</dd></div>
      <div><dt>发布时间</dt><dd>{row.published_on || '未知'}</dd></div></dl>
    <details><summary>查看需求与大陆相关依据</summary>
      <p className="commission-description">{row.description}</p>
      {row.delivery_deadline&&<p>原帖交付时间：{row.delivery_deadline}</p>}
      <p>{row.region_evidence?`原文线索：“${row.region_evidence}”`:'原帖未明确提供大陆相关依据。'}</p>
      <p className="notice">仅为原帖线索，未核验发布方身份、付款能力或实际所在地。
        {row.confirmed_on && ` 原站最近确认：${row.confirmed_on}。`} 本机核对：{timeLabel(row.checked_at)}（北京时间）。</p>
    </details>
    <a className="commission-original" href={row.url} target="_blank" rel="noopener noreferrer">查看原始需求 →</a>
  </article>;
}

export function CommissionContent({data,scope='mainland',showClosed=false,source='all'}:{data:CommissionView;scope?:string;showClosed?:boolean;source?:string}) {
  const rows=data.leads.filter(row=>(scope==='pending'?row.region==='UNKNOWN':row.region==='MAINLAND_CLUE')
    && (source==='all'||row.source===source) && (showClosed || !['CLOSED','EXPIRED'].includes(row.status)));
  const failedSources=data.latest?.sources?.filter(source=>source.status!=='OK') ?? [];
  return <>
    {failedSources.length>0&&<p role="status" className="notice">本次{failedSources.map(source=>source.name).join('、')}未能完整读取，不能据此判断没有商单。成功取得的资料和历史记录已保留，可展开底部来源结果查看。</p>}
    <p className="notice">{scope==='pending'?'这些需求的大陆归属尚不明确，单独留作核实。':'优先展示原帖提及大陆地区或国内平台的需求；这不等于已核验甲方所在地。'} 按原始发布时间倒序，未知日期排后。</p>
    {!rows.length && <p className="research-empty">{data.leads.length?'当前筛选下没有需求。可查看“归属待核实”或已结束记录。':'尚未收集商单。点击“寻找商单”，读取公开平台的真实需求。'}</p>}
    <div className="commission-zones">{['视频与广告','漫剧与动画','图片与视觉'].map(category=>{
      const selected=rows.filter(row=>row.category===category);
      if(!selected.length)return null;
      return <section className="commission-zone" key={category}><div className="section-heading"><h2>{category}</h2><span>{selected.length} 条线索</span></div>
        <div className="commission-grid">{selected.slice(0,2).map(row=><CommissionCard key={row.id} row={row}/>)}</div>
        {selected.length>2&&<details className="commission-more"><summary>展开其余 {selected.length-2} 条</summary><div className="commission-grid">{selected.slice(2).map(row=><CommissionCard key={row.id} row={row}/>)}</div></details>}
      </section>;
    })}</div>
    {data.latest&&<details className="commission-source-report"><summary>本次来源与读取结果 · {labels[data.latest.status] ?? '状态未知'}</summary>
      <p>新增 {data.latest.inserted ?? 0} · 更新已有 {data.latest.updated ?? 0}。{data.latest.finished_at&&`完成于 ${timeLabel(data.latest.finished_at)}（北京时间）`}</p>
      {data.latest.sources?.map(source=><p key={source.source}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.name}</a>：{labels[source.status]} · 核对 {source.checked} · 保留 {source.accepted}
        {source.errors.length>0&&' · 部分页面未能读取；已有资料保留'}{source.coverage&&<><br/>{source.coverage}</>}</p>)}
    </details>}
  </>;
}

export function Commissions() {
  const [data,setData]=useState<CommissionView|null>(null);
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const [scope,setScope]=useState('mainland');const [showClosed,setShowClosed]=useState(false);
  const [source,setSource]=useState('all');
  useEffect(()=>{const controller=new AbortController();getCommissions(controller.signal).then(setData)
    .catch(()=>{if(!controller.signal.aborted)setError('商单资料无法加载，请检查本地服务。');});return()=>controller.abort();},[]);
  async function collect() {setError('');setBusy(true);try{setData(await collectCommissions());}
    catch(reason){setError(reason instanceof Error?reason.message:'本次读取未完成，已有资料保留。');}finally{setBusy(false);}}
  const scoped=data?.leads.filter(row=>(source==='all'||row.source===source)&&(showClosed||!['CLOSED','EXPIRED'].includes(row.status))) ?? [];
  return <main className="commissions-page"><header className="commission-header"><div><div className="brand">Dream Intelligence · 商业机会</div>
    <h1>大陆 AI 商单</h1><p className="notice">寻找视频、图片、漫剧制作需求，保留预算与原帖，便于你判断是否接洽。</p></div>
    <button type="button" disabled={busy||!data} onClick={()=>void collect()}>{busy?'正在核对公开需求…':'寻找商单'}</button></header>
    <p className="commission-scope">公开来源：{data?.sources.map(row=>row.name).join('、') || '正在读取'}。当前手动更新；猪八戒仅从公开详情及相似需求有限发现，不代表全站搜索。排除明确的海外项目、招聘与承制方自荐。</p>
    <div className="commission-controls"><div className="daily-period"><button type="button" aria-pressed={scope==='mainland'} onClick={()=>setScope('mainland')}>大陆相关{data?` · ${scoped.filter(row=>row.region==='MAINLAND_CLUE').length}`:''}</button>
      <button type="button" aria-pressed={scope==='pending'} onClick={()=>setScope('pending')}>归属待核实{data?` · ${scoped.filter(row=>row.region==='UNKNOWN').length}`:''}</button></div>
      <label className="commission-source-filter">来源 <select value={source} onChange={event=>setSource(event.target.value)}><option value="all">全部来源</option>
        {data?.sources.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label><input type="checkbox" checked={showClosed} onChange={event=>setShowClosed(event.target.checked)}/> 显示已结束与过期</label></div>
    {error&&<p role="alert" className="feedback-error">{error}</p>}
    {data?<CommissionContent data={data} scope={scope} showClosed={showClosed} source={source}/>:<p role="status">正在读取已保存的商单…</p>}
  </main>;
}
