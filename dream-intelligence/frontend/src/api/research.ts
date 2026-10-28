export interface ResearchPlan {
  id: number;
  name: string;
  topics: string[];
  websites: string[];
  purpose: string;
  created_at: string;
  collection_type?: 'research' | 'images' | 'videos';
}

export interface ResearchImage {
  id: number; title: string; source_url: string; image_url: string; thumbnail_url: string;
  provider?: string;
  creator: string; license: string; license_url: string; attribution: string;
  width: number | null; height: number | null; favorite: boolean; downloaded: boolean;
  recommended: boolean; reason: string; usage_notes: string;
}

export interface VisualObservation {
  image_id:number;readable:boolean;description:string;scene:string;lighting:string;colors:string[];
  composition:string;category:string;fit:'MATCH'|'PARTIAL'|'NOT_MATCH';purpose_relevance:string;
  suggestion:string;uncertainty:string;watermark:'VISIBLE'|'NOT_VISIBLE'|'UNCERTAIN';
}
export interface VisualGroup {
  category:string;summary:string;key_points:string[];suggested_action:string;image_ids:number[];
}
export interface VisualReport {
  run_id:number;model:string;analyzed_at:string;overview:string;observations:VisualObservation[];
  groups:VisualGroup[];analyzed_count:number;candidate_count:number;input_hash:string;
  errors:{image_id:number;reason:string}[];cached:boolean;
}

export interface ResearchRun {
  id: number;
  plan_id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  received: number;
  matched: number;
  inserted: number;
  errors: { website: string | null; reason: string }[];
  summary: null | {
    overview: string;
    findings: { item_id: number; insight: string; purpose_relevance: string; suggested_action: string }[];
    limitations: string;
    sections?: { category: string; summary: string; key_points: string[];
      suggested_action: string; item_ids: number[] }[];
  };
  items: { id: number; title: string; url: string; source: string; published_at: string | null }[];
  images?: ResearchImage[];
  image_summary?: { overview: string; limitations: string; kind?: 'analysis' | 'search' } | null;
  visual_analysis?: VisualReport | null;
  video_search?: {queries:{topic:string;query:string;order:string;returned:number;status:string}[];
    candidate_count:number;candidate_channel_count:number;selected_count:number;selected_channel_count:number;max_per_channel:number}|null;
}

const base = 'http://127.0.0.1:8000/api/v1/research-plans';

async function checked<T>(pending: Promise<Response>): Promise<T> {
  const response = await pending;
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<T>;
}

export async function listResearchPlans(signal?: AbortSignal): Promise<ResearchPlan[]> {
  return checked(fetch(base, { signal }));
}

export async function createResearchPlan(input: Omit<ResearchPlan, 'id' | 'created_at'>): Promise<ResearchPlan> {
  let response: Response;
  try {
    response = await fetch(base, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input) });
  } catch {
    throw new Error('无法连接本地服务，请确认 DSIH 已启动。');
  }
  if (response.status === 422) {
    const body = await response.json().catch(() => null);
    const field = body?.detail?.find((issue: { loc?: unknown[] }) =>
      Array.isArray(issue.loc) && issue.loc[0] === 'body')?.loc?.[1];
    const hints: Record<string, string> = {
      name: '请填写方案名称（最多 100 字）。',
      topics: '请填写 1–8 个不同的话题，每个最多 80 字。',
      websites: '请填写 1–5 个公开网站，支持 www.bilibili.com 或完整的 http(s) 地址。',
      purpose: '请填写至少 10 字的分析目的。',
    };
    throw new Error(hints[String(field)] ?? '方案内容未通过校验，请检查各项填写。');
  }
  if (!response.ok) throw new Error(`保存失败，本地服务返回 ${response.status}。`);
  return response.json() as Promise<ResearchPlan>;
}

export async function disableResearchPlan(id: number): Promise<void> {
  const response = await fetch(`${base}/${id}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
}

export async function updateImageSources(id:number,websites:string[]):Promise<ResearchPlan> {
  const response=await fetch(`${base}/${id}/image-sources`,{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({websites})});
  if(response.status===409) throw new Error('研究正在运行，请完成后再修改来源。');
  if(!response.ok) throw new Error('来源未保存，请至少选择一个可用来源后重试。');
  return response.json();
}

export async function listResearchRuns(id: number, signal?: AbortSignal): Promise<ResearchRun[]> {
  return checked(fetch(`${base}/${id}/runs`, { signal }));
}

export async function runResearchPlan(id: number): Promise<ResearchRun> {
  const response=await fetch(`${base}/${id}/run`,{method:'POST'});
  if(!response.ok){const body=await response.json().catch(()=>null);
    throw new Error(body?.detail==='YOUTUBE_NOT_CONFIGURED'?'请先配置 YouTube API Key 并重新启动后端。':
      response.status===409?'另一项采集正在运行，请稍后再试。':'本次采集未完成，请检查来源状态。');}
  return response.json();
}

export async function getImageVisionStatus(signal?:AbortSignal):Promise<{configured:boolean;model:string|null}> {
  return checked(fetch('http://127.0.0.1:8000/api/v1/image-vision/status',{signal}));
}

export async function analyzeImageVision(planId:number,runId:number):Promise<VisualReport> {
  const response=await fetch(`${base}/${planId}/runs/${runId}/vision`,{method:'POST'});
  if(!response.ok) {
    const body=await response.json().catch(()=>null);
    const code=typeof body?.detail==='string' ? body.detail : '';
    const labels:Record<string,string>={VISION_NOT_CONFIGURED:'视觉模型尚未配置，请先检查 Qwen 接入。',
      VISION_RUN_BUSY:'另一项研究正在运行，请完成后再试。',VISION_NO_IMAGES:'当前没有可供分析的图片。',
      VISION_PREVIEWS_UNAVAILABLE:'预览图暂时无法读取，请稍后重试。',
      VISION_REPORT_INVALID:'看图结果未通过校验，旧结果已保留。',
      VISION_NOT_OBSERVED:'模型未能读到图像，旧结果已保留。',
      VISION_INPUT_CHANGED:'分析期间方案已变化，请刷新后重试。'};
    throw new Error(labels[code] ?? (code.startsWith('VISION_PROVIDER_HTTP_4')
      ? '视觉模型接口拒绝了本次请求，请检查权限与模型配置；旧结果已保留。'
      : '看图分析未完成，旧结果已保留，请稍后重试。'));
  }
  return response.json();
}

export async function openDoubanLogin(): Promise<void> {
  const response = await fetch('http://127.0.0.1:8000/api/v1/research-sources/douban/login', { method: 'POST' });
  if (!response.ok) throw new Error('登录窗口未能打开，请先结束采集并确认 Chrome 可用。');
}

export async function favoriteImage(id: number, favorite: boolean): Promise<void> {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/research-images/${id}/favorite`, {
    method: favorite ? 'POST' : 'DELETE' });
  if (!response.ok) throw new Error('收藏状态未能保存，请重试。');
}

export async function listFavoriteImages(planId: number): Promise<ResearchImage[]> {
  return checked(fetch(`${base}/${planId}/favorite-images`));
}

export async function downloadImage(id: number): Promise<void> {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/research-images/${id}/download`, { method: 'POST' });
  if (!response.ok) throw new Error('下载未完成：原图可能不可访问、超过 20MB，或格式／许可信息不完整。可打开原站核对。');
  const link = document.createElement('a');
  link.href = `http://127.0.0.1:8000/api/v1/research-images/${id}/file`;
  document.body.appendChild(link); link.click(); link.remove();
}

export async function analyzeResearchRun(planId: number, runId: number): Promise<ResearchRun> {
  return checked(fetch(`${base}/${planId}/runs/${runId}/analyze`, { method: 'POST' }));
}
