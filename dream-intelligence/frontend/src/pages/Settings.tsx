import { useState } from 'react';
import { Research } from './Research';
import { Watchlist } from './Watchlist';
import { SubscriptionSettings } from './SubscriptionSettings';

export function Settings() {
  const [tab, setTab] = useState(window.location.pathname === '/watchlist' ? 'watchlist' :
    new URLSearchParams(window.location.search).get('tab') === 'subscriptions' ? 'subscriptions' : 'topics');
  return <main className="settings-page"><header><span className="eyebrow">Dream Intelligence</span>
    <h1>设置</h1><p className="daily-muted">管理你关心什么、从哪里收集，以及为什么关注。</p></header>
    <div className="settings-tabs" role="tablist" aria-label="设置分类">
      <button role="tab" aria-selected={tab === 'topics'} aria-controls="settings-panel" id="tab-topics" onClick={() => setTab('topics')}>议题与来源</button>
      <button role="tab" aria-selected={tab === 'watchlist'} aria-controls="settings-panel" id="tab-watchlist" onClick={() => setTab('watchlist')}>关注对象</button>
      <button role="tab" aria-selected={tab === 'subscriptions'} aria-controls="settings-panel" id="tab-subscriptions" onClick={() => setTab('subscriptions')}>自动订阅</button>
    </div>
    <div id="settings-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
      {tab === 'topics' ? <Research settings /> : tab === 'watchlist' ? <Watchlist embedded /> : <SubscriptionSettings />}
    </div>
  </main>;
}
