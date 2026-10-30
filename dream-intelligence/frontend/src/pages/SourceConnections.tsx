import {useEffect,useState,type FormEvent} from 'react';
import {listSourceConnections,listSourceTemplates,saveSourceConnection,type SourceConnection,type SourceDefinition,type SourceTemplate} from '../api/sourceConnections';

export function SourceConnectionCard({source,onEdit}:{source:SourceConnection;onEdit:()=>void}) {
  return <article className="source-connection-card"><div><h3>{source.name}</h3>
    <p>{source.description}</p><p className="notice">{source.enabled?'已启用':'已停用'} · {source.adapter==='rss'?'公共 RSS/Atom':'JSON API'} ·
      {source.auth_env?(source.credential_present?'凭据变量已存在':source.auth_required?'缺少凭据变量':'未配置凭据，可尝试匿名请求'):'无需凭据'} · 尚未联网验收</p>
    <p className="notice">{source.site_url}</p></div><button type="button" onClick={onEdit}>编辑接口</button></article>;
}

export function SourceDefinitionForm({initial,onSave,onCancel,busy}:{initial:SourceDefinition;
  onSave:(definition:SourceDefinition)=>Promise<void>;onCancel:()=>void;busy:boolean}) {
  const [value,setValue]=useState(initial);
  const [mapping,setMapping]=useState(JSON.stringify(initial.field_map,null,2));
  const [params,setParams]=useState(JSON.stringify(initial.params,null,2));
  const [sortText,setSortText]=useState(initial.sort_values.join(','));
  const [error,setError]=useState('');
  const change=<K extends keyof SourceDefinition>(key:K,next:SourceDefinition[K])=>setValue(current=>({...current,[key]:next}));
  async function submit(event:FormEvent) {
    event.preventDefault();setError('');
    let fields:Record<string,string>,fixed:Record<string,string>;
    try {fields=value.adapter==='json_api'?JSON.parse(mapping):value.field_map;fixed=value.adapter==='json_api'?JSON.parse(params):{};}catch {setError('字段映射和固定参数必须是有效的 JSON 对象。');return;}
    await onSave({...value,field_map:fields,params:fixed,sort_values:value.adapter==='json_api'?sortText.split(',').map(row=>row.trim()).filter(Boolean):[]});
  }
  return <form className="source-definition-form" onSubmit={event=>void submit(event)}><fieldset disabled={busy}>
    <div className="source-config-grid">
      <label>接口名称<input required maxLength={80} value={value.name} onChange={event=>change('name',event.target.value)}/></label>
      <label>网站首页<input required type="url" value={value.site_url} onChange={event=>change('site_url',event.target.value)}/></label>
      <label>接口类型<select value={value.adapter} onChange={event=>setValue(current=>event.target.value==='rss'?{...current,adapter:'rss',auth_env:'',auth_required:false,query_param:'',query_suffix:'',sort_param:'',sort_values:[],default_sort:'',limit_param:''}:{...current,adapter:'json_api'})}>
        <option value="json_api">JSON API</option><option value="rss">公共 RSS/Atom</option></select></label>
      <label>请求地址<input required type="url" value={value.endpoint} onChange={event=>change('endpoint',event.target.value)}/></label>
    </div>
    <label>来源能力说明<textarea rows={2} maxLength={400} value={value.description} onChange={event=>change('description',event.target.value)}/></label>
    <label className="source-check"><input type="checkbox" checked={value.enabled} onChange={event=>change('enabled',event.target.checked)}/>启用此接口供方案选择</label>
    {value.adapter==='json_api'&&<><div className="source-config-grid">
      <label>凭据环境变量名（不填密钥）<input autoComplete="off" value={value.auth_env} placeholder="GITHUB_TOKEN 或 DSIH_SOURCE_XXX" onChange={event=>change('auth_env',event.target.value)}/></label>
      <label>接口最多返回条数<input type="number" min={1} max={12} required value={value.max_results} onChange={event=>change('max_results',Number(event.target.value))}/></label>
    </div><label className="source-check"><input type="checkbox" checked={value.auth_required} onChange={event=>change('auth_required',event.target.checked)}/>运行时必须有该凭据</label>
    <details className="source-advanced"><summary>接口参数与字段映射</summary><div className="source-config-grid">
      <label>检索词参数名<input value={value.query_param} onChange={event=>change('query_param',event.target.value)}/></label>
      <label>固定检索限定词<input value={value.query_suffix} onChange={event=>change('query_suffix',event.target.value)}/></label>
      <label>结果数组路径<input value={value.items_path} placeholder="items；顶层为数组时留空" onChange={event=>change('items_path',event.target.value)}/></label>
      <label>排序参数名<input value={value.sort_param} onChange={event=>change('sort_param',event.target.value)}/></label>
      <label>允许的排序值<input value={sortText} onChange={event=>setSortText(event.target.value)}/></label>
      <label>默认排序<input value={value.default_sort} onChange={event=>change('default_sort',event.target.value)}/></label>
      <label>条数参数名<input value={value.limit_param} onChange={event=>change('limit_param',event.target.value)}/></label>
      <label>无原文 URL 时的网址前缀<input value={value.url_prefix} onChange={event=>change('url_prefix',event.target.value)}/></label>
    </div><label>固定参数（JSON，仅非敏感参数）<textarea rows={4} value={params} onChange={event=>setParams(event.target.value)}/></label>
    <label>返回字段映射（JSON）<textarea rows={8} value={mapping} onChange={event=>setMapping(event.target.value)}/></label>
    <p className="notice">支持 id、title、url、content、published_at、stars、updated_at；值为点分隔字段名，例如 owner.login。只发出一次有上限的 GET 请求，不执行脚本或自动翻页。</p></details></>}
    <p className="notice">保存只更新本机配置，不会采集、调用模型或启动定时任务。凭据从后端环境读取；修改环境变量后需重新加载 API。</p>
    <div className="research-actions"><button type="submit">{busy?'保存中…':'保存接口'}</button><button type="button" onClick={onCancel}>取消</button></div>
    {error&&<p role="alert" className="feedback-error">{error}</p>}
  </fieldset></form>;
}

export function SourceConnections() {
  const [sources,setSources]=useState<SourceConnection[]>([]);
  const [templates,setTemplates]=useState<SourceTemplate[]>([]);
  const [editing,setEditing]=useState<{id?:number;definition:SourceDefinition;key:number}|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  useEffect(()=>{const controller=new AbortController();
    Promise.all([listSourceConnections(controller.signal),listSourceTemplates(controller.signal)]).then(([rows,choices])=>{setSources(rows);setTemplates(choices);})
      .catch(()=>{if(!controller.signal.aborted)setError('无法加载来源接口，请检查 API。');});return()=>controller.abort();},[]);
  async function save(value:SourceDefinition) {
    setBusy(true);setError('');setNotice('');
    try {const row=await saveSourceConnection(value,editing?.id);setSources(current=>[...current.filter(source=>source.id!==row.id),row].sort((a,b)=>a.id-b.id));
      setEditing(null);setNotice('来源接口已保存。可在关注方案中选择，或让方案助手使用它；尚未执行采集。');}
    catch(reason){setError(reason instanceof Error?reason.message:'接口未保存。');}finally{setBusy(false);}
  }
  return <section className="source-connections"><h2>来源接口</h2><p className="notice">在这里配置可复用的接口，关注方案和助手会读取同一份来源目录。新 JSON API 或 RSS 可按文档配置；需要专门登录流程或协议的网站须另接适配器。</p>
    <div className="research-actions">{templates.map(template=><button key={template.id} type="button" disabled={busy}
      onClick={()=>{setError('');setNotice('');setEditing({definition:template.definition,key:Date.now()});}}>添加{template.definition.name}</button>)}</div>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert" className="feedback-error">{error}</p>}
    {editing&&<SourceDefinitionForm key={editing.key} initial={editing.definition} busy={busy} onSave={save} onCancel={()=>setEditing(null)}/>}
    {!sources.length&&!editing&&<p className="research-empty">尚未配置来源接口。可从 GitHub 模板开始，再在方案中设置检索词、排序和条数。</p>}
    {sources.map(source=><SourceConnectionCard key={source.id} source={source} onEdit={()=>{setError('');setNotice('');
      const {id,credential_present,ready,...definition}=source;void credential_present;void ready;setEditing({id,definition,key:Date.now()});}}/>)}
    <p className="notice">Hugging Face、Instagram 等其他网站本次尚未接入。现有微博、B 站、豆瓣等内置来源继续按原方式使用。</p>
  </section>;
}
