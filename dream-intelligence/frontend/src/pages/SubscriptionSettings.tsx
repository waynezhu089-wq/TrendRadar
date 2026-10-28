import {useEffect,useState} from 'react';
import {getTiboSettings,saveTiboSettings,intervalLabel,type TiboSettings} from '../api/tibo';

export function SubscriptionPreferences({data,minutes,onChange,onSave,busy}:{data:TiboSettings;
  minutes:number;onChange:(value:number)=>void;onSave:()=>void;busy:boolean}) {
  const next=data.next_run_time ? new Date(data.next_run_time).toLocaleString('zh-CN',{
    timeZone:'Asia/Shanghai',hour12:false}) : null;
  return <section className="subscription-settings"><span className="eyebrow">自动订阅</span>
    <h2>Tibo · Codex 动态</h2><p>定期收集 Tibo 的更新并翻译成中文。发现新的额度重置消息后，发送飞书提醒。</p>
    <div className="subscription-frequency"><label htmlFor="tibo-interval">检查频率</label>
      <select id="tibo-interval" value={minutes} disabled={!data.enabled || busy}
        onChange={event=>onChange(Number(event.target.value))}>
        {!data.interval_options.includes(minutes) && <option value={minutes}>每 {intervalLabel(minutes)}（原设置）</option>}
        {data.interval_options.map(value=><option key={value} value={value}>每 {intervalLabel(value)}</option>)}
      </select><button type="button" disabled={busy || !data.enabled || minutes===data.poll_minutes}
        onClick={onSave}>{busy ? '保存中…' : '保存设置'}</button></div>
    <p className="notice">保存后约 30 秒内自动生效，下一次检查从生效时开始计时。保存不会立即采集或发送消息。</p>
    <div className="subscription-state" role="status">
      {!data.enabled ? '订阅尚未启用。' : !data.scheduler_connected ? '已保存，等待调度服务读取。' :
        data.pending ? `已保存：每 ${intervalLabel(data.poll_minutes)}；等待调度服务应用。` :
        `当前生效：每 ${intervalLabel(data.applied_poll_minutes ?? data.poll_minutes)}。`}
      {data.scheduler_connected && !data.pending && next && <p>下次检查：{next}（北京时间）</p>}
    </div><a href="/research?subscription=tibo">查看 Tibo 动态 →</a>
  </section>;
}

export function SubscriptionSettings() {
  const [data,setData]=useState<TiboSettings|null>(null);
  const [minutes,setMinutes]=useState(120);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{const controller=new AbortController();
    getTiboSettings(controller.signal).then(value=>{setData(value);setMinutes(value.poll_minutes);})
      .catch(()=>{if(!controller.signal.aborted)setError('无法加载订阅设置，请刷新重试。');});
    // Status refresh reads saved preferences only; it never checks X or sends messages.
    const timer=window.setInterval(()=>{getTiboSettings(controller.signal).then(setData)
      .catch(()=>{});},10000);
    return ()=>{controller.abort();window.clearInterval(timer);};},[]);
  async function save() {
    setBusy(true);setError('');
    try {setData(await saveTiboSettings(minutes));}
    catch(reason){setError(reason instanceof Error ? reason.message : '设置未保存。');}
    finally {setBusy(false);}
  }
  return <>{error && <p role="alert" className="feedback-error">{error}</p>}
    {data ? <SubscriptionPreferences data={data} minutes={minutes} onChange={setMinutes}
      onSave={()=>void save()} busy={busy}/> : !error && <p>正在读取订阅设置…</p>}</>;
}
