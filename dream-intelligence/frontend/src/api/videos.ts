export interface VideoReference {
  id:number;external_id:string;title:string;title_zh:string|null;summary_zh:string|null;
  category:string;channel:string;url:string;thumbnail_url:string;published_at:string;favorite:boolean;
}
export interface VideoSchedule {
  enabled:boolean;interval_minutes:number;interval_options:number[];configured:boolean;
  scheduler_connected:boolean;scheduler_configured:boolean;next_run_at:string|null;
}
const base='http://127.0.0.1:8000/api/v1/research-plans';
async function read<T>(url:string,options?:RequestInit):Promise<T>{
  const response=await fetch(url,options);
  if(!response.ok){const body=await response.json().catch(()=>null);
    throw new Error(body?.detail==='YOUTUBE_NOT_CONFIGURED'?'请先配置 YouTube API Key 并重新启动后端。':'操作未完成，请稍后重试。');}
  return response.json();
}
export const listVideos=(id:number,favorites=false)=>read<VideoReference[]>(`${base}/${id}/videos?favorites=${favorites}`);
export const getVideoSchedule=(id:number)=>read<VideoSchedule>(`${base}/${id}/video-schedule`);
export const saveVideoSchedule=(id:number,enabled:boolean,interval_minutes:number)=>read<VideoSchedule>(`${base}/${id}/video-schedule`,{
  method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled,interval_minutes})});
export const favoriteVideo=(plan:number,video:number,favorite:boolean)=>read(`${base}/${plan}/videos/${video}/favorite`,{method:favorite?'POST':'DELETE'});
