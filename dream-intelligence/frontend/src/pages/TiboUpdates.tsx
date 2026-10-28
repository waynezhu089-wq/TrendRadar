import { useEffect, useState } from 'react';
import { getTiboStatus,openXLogin,intervalLabel,type TiboStatus } from '../api/tibo';

const date=(value:string|null)=>value ? new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}) : '未提供';
const errorLabels:Record<string,string>={XLoginRequired:'专用 X 登录待完成或已失效',
  XAccessBlocked:'X 限制访问，已停止继续请求',XBrowserUnavailable:'X 专用浏览器不可用，请关闭登录窗口',
  ResetFeedUnavailable:'社区消息源暂时不可用',CHINESE_TRANSLATION_FAILED:'部分消息中文整理未完成，稍后重试'};
export function TiboFeed({data}:{data:TiboStatus}) {
  return <div className="tibo-feed">
    <header className="tibo-header"><span className="eyebrow">自动订阅 · @{data.account}</span>
      <h2>Tibo · Codex 动态</h2><p>中文阅读更新，单独提醒额度重置。</p>
      <p className="notice">{data.enabled ? `每 ${intervalLabel(data.poll_minutes)} 检查，检测到相关新消息即发飞书；源站可能延迟。` : '订阅尚未启用。'}<br />
        最近成功读取：{date(data.last_success_at)}（北京时间）</p></header>
    {!data.browser_enabled && <p className="notice">当前使用 Codex Resets 社区重置消息源；完整账号动态尚待专用 X 会话验证。</p>}
    {data.errors.length>0 && <p role="status" className="notice">{data.errors.map(row=>errorLabels[row.reason] ?? '部分来源读取未完成').join('；')}</p>}
    <div className="tibo-posts">{data.posts.map(post=><article className="tibo-post" key={post.id}>
      <div className="news-meta"><span>{post.signal_label}</span><time>{date(post.published_at ?? post.reported_at)} · {post.published_at ? '发布时间' : '社区记录时间'}</time></div>
      <h3>{post.title_zh ?? '等待中文整理'}</h3>
      <p className="tibo-translation">{post.translation_zh ?? '原始记录已保存，译文尚未完成。'}</p>
      {post.reason_zh && <p className="notice">{post.reason_zh}</p>}
      <div className="tibo-links"><a href={post.url} target="_blank" rel="noopener noreferrer">查看 X 原帖 ↗</a>
        <a href={post.source_url} target="_blank" rel="noopener noreferrer">{post.source_kind==='x_browser' ? 'X 会话读取' : '来源：Codex Resets 社区转录'} ↗</a>
        {post.delivery_statuses.includes('SENT') && <span>飞书已发送</span>}
        {post.delivery_statuses.some(status=>['UNKNOWN','SENDING'].includes(status)) && <span>发送结果待核对，系统不会自动重复发送</span>}
      </div>
      <details><summary>{post.source_kind==='community_observed' ? '社区记录英文' : '查看原文'}</summary><p>{post.original_text}</p></details>
    </article>)}</div>
    {!data.posts.length && <p className="research-empty">等待首次读取。订阅启用时会建立基线，之后新增消息再触发提醒。</p>}
  </div>;
}

export function TiboUpdates() {
  const [data,setData]=useState<TiboStatus|null>(null);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  async function refresh() {
    try {setData(await getTiboStatus());setError('');}
    catch(reason){setError(reason instanceof Error ? reason.message : '无法加载订阅。');}
  }
  useEffect(()=>{const controller=new AbortController();
    getTiboStatus(controller.signal).then(setData).catch(()=>{if(!controller.signal.aborted)setError('无法加载订阅。');});
    return ()=>controller.abort();},[]);
  async function login() {
    try {await openXLogin();setNotice('请在专用 Chrome 窗口亲自登录 X，然后关闭该窗口。无需提供密码或 Cookie。');}
    catch {setError('登录窗口未能打开，请确认 Chrome 可用。');}
  }
  return <section className="tibo-panel"><div className="research-actions">
    <button type="button" onClick={()=>void refresh()}>刷新列表</button>
    <button type="button" onClick={()=>void login()}>登录 X 专用会话</button>
    <a href="/settings?tab=subscriptions">订阅设置 →</a></div>
    {notice && <p role="status" className="notice">{notice}</p>}
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {data && <TiboFeed data={data}/>}</section>;
}
