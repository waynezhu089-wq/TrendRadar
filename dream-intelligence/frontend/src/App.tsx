import { Today } from './pages/Today';
import { Market } from './pages/Market';
import { Research } from './pages/Research';
import { Settings } from './pages/Settings';
import { Commissions } from './pages/Commissions';

export default function App() {
  const isSettings = ['/settings', '/watchlist'].includes(window.location.pathname);
  const isMarket = window.location.pathname === '/market';
  const isResearch = window.location.pathname === '/research';
  const isCommissions = window.location.pathname === '/commissions';
  const isToday = !isSettings && !isMarket && !isResearch && !isCommissions;
  return <>
    <nav className="site-nav" aria-label="主导航">
      <a className="nav-home" href="/" aria-label="Dream Intelligence 首页">DI<span>Dream Intelligence</span></a>
      <a href="/" aria-current={isToday ? 'page' : undefined}>Today</a>
      <a href="/research" aria-current={isResearch ? 'page' : undefined}>Research</a>
      <a href="/market" aria-current={isMarket ? 'page' : undefined}>Market</a>
      <a href="/commissions" aria-current={isCommissions ? 'page' : undefined}>AI 商单</a>
      <a className="nav-settings" href="/settings" aria-current={isSettings ? 'page' : undefined}>设置</a>
    </nav>
    {isCommissions ? <Commissions /> : isResearch ? <Research /> : isMarket ? <Market /> : isSettings ? <Settings /> : <Today />}
  </>;
}
