export interface SourceDefinition {
  name:string; site_url:string; adapter:'json_api'|'rss'; endpoint:string; description:string; enabled:boolean;
  auth_env:string; auth_required:boolean; query_param:string; query_suffix:string; items_path:string;
  field_map:Record<string,string>; url_prefix:string; params:Record<string,string>;
  sort_param:string; sort_values:string[]; default_sort:string; limit_param:string; max_results:number;
}
export interface SourceConnection extends SourceDefinition {id:number; credential_present:boolean; ready:boolean}
export interface SourceBinding {connection_id:number; query:string; sort:string; limit:number}
export interface SourceTemplate {id:string; definition:SourceDefinition}
const base='http://127.0.0.1:8000/api/v1/source-connections';
async function checked<T>(pending:Promise<Response>):Promise<T> {
  const response=await pending;
  if(!response.ok) throw new Error(response.status===409?'研究正在运行，请结束后再调整接口。':
    response.status===422?'配置未通过校验。请检查公开 HTTPS 地址、参数与字段映射；密钥栏只填环境变量名。':'来源接口暂不可用。');
  return response.json();
}
export const listSourceConnections=(signal?:AbortSignal)=>checked<SourceConnection[]>(fetch(base,{signal}));
export const listSourceTemplates=(signal?:AbortSignal)=>checked<SourceTemplate[]>(fetch(base+'/templates',{signal}));
export function saveSourceConnection(definition:SourceDefinition,id?:number):Promise<SourceConnection> {
  return checked(fetch(base+(id?`/${id}`:''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(definition)}));
}
export function savePlanSourceBindings(planId:number,bindings:SourceBinding[]) {
  return checked<import('./research').ResearchPlan>(fetch(`http://127.0.0.1:8000/api/v1/research-plans/${planId}/source-bindings`,
    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bindings})}));
}
