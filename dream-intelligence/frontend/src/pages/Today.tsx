import { useEffect, useState } from 'react';
import { analyzeDaily, getDaily, type DailyView, type DailyItem } from '../api/daily';

function dateLabel(value: string, full = false) {
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric',
    ...(full ? { hour: '2-digit', minute: '2-digit' } : {}) }).format(new Date(value));
}

function NewsDate({ item, start }: { item: DailyItem; start: string }) {
  if (!item.published_at) return <span>发布时间未知 · {dateLabel(item.included_at)} 收录/分析</span>;
  return <span><time dateTime={item.published_at}>{dateLabel(item.published_at, true)} 发布</time>
    {Date.parse(item.published_at) < Date.parse(start) && <span className="daily-older">较早发布 · 本期收录/分析</span>}</span>;
}

export function TodayContent({ data, busy = false, onAnalyze }: {
  data: DailyView; busy?: boolean; onAnalyze?: () => void;
}) {
  const hasItems = data.topics.some(topic => topic.items.length);
  return <>
    <section className="daily-overview" aria-labelledby="daily-summary">
      <div className="daily-summary-heading"><div><span className="eyebrow">为你的关注而整理</span>
        <h2 id="daily-summary">{data.days === 1 ? '今日' : '近 7 天'}简报</h2></div>
        {(hasItems && !data.analysis || data.pending_candidates > 0) && <button type="button" onClick={onAnalyze} disabled={busy}>
          {busy ? '正在分析并整理简报…' : data.pending_candidates > 0 ? '分析并更新简报' : '生成本期分析'}</button>}
      </div>
      {data.analysis ? <ul>{data.analysis.overview.map((text, index) => <li key={index}>{text}</li>)}</ul>
        : <p className="daily-muted">{hasItems
          ? '资讯已按议题整理。生成本期分析后，这里会呈现与你的目的相关的变化和线索。'
          : data.days === 1 ? '今天尚无已收录或完成分析的情报。可以查看近 7 天，或进入 Research 更新专题。'
          : '本期尚无已收录或完成分析的情报。可以进入 Research 更新专题。'}</p>}
      {data.pending_candidates > 0 && <p className="daily-pending">最近 7 天有 {data.pending_candidates} 条候选资料可分析，每次最多 6 条；点击后调用已配置的模型。</p>}
      {data.processing && <p className="daily-pending" role="status">本次分析完成 {data.processing.analyzed} 条 · 跳过 {data.processing.skipped} 条 · 失败 {data.processing.failed} 条</p>}
      {data.notices?.map((notice, index) => <p key={index} role="alert" className="feedback-error">{notice}</p>)}
    </section>
    <div className="daily-topic-grid">{data.topics.map(topic => {
      const report = data.analysis?.topics.find(row => row.topic_id === topic.id);
      const visible = topic.items.slice(0, 3);
      return <section className="daily-topic" key={topic.id} aria-labelledby={`heading-${topic.id}`}>
        <header className="daily-topic-heading"><div><h2 id={`heading-${topic.id}`}>{topic.title}</h2>
          <p className="daily-purpose">{topic.purpose}</p></div>
          <span className="daily-count">{topic.total} 条</span></header>
        {report && <div className="daily-topic-analysis"><span className="eyebrow">议题归纳</span>
          <p>{report.summary}</p><details><summary>关键线索与建议</summary>
            <ul>{report.key_points.map((text, index) => <li key={index}>{text}</li>)}</ul>
            <p>{report.suggested_action}</p></details></div>}
        {!visible.length ? <p className="daily-empty">{data.days === 1 ? '今日暂无新增' : '近 7 天暂无新增'}</p>
          : <ol className="daily-headlines">{visible.map(item => <li key={item.id}>
            <div className="daily-news-meta"><span>{item.source}</span>
              <NewsDate item={item} start={data.start} /></div>
            <h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3>
            <p className="daily-item-summary">{item.summary}</p>
          </li>)}</ol>}
        {topic.href ? <a className="daily-topic-link" href={topic.href}>查看专题{topic.total > 3 ? ` · 共 ${topic.total} 条` : ''} →</a>
          : topic.items.length > 3 && <details className="daily-more"><summary>展开更多 · 共 {topic.total} 条</summary>
            <ol className="daily-headlines">{topic.items.slice(3).map(item => <li key={item.id}>
              <div className="daily-news-meta"><span>{item.source}</span><NewsDate item={item} start={data.start} /></div>
              <h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3><p className="daily-item-summary">{item.summary}</p>
            </li>)}</ol>
            {topic.total > topic.items.length && <p className="notice">本期展示最新 {topic.items.length} 条。</p>}
          </details>}
      </section>;
    })}</div>
    {data.topics.length === 0 && <p className="daily-empty">还没有关注议题。<a href="/settings">在设置中建立关注方案</a>。</p>}
    <p className="daily-footnote">本期收录或完成分析的资讯 · 按原始发布时间倒序，未知日期排后 · 北京时间 · 更新于 {dateLabel(data.end, true)}
      {data.unknown_dates > 0 && ` · 当前展示中 ${data.unknown_dates} 条发布时间未知，已明确标注`}
      {data.analysis && ' · 综合分析基于每个议题最新最多 12 条已分析资讯'}</p>
  </>;
}

export function Today() {
  const [days, setDays] = useState<1 | 7>(1);
  const [data, setData] = useState<DailyView | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    getDaily(days, controller.signal).then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [days]);
  async function onAnalyze() {
    setBusy(true); setError('');
    try { setData(await analyzeDaily(days, Boolean(data?.pending_candidates))); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '本期分析暂不可用。'); }
    finally { setBusy(false); }
  }
  return <main className="daily-page"><header className="daily-header"><div>
    <span className="eyebrow">Dream Intelligence</span><h1>Today</h1>
    <p>围绕你关心的议题，看看最近发生了什么。</p></div>
    <div className="daily-period" role="group" aria-label="资讯时间范围">
      <button type="button" disabled={busy} aria-pressed={days === 1} onClick={() => setDays(1)}>今天</button>
      <button type="button" disabled={busy} aria-pressed={days === 7} onClick={() => setDays(7)}>近 7 天</button>
    </div></header>
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {data ? <TodayContent data={data} busy={busy} onAnalyze={() => void onAnalyze()} />
      : !error && <p role="status" className="daily-loading">正在整理关注议题…</p>}
  </main>;
}
