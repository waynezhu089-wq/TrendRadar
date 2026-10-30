import type { ResearchRun } from '../api/research';

type Item = ResearchRun['items'][number];
const timestamp = (item: Item) => item.published_at ? Date.parse(item.published_at) : -Infinity;
const newestFirst = (a: Item, b: Item) => timestamp(b) - timestamp(a) || b.id - a.id;
export function SourceSearchEvidence({reports}:{reports:NonNullable<ResearchRun['source_reports']>}) {
  return <>{reports.map(report=><section className="source-search-evidence" key={report.connection_id}>
    <h3>{report.name} · 检索记录</h3><p>检索式：{report.query} · 排序：{report.sort||'来源默认'} · 请求最多 {report.limit} 条</p>
    <p className="notice">{report.status==='COMPLETED'?`本次取得 ${report.received??0} 条，入选 ${report.selected??0} 条。`:'本次接口未完成，不能视为没有匹配结果。'}{report.incomplete?'来源标记结果不完整。':''}
      {report.observed_at?` 快照时间：${new Date(report.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}（北京时间）。`:''}</p>
    <ol>{report.results.map(row=>{let url:URL|null=null;try{url=new URL(row.url);if(!['https:','http:'].includes(url.protocol)||url.username||url.password)url=null;}catch{url=null;}
      return <li key={row.item_id??row.url}>{url?<a href={url.href} target="_blank" rel="noopener noreferrer">{row.title}</a>:row.title}
        {row.stars!==undefined&&<span> · ★ {row.stars.toLocaleString('zh-CN')}</span>}<p>{row.content}</p></li>;
    })}</ol><p className="notice">{report.scope} 排名只针对本次检索式，star 是当次观测值，不能代表项目质量；仓库建立时间不等于版本发布时间。</p>
  </section>)}</>;
}
function published(item: Item) {
  return item.published_at ? new Date(item.published_at).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }) : '发布时间未知';
}

export function ResearchResults({ run }: { run: ResearchRun }) {
  const items = [...run.items].sort(newestFirst);
  const findings = new Map(run.summary?.findings.map(row => [row.item_id, row]) ?? []);
  const grouped = run.summary?.sections ?? [];
  const assigned = new Set(grouped.flatMap(group => group.item_ids));
  const sections = grouped.map(group => ({ ...group,
    items: items.filter(item => group.item_ids.includes(item.id)),
  })).filter(group => group.items.length > 0)
    .sort((a, b) => newestFirst(a.items[0], b.items[0]));
  const remaining = items.filter(item => !assigned.has(item.id));
  return <div className="research-results">
    <SourceSearchEvidence reports={run.source_reports??[]}/>
    {run.summary && <section className="research-overview" aria-label="本次总览">
      <span className="eyebrow">研究总览</span><h3>本次值得关注什么</h3>
      <p>{run.summary.overview}</p>
    </section>}
    <div className="section-heading"><h3>分类情报</h3><span>区域按最新条目排列 · 区内按发布时间倒序 · 北京时间</span></div>
    {sections.length === 0 && items.length > 0 && <p className="notice">
      这些条目尚无分类分析。点击“分析已有结果”，agent 会按类型归纳；不会重新采集。
    </p>}
    <div className="research-zone-grid">
      {sections.map(group => <section className="research-zone" key={group.category}>
        <header className="zone-heading"><h3>{group.category}</h3><span>{group.items.length} 条</span></header>
        <div className="zone-analysis">
          <span className="eyebrow">AGENT 综合分析</span>
          <p>{group.summary}</p>
          <ul>{group.key_points.map((point, i) => <li key={i}>{point}</li>)}</ul>
          <p className="zone-action"><b>建议关注：</b>{group.suggested_action}</p>
        </div>
        <div className="zone-items">{group.items.map(item => <article className="research-news" key={item.id}>
          <div className="news-meta"><span>{item.source}</span><time dateTime={item.published_at ?? undefined}>{published(item)}</time></div>
          <h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}<span aria-hidden="true"> ↗</span></a></h4>
          {findings.has(item.id) && <details><summary>查看单条解读</summary>
            <p>{findings.get(item.id)!.insight}</p>
            <p><b>与目的的关系：</b>{findings.get(item.id)!.purpose_relevance}</p>
            <p><b>可考虑：</b>{findings.get(item.id)!.suggested_action}</p>
          </details>}
        </article>)}</div>
      </section>)}
      {remaining.length > 0 && <section className="research-zone pending-zone">
        <header className="zone-heading"><h3>{sections.length ? '尚未纳入分类分析' : '待归类资讯'}</h3><span>{remaining.length} 条</span></header>
        <p className="notice">每次最多分析最新 12 条，以下条目按发布时间排列；尚无区域综合结论。</p>
        {remaining.map(item => <article className="research-news" key={item.id}>
          <div className="news-meta"><span>{item.source}</span><time dateTime={item.published_at ?? undefined}>{published(item)}</time></div>
          <h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title} ↗</a></h4>
        </article>)}
      </section>}
    </div>
    {!items.length && <p className="notice">{run.errors.length > 0
      ? '本次采集或话题筛选未完成，请查看上方原因。已有原始资料会保留。'
      : run.received > 0 ? `本次获取了 ${run.received} 条候选，但未筛出与当前话题和目的相关的条目。可以调整话题，或稍后再运行。`
      : '本次未获取到可用条目。可以检查目标网站，或稍后再运行。'}</p>}
    {run.summary?.limitations && <details className="research-evidence"><summary>证据范围与限制</summary><p>{run.summary.limitations}</p></details>}
  </div>;
}
