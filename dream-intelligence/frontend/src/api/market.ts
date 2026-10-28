export interface TechnicalState {
  change_pct: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  close_vs_ma5_pct: number | null;
  close_vs_ma10_pct: number | null;
  close_vs_ma20_pct: number | null;
  high_20d: number | null;
  low_20d: number | null;
  range_position_20d: number | null;
  avg_volume_5d: number | null;
  volume_ratio_5d: number | null;
  sample_days: number;
}

export interface MarketItem {
  symbol: string;
  market: 'SH' | 'SZ' | 'BJ';
  name: string;
  date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  amount: number | null;
  turnover: number | null;
  source: string | null;
  technical: TechnicalState;
  unread_announcement_count: number;
  announcements: MarketAnnouncement[];
}

export interface MarketAnnouncement {
  id: number;
  title: string;
  url: string;
  published_at: string | null;
  source: 'SZSE';
  read_status: 'READABLE' | 'SKIPPED_COMPLEX' | 'FAILED' | null;
  text_available: boolean;
  is_read: boolean;
}

export async function markAnnouncementRead(id: number): Promise<void> {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/market/announcements/${id}/read`,
    { method: 'POST' });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
}

export async function markAnnouncementUnread(id: number): Promise<void> {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/market/announcements/${id}/read`,
    { method: 'DELETE' });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
}

export async function getAnnouncementText(id: number): Promise<string> {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/market/announcements/${id}/text`);
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  const data: { id: number; title: string; text: string } = await response.json();
  return data.text;
}

export async function getMarket(signal?: AbortSignal): Promise<MarketItem[]> {
  const response = await fetch('http://127.0.0.1:8000/api/v1/market', { signal });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  const data: { items: MarketItem[] } = await response.json();
  return data.items;
}
