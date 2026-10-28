export interface TiboPost {
  id: number; url: string; title_zh: string | null; translation_zh: string | null;
  original_text: string; reason_zh: string | null; signal: string; signal_label: string;
  source_kind: string; source_url: string; published_at: string | null; reported_at: string | null;
  captured_at: string; delivery_statuses: string[];
}
export interface TiboStatus {
  account: string; enabled: boolean; browser_enabled: boolean; poll_minutes: number;
  last_polled_at: string | null; last_success_at: string | null;
  errors: {source:string;reason:string}[]; posts: TiboPost[];
}
const base='http://127.0.0.1:8000/api/v1/tibo-monitor';
export interface TiboSettings {
  enabled: boolean; poll_minutes: number; interval_options: number[];
  applied_poll_minutes: number | null; next_run_time: string | null;
  scheduler_connected: boolean; pending: boolean;
}
export const intervalLabel=(minutes:number)=>minutes % 60 === 0 ? `${minutes / 60} 小时` : `${minutes} 分钟`;
export async function getTiboSettings(signal?:AbortSignal):Promise<TiboSettings> {
  const response=await fetch(`${base}/settings`,{signal});
  if(!response.ok) throw new Error('暂时无法读取订阅设置。');
  return response.json();
}
export async function saveTiboSettings(poll_minutes:number):Promise<TiboSettings> {
  const response=await fetch(`${base}/settings`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({poll_minutes})});
  if(!response.ok) throw new Error('设置未保存，请稍后重试。');
  return response.json();
}
export async function getTiboStatus(signal?: AbortSignal): Promise<TiboStatus> {
  const response=await fetch(base,{signal});
  if (!response.ok) throw new Error('暂时无法读取 Tibo 订阅。');
  return response.json();
}
export async function openXLogin(): Promise<void> {
  const response=await fetch(`${base}/login`,{method:'POST'});
  if (!response.ok) throw new Error('专用 X 登录窗口未能打开。');
}
