import { useEffect, useState, type FormEvent } from 'react';
import { confirmPlan, draftPlan, type AssistantMessage, type CreatedPlan, type PlanFields, type PlanProposal } from '../api/planAssistant';
import { readAssistantSession, saveAssistantSession, clearAssistantSession } from '../api/assistantSession';

const splitLines = (value: string) => value.split(/[\n,，]+/).map(row => row.trim()).filter(Boolean);
function sourceLink(value: string) {
  try {
    const url = new URL(value.includes('://') ? value : `https://${value}`);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url : null;
  } catch { return null; }
}

export function PlanPreview({ proposal }: { proposal: PlanProposal }) {
  const plan = proposal.plan;
  if (!plan) return null;
  return <div className="assistant-preview">
    <span className="eyebrow">待创建的关注方案</span><h3>{plan.name}</h3>
    <dl><dt>收集类型</dt><dd>{plan.collection_type==='videos'?'YouTube 视频灵感':plan.collection_type === 'images' ? '视频灵感与图片参考素材' : '资讯研究'}</dd>
      <dt>关注话题</dt><dd>{plan.topics.join(' · ')}</dd>
      <dt>分析目的</dt><dd>{plan.purpose}</dd></dl>
    <div className="assistant-sources">{plan.websites.map(value => {
      const source = proposal.sources.find(row => row.url === value);
      const url = sourceLink(value);
      return <div key={value}><strong>{source?.name ?? '手动调整的来源'}</strong>
        {url ? <a href={url.href} target="_blank" rel="noopener noreferrer">{url.hostname}</a> : <span>{value || '请填写公开网址'}</span>}
        <p>{source?.scope ?? '仅尝试公共 RSS 或静态页面；可继续与助手确认采集范围。'}</p></div>;
    })}{plan.source_bindings?.map(binding=>{const source=proposal.sources.find(row=>row.connection_id===binding.connection_id);
      const url=source?sourceLink(source.url):null;
      return <div key={binding.connection_id}><strong>{source?.name??`来源接口 #${binding.connection_id}`}</strong>
        {url&&<a href={url.href} target="_blank" rel="noopener noreferrer">{url.hostname}</a>}
        <p>检索：{binding.query||plan.topics.join(' ')} · 排序：{binding.sort||'接口默认'} · 最多 {binding.limit} 条</p>
        <p>{source?.scope??'使用已保存的来源接口配置。'}</p></div>;
    })}</div>
    {Boolean(proposal.deferred_sources?.length) && <div className="assistant-deferred"><strong>暂未加入</strong>
      {proposal.deferred_sources!.map(source => <p key={source.name}>{source.name}：{source.reason}</p>)}
      <p>先创建当前范围的方案，之后可以补充这些来源。</p></div>}
  </div>;
}

export function PlanAssistant({ onCreated, onClose }: { onCreated: (result: CreatedPlan) => void; onClose: () => void }) {
  const [session] = useState(readAssistantSession);
  const [input, setInput] = useState(session?.input ?? '');
  const [messages, setMessages] = useState<AssistantMessage[]>(session?.messages ?? []);
  const [proposal, setProposal] = useState<PlanProposal | null>(session?.proposal ?? null);
  const [draft, setDraft] = useState<PlanFields | null>(session?.draft ?? null);
  const [topicText, setTopicText] = useState(session?.topicText ?? '');
  const [websiteText, setWebsiteText] = useState(session?.websiteText ?? '');
  const [busy, setBusy] = useState<'thinking' | 'saving' | null>(null);
  const [error, setError] = useState('');
  const [retryMessages, setRetryMessages] = useState<AssistantMessage[] | null>(null);
  useEffect(() => {
    saveAssistantSession({ input, messages, proposal, draft, topicText, websiteText });
  }, [input, messages, proposal, draft, topicText, websiteText]);

  function reset() {
    clearAssistantSession(); setInput(''); setMessages([]); setProposal(null); setDraft(null);
    setTopicText(''); setWebsiteText(''); setError(''); setRetryMessages(null);
  }

  async function ask(history: AssistantMessage[]) {
    setBusy('thinking'); setError(''); setRetryMessages(null); setProposal(null);
    try {
      const result = await draftPlan(history, draft);
      const answer = [result.message, ...result.questions].join('\n');
      setMessages([...history, { role: 'assistant', content: answer }]);
      setProposal(result); setDraft(result.plan);
      setTopicText(result.plan?.topics.join('\n') ?? '');
      setWebsiteText(result.plan?.websites.join('\n') ?? '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '助手暂不可用。');
      setRetryMessages(history);
      // An earlier proposal must not be confirmed as the answer to a failed new request.
      setProposal(null);
    } finally { setBusy(null); }
  }
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim() || busy) return;
    const history: AssistantMessage[] = [...messages, { role: 'user', content: input.trim() }];
    setMessages(history); setInput('');
    await ask(history);
  }
  async function save() {
    if (!draft || busy || proposal?.status !== 'draft_ready') return;
    setBusy('saving'); setError('');
    try { const result = await confirmPlan(draft); clearAssistantSession(); onCreated(result); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '尚未保存成功，草案已保留。'); }
    finally { setBusy(null); }
  }
  return <section className="plan-assistant" aria-labelledby="assistant-heading">
    <header className="assistant-heading"><div><span className="eyebrow">方案助手</span>
      <h2 id="assistant-heading">说说你想关注什么</h2></div>
      <div className="assistant-header-actions"><button type="button" className="assistant-close" disabled={Boolean(busy)} onClick={reset}>重新开始</button>
      <button type="button" className="assistant-close" disabled={Boolean(busy)} onClick={onClose}>收起</button></div></header>
    <p className="notice">说清想研究的议题，或要制作的视频、想探索的画面和用途，助手会帮你整理方案。</p>
    {messages.length > 0 && <div className="assistant-conversation" role="log" aria-label="与方案助手的对话" aria-live="polite">
      {messages.map((message, index) => <div key={index} className={`assistant-message ${message.role}`}>
        <small>{message.role === 'user' ? '你' : '方案助手'}</small><p>{message.content}</p>
      </div>)}
    </div>}
    <form className="assistant-composer" onSubmit={event => void send(event)}>
      <label htmlFor="assistant-request">{messages.length ? '补充要求或继续调整' : '你的需求'}</label>
      <textarea id="assistant-request" rows={3} maxLength={1800} value={input} disabled={Boolean(busy)}
        onChange={event => setInput(event.target.value)}
        placeholder="例如：为一支雨夜城市短片找色彩和场景氛围参考，接受带水印的预览。" />
      <button type="submit" disabled={Boolean(busy) || !input.trim()}>{busy === 'thinking' ? '正在整理需求…' : proposal?.status === 'draft_ready' ? '调整草案' : messages.length ? '发送补充' : '和助手说'}</button>
    </form>
    {proposal?.status === 'needs_details' && Boolean(proposal.deferred_sources?.length) && <div className="assistant-unblock">
      <button type="button" disabled={Boolean(busy)} onClick={() => {
        const history: AssistantMessage[] = [...messages, { role: 'user', content: '先用已接入且符合我关注方向的来源生成可创建的草案。没有适配器或没有具体网址的来源暂不加入，在草案中注明；不需要继续追问这些链接。' }];
        setMessages(history); void ask(history);
      }}>先生成可用来源草案</button><p>暂不纳入未接入的网站，创建前会列明当前范围。</p>
    </div>}
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {retryMessages && <button type="button" disabled={Boolean(busy)} className="assistant-retry" onClick={() => void ask(retryMessages)}>重试这条需求</button>}
    {proposal?.status === 'draft_ready' && draft && <>
      <PlanPreview proposal={{ ...proposal, plan: draft }} />
      <details className="assistant-edit"><summary>手动调整草案</summary>
        <fieldset disabled={Boolean(busy)} className="assistant-edit-fields">
          <label>名称<input value={draft.name} maxLength={100} onChange={event => setDraft({ ...draft, name: event.target.value })} /></label>
          <label>话题（每行一个，最多 8 个）<textarea rows={3} value={topicText} onChange={event => { setTopicText(event.target.value); setDraft({ ...draft, topics: splitLines(event.target.value) }); }} /></label>
          <label>网站（每行一个，最多 5 个）<textarea rows={2} value={websiteText} onChange={event => { setWebsiteText(event.target.value); setDraft({ ...draft, websites: splitLines(event.target.value) }); }} /></label>
          {draft.source_bindings?.map((binding,index)=><div key={binding.connection_id}>
            <label>接口 #{binding.connection_id} 检索式<input maxLength={256} value={binding.query} onChange={event=>setDraft({...draft,source_bindings:draft.source_bindings!.map((row,n)=>n===index?{...row,query:event.target.value}:row)})}/></label>
            <label>最多条数<input type="number" min={1} max={12} value={binding.limit} onChange={event=>setDraft({...draft,source_bindings:draft.source_bindings!.map((row,n)=>n===index?{...row,limit:Number(event.target.value)}:row)})}/></label>
          </div>)}
          <label>目的<textarea rows={3} value={draft.purpose} maxLength={1000} onChange={event => setDraft({ ...draft, purpose: event.target.value })} /></label>
        </fieldset>
        <p className="notice">手动填写其他网站时，只会尝试其公共 RSS 或静态页面；不会自动获得该站的登录采集能力。</p>
      </details>
      <div className="assistant-confirm"><button type="button" disabled={Boolean(busy)} onClick={() => void save()}>
        {busy === 'saving' ? '正在创建…' : '创建这个方案'}</button><span>创建后可进入研究工作台运行。</span></div>
    </>}
  </section>;
}
