export type WatchlistType = 'keyword' | 'project' | 'company' | 'model' | 'topic';

export interface WatchlistEntry {
  id: number;
  type: WatchlistType;
  value: string;
  created_at: string;
}

const url = 'http://127.0.0.1:8000/api/v1/watchlist';

export async function getWatchlist(signal?: AbortSignal): Promise<WatchlistEntry[]> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json();
}

export async function addWatchlist(type: WatchlistType, value: string): Promise<WatchlistEntry> {
  const response = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, value }),
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json();
}

export async function deleteWatchlist(id: number): Promise<void> {
  const response = await fetch(`${url}/${id}`, { method: 'DELETE' });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
}
