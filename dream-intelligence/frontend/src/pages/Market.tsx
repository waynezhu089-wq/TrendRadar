import { useEffect, useState } from 'react';
import { getAnnouncementText, getMarket, markAnnouncementRead, markAnnouncementUnread,
  type MarketAnnouncement, type MarketItem } from '../api/market';

function showNumber(value: number | null, suffix = '') {
  return value === null ? '—' : `${value.toLocaleString('zh-CN', { maximumFractionDigits: 4 })}${suffix}`;
}

function AnnouncementEntry({ announcement, onReadChange }: {
  announcement: MarketAnnouncement;
  onReadChange: (id: number, isRead: boolean) => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [marking, setMarking] = useState(false);

  async function onRead() {
    if (text !== null) {
      setExpanded(current => !current);
      return;
    }
    setBusy(true);
    setError('');
    try {
      setText(await getAnnouncementText(announcement.id));
      setExpanded(true);
    } catch {
      setError('正文暂不可用，请查看官方公告。');
    } finally {
      setBusy(false);
    }
  }

  async function onMarkRead() {
    setMarking(true);
    setError('');
    try {
      if (announcement.is_read) await markAnnouncementUnread(announcement.id);
      else await markAnnouncementRead(announcement.id);
      onReadChange(announcement.id, !announcement.is_read);
    } catch {
      setError('已读状态保存失败，请重试。');
    } finally {
      setMarking(false);
    }
  }

  return <li>
    <div className="announcement-summary">
      <time>{announcement.published_at?.slice(0, 10) ?? '—'}</time>
      <span>{announcement.is_read ? <span className="read-badge">✓ 已读</span> :
        <span className="unread-badge">● 新公告</span>} {announcement.title}</span>
    </div>
    <div className="announcement-actions">
      {announcement.text_available && <button type="button" disabled={busy} onClick={() => void onRead()}>
        {busy ? '读取中…' : expanded ? '收起正文' : '读取正文'}
      </button>}
      <a href={announcement.url} target="_blank" rel="noopener noreferrer">查看官方公告</a>
      <button type="button" disabled={marking} onClick={() => void onMarkRead()}>
        {marking ? '保存中…' : announcement.is_read ? '标记未读' : '标记已读'}
      </button>
    </div>
    {announcement.read_status === 'SKIPPED_COMPLEX' && <p>正文未自动读取。</p>}
    {announcement.read_status === 'FAILED' && <p>正文暂不可用。</p>}
    {announcement.read_status === null && <p>正文待读取。</p>}
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {expanded && text !== null && <pre className="announcement-text">{text}</pre>}
  </li>;
}

export function Market() {
  const [items, setItems] = useState<MarketItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  function updateReadState(symbol: string, market: string, id: number, isRead: boolean) {
    setItems(current => current.map(item => {
      if (item.symbol !== symbol || item.market !== market) return item;
      const announcement = item.announcements.find(row => row.id === id);
      if (!announcement || announcement.is_read === isRead) return item;
      return {
        ...item,
        unread_announcement_count: item.unread_announcement_count + (isRead ? -1 : 1),
        announcements: item.announcements.map(row => row.id === id ? { ...row, is_read: isRead } : row),
      };
    }));
  }

  useEffect(() => {
    const controller = new AbortController();
    getMarket(controller.signal).then(setItems).catch(() => {
      if (!controller.signal.aborted) setError('无法加载市场数据，请刷新重试。');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  return <main>
    <header><div className="brand">Dream Intelligence</div><p className="notice">A 股最近交易日快照</p></header>
    <h1>Market</h1>
    {error && <p role="alert" className="feedback-error">{error}</p>}
    {loading ? <p role="status">Loading…</p> : items.length === 0 ? <p>暂无关注股票。</p> :
      <div className="market-list">{items.map(item => <section className="market-card" key={`${item.market}:${item.symbol}`}>
        <h2>{item.name} <small>{item.symbol} · {item.market}</small></h2>
        <dl>
          <div><dt>最近交易日</dt><dd>{item.date ?? '—'}</dd></div>
          <div><dt>收盘价</dt><dd>{showNumber(item.close)}</dd></div>
          <div><dt>成交量（股）</dt><dd>{showNumber(item.volume)}</dd></div>
          <div><dt>成交额（元）</dt><dd>{showNumber(item.amount)}</dd></div>
          <div><dt>换手率</dt><dd>{showNumber(item.turnover, '%')}</dd></div>
        </dl>
        <div className="market-technical">
          <h3>技术状态 <small>基于已保存的 {item.technical.sample_days} 个交易日</small></h3>
          <dl>
            <div><dt>当日涨跌</dt><dd>{showNumber(item.technical.change_pct, '%')}</dd></div>
            <div><dt>MA5</dt><dd>{showNumber(item.technical.ma5)}</dd></div>
            <div><dt>MA10</dt><dd>{showNumber(item.technical.ma10)}</dd></div>
            <div><dt>MA20</dt><dd>{showNumber(item.technical.ma20)}</dd></div>
            <div><dt>距 MA20</dt><dd>{showNumber(item.technical.close_vs_ma20_pct, '%')}</dd></div>
            <div><dt>20 日最高</dt><dd>{showNumber(item.technical.high_20d)}</dd></div>
            <div><dt>20 日最低</dt><dd>{showNumber(item.technical.low_20d)}</dd></div>
            <div><dt>20 日区间位置</dt><dd>{showNumber(item.technical.range_position_20d, '%')}</dd></div>
            <div><dt>前 5 日均量（股）</dt><dd>{showNumber(item.technical.avg_volume_5d)}</dd></div>
            <div><dt>当日 / 前 5 日均量</dt><dd>{showNumber(item.technical.volume_ratio_5d, ' 倍')}</dd></div>
          </dl>
        </div>
        <div className="market-announcements">
          <h3>最新公告（未读 {item.unread_announcement_count}）</h3>
          {item.announcements.length === 0 ? <p>暂无公告。</p> :
            <ul>{item.announcements.map(announcement =>
              <AnnouncementEntry key={announcement.id} announcement={announcement}
                onReadChange={(id, isRead) => updateReadState(item.symbol, item.market, id, isRead)} />)}</ul>}
        </div>
      </section>)}</div>}
  </main>;
}
