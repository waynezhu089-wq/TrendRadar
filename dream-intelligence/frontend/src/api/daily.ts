export interface DailyItem {
  id: number; title: string; url: string; source: string; published_at: string | null;
  captured_at: string; analyzed_at: string; included_at: string;
  summary: string; priority: number | null;
}
export interface DailyTopic {
  id: string; title: string; purpose: string; href: string; total: number; items: DailyItem[];
}
export interface TopicAnalysis {
  topic_id: string; summary: string; key_points: string[]; suggested_action: string; item_ids: number[];
}
export interface DailyView {
  days: number; start: string; end: string; topics: DailyTopic[]; unknown_dates: number; fingerprint: string;
  pending_candidates: number; notices: string[];
  processing: { selected: number; analyzed: number; skipped: number; failed: number; provider_unavailable: boolean } | null;
  analysis: { overview: string[]; topics: TopicAnalysis[] } | null;
}
const base = 'http://127.0.0.1:8000/api/v1/daily-brief';
export async function getDaily(days: 1 | 7, signal?: AbortSignal): Promise<DailyView> {
  const response = await fetch(`${base}?days=${days}`, { signal });
  if (!response.ok) throw new Error('暂时无法加载每日资讯，请稍后重试。');
  return response.json();
}
export async function analyzeDaily(days: 1 | 7, includePending = false): Promise<DailyView> {
  const response = await fetch(`${base}/analyze?days=${days}${includePending ? '&include_pending=true' : ''}`, { method: 'POST' });
  if (!response.ok) throw new Error(response.status === 409 ? '另一项每日分析正在进行，请稍后刷新。'
    : '综合分析未完成，已有资讯已保留。请稍后重试。');
  return response.json();
}
