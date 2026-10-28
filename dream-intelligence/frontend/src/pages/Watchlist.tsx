import { useEffect, useState, type FormEvent } from 'react';
import { addWatchlist, deleteWatchlist, getWatchlist,
  type WatchlistEntry, type WatchlistType } from '../api/watchlist';

const types: WatchlistType[] = ['keyword', 'project', 'company', 'model', 'topic'];

function stableOrder(a: WatchlistEntry, b: WatchlistEntry) {
  return a.type.localeCompare(b.type) || a.created_at.localeCompare(b.created_at) || a.id - b.id;
}

export function Watchlist({ embedded = false }: { embedded?: boolean }) {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [type, setType] = useState<WatchlistType>('project');
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    getWatchlist(controller.signal).then(setEntries).catch(() => {
      if (!controller.signal.aborted) setError('无法加载关注列表，请刷新重试。');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function onAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const created = await addWatchlist(type, value);
      setEntries(current => [...current, created].sort(stableOrder));
      setValue('');
    } catch (failure) {
      setError(failure instanceof Error && failure.message.includes('409')
        ? '这个关注对象已存在。' : '添加失败，请重试。');
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(entry: WatchlistEntry) {
    setBusy(true);
    setError('');
    try {
      await deleteWatchlist(entry.id);
      setEntries(current => current.filter(item => item.id !== entry.id));
    } catch {
      setError('删除失败，请重试。');
    } finally {
      setBusy(false);
    }
  }

  const Container = embedded ? 'div' : 'main';
  return <Container className="watchlist-settings">
    <h2>关注对象</h2>
    <p className="notice">长期关注的关键词、项目、公司、模型和话题，用于情报相关性判断。</p>
    <form className="watchlist-form" onSubmit={event => void onAdd(event)}>
      <label>类型 <select value={type} onChange={event => setType(event.target.value as WatchlistType)}>
        {types.map(option => <option key={option} value={option}>{option}</option>)}
      </select></label>
      <label>关注对象 <input value={value} onChange={event => setValue(event.target.value)} required /></label>
      <button type="submit" disabled={busy}>添加</button>
    </form>
    {error && <p role="alert" className="feedback-error">{error}</p>}
    <h2>已关注</h2>
    {loading ? <p role="status">Loading…</p> : entries.length === 0 ? <p>暂无关注对象。</p> :
      <ul className="watchlist-items">{entries.map(entry => <li key={entry.id}>
        <span>{entry.value}</span><small>{entry.type}</small>
        <button type="button" disabled={busy} onClick={() => void onDelete(entry)} aria-label={`删除 ${entry.value}`}>删除</button>
      </li>)}</ul>}
  </Container>;
}
