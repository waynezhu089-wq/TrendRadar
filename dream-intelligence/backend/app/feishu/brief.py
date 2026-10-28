"""Pure Daily Brief assembly; no database, network, or secret access."""

import ipaddress
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class BriefItem:
    title: str
    summary: str
    url: str | None


@dataclass(frozen=True)
class BriefMarket:
    name: str
    symbol: str
    market: str
    date: date | None
    close: float | None
    change_pct: float | None
    close_vs_ma20_pct: float | None
    range_position_20d: float | None


@dataclass(frozen=True)
class BriefAnnouncement:
    title: str
    published_at: datetime | None
    url: str


@dataclass(frozen=True)
class DailyBrief:
    payload: dict
    totals: dict[str, int]
    shown: dict[str, int]
    sections: tuple[str, ...]
    link_targets: tuple[tuple[str, str], ...]
    has_content: bool


_LOCAL_URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?[^\s]*",
                        re.IGNORECASE)


def _display(value: str, limit: int = 180) -> str:
    clean = _LOCAL_URL.sub("（本地链接已省略）", " ".join((value or "").split()))
    clean = clean[:limit - 1] + "…" if len(clean) > limit else clean
    for char in ("\\", "[", "]", "(", ")", "*", "_", "`"):
        clean = clean.replace(char, "\\" + char)
    return clean


def external_url(value: str | None, official: bool = False) -> str | None:
    if not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("https", "http") or not host or parsed.username or parsed.password:
            return None
        if official and (parsed.scheme != "https" or not
                         (host == "szse.cn" or host.endswith(".szse.cn"))):
            return None
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        # Parentheses must not break a Feishu Markdown link target.
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.replace("(", "%28").replace(")", "%29"),
                           parsed.query.replace("(", "%28").replace(")", "%29"), ""))
    except ValueError:
        return None


def _number(value: float | None, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.2f}{suffix}"


def _block(content: str) -> dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def build_daily_brief(must_read: list[BriefItem], relevant: list[BriefItem],
                      markets: list[BriefMarket], announcements: list[BriefAnnouncement],
                      generated_at: datetime, unread_total: int | None = None) -> DailyBrief:
    """Return a bounded Feishu card plus safe preview metadata."""
    total_unread = len(announcements) if unread_total is None else unread_total
    if total_unread < len(announcements):
        raise ValueError("Unread total cannot be less than selected announcements")
    totals = {"must_read": len(must_read), "relevant": len(relevant),
              "market": len(markets), "unread_announcements": total_unread}
    shown = {"must_read": min(len(must_read), 3), "relevant": min(len(relevant), 3),
             "market": len(markets), "unread_announcements": min(len(announcements), 3)}
    elements = [_block("生成时间：" + generated_at.strftime("%Y-%m-%d %H:%M %Z"))]
    sections = []
    links = []

    def add_items(label: str, key: str, items: list[BriefItem]) -> None:
        sections.append(label)
        elements.append(_block(f"**{label}（{totals[key]}）**"))
        for index, item in enumerate(items[:3], 1):
            content = f"{index}. **{_display(item.title)}**\n{_display(item.summary, 220) or '—'}"
            url = external_url(item.url)
            if url:
                content += f"\n[查看原文]({url})"
                links.append((item.title, urlsplit(url).hostname or ""))
            elements.append(_block(content))
        if len(items) > 3:
            elements.append(_block(f"另有 {len(items) - 3} 条"))
        if not items:
            elements.append(_block("暂无"))

    add_items("🔥 Must Read", "must_read", must_read)
    add_items("👀 Relevant", "relevant", relevant)
    sections.append("📈 Market")
    elements.append(_block("**📈 Market**"))
    for market in markets:
        elements.append(_block(
            f"**{_display(market.name)} {_display(market.symbol)}.{_display(market.market)}**\n"
            f"最近交易日：{market.date.isoformat() if market.date else '—'}｜"
            f"收盘：{_number(market.close)}\n"
            f"当日涨跌：{_number(market.change_pct, '%')}｜"
            f"距 MA20：{_number(market.close_vs_ma20_pct, '%')}｜"
            f"20 日区间位置：{_number(market.range_position_20d, '%')}"))
    if not markets:
        elements.append(_block("暂无"))

    sections.append("📢 未读公告")
    elements.append(_block(f"**📢 未读公告（{total_unread}）**"))
    for index, announcement in enumerate(announcements[:3], 1):
        date_text = announcement.published_at.date().isoformat() if announcement.published_at else "—"
        content = f"{index}. {date_text}｜{_display(announcement.title)}"
        url = external_url(announcement.url, official=True)
        if url:
            content += f"\n[查看官方公告]({url})"
            links.append((announcement.title, urlsplit(url).hostname or ""))
        elements.append(_block(content))
    if total_unread > shown["unread_announcements"]:
        elements.append(_block(f"另有 {total_unread - shown['unread_announcements']} 条"))
    if not announcements:
        elements.append(_block("暂无"))

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "Dream Intelligence｜Daily Brief"},
                       "template": "turquoise"},
            "elements": elements,
        },
    }
    return DailyBrief(payload, totals, shown, tuple(sections), tuple(links),
                      bool(must_read or relevant or total_unread))
