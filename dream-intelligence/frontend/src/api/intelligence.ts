export type FeedbackValue = 'useful' | 'not_useful' | 'watch';

export interface Intelligence {
  id: number; title: string; url: string; category: string; summary: string;
  why_it_matters: string; priority: number; dreamstream_relevance: number;
  source: string; source_type: string; published_at: string | null; tags: string[];
  today_bucket: "MUST_READ" | "RELEVANT" | "OTHER";
  recommended_action: string; analyzer_version: string;
  feedback: FeedbackValue | null;
}
export interface TodayResponse {
  stats: { raw_items: number; analyzed: number; relevant: number; must_read: number };
  items: Intelligence[];
}
export async function getToday(signal: AbortSignal): Promise<TodayResponse> {
  const response = await fetch('http://127.0.0.1:8000/api/v1/today', { signal });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json();
}

export async function postFeedback(itemId: number, feedback: FeedbackValue): Promise<FeedbackValue> {
  const response = await fetch('http://127.0.0.1:8000/api/v1/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id: itemId, feedback }),
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  const saved: { item_id: number; feedback: FeedbackValue } = await response.json();
  return saved.feedback;
}
