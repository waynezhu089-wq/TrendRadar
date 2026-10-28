"""Build a read-only Daily Brief; optionally send it once to a Feishu webhook."""

import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select

from app.api.v1.market import get_market
from app.api.v1.today import today
from app.db.database import SessionLocal
from app.db.models import MarketAnnouncement, MarketAnnouncementRead, MarketWatchlist
from app.feishu.brief import (BriefAnnouncement, BriefItem, BriefMarket,
                              build_daily_brief)
from app.feishu.sender import FeishuSendError, FeishuWebhookSender


def build_current_brief(session_factory=SessionLocal, now: datetime | None = None):
    """Read existing analyses and Market data without initiating any collection or writes."""
    with session_factory() as session:
        today_data = today(session)
        market_data = get_market(session)
        enabled = {(row.symbol, row.market) for row in session.scalars(
            select(MarketWatchlist).where(MarketWatchlist.enabled.is_(True)))}
        market_items = [row for row in market_data.items if (row.symbol, row.market) in enabled]

        query = (select(MarketAnnouncement)
                 .join(MarketWatchlist, and_(
                     MarketWatchlist.symbol == MarketAnnouncement.symbol,
                     MarketWatchlist.market == MarketAnnouncement.market))
                 .outerjoin(MarketAnnouncementRead,
                            MarketAnnouncementRead.announcement_id == MarketAnnouncement.id)
                 .where(MarketWatchlist.enabled.is_(True),
                        MarketAnnouncementRead.id.is_(None),
                        MarketAnnouncement.source == "SZSE"))
        unread_total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        unread = session.scalars(query.order_by(
            MarketAnnouncement.published_at.desc(), MarketAnnouncement.id).limit(3)).all()

        return build_daily_brief(
            must_read=[BriefItem(row.title, row.summary, row.url) for row in today_data.items
                       if row.today_bucket == "MUST_READ"],
            relevant=[BriefItem(row.title, row.summary, row.url) for row in today_data.items
                      if row.today_bucket == "RELEVANT"],
            markets=[BriefMarket(row.name, row.symbol, row.market, row.date, row.close,
                                 row.technical.change_pct, row.technical.close_vs_ma20_pct,
                                 row.technical.range_position_20d) for row in market_items],
            announcements=[BriefAnnouncement(row.title, row.published_at, row.url)
                           for row in unread],
            unread_total=unread_total,
            generated_at=now or datetime.now(ZoneInfo("Asia/Shanghai")),
        )


def main(argv=None, builder=build_current_brief, sender_class=FeishuWebhookSender):
    parser = argparse.ArgumentParser(description="Build or send one Feishu Daily Brief")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print safe preview without webhook call")
    mode.add_argument("--once", action="store_true", help="Send one nonempty brief")
    args = parser.parse_args(argv)
    brief = builder()

    if args.dry_run:
        print(json.dumps({
            "status": "DRY_RUN", "title": "Dream Intelligence｜Daily Brief",
            "totals": brief.totals, "shown": brief.shown,
            "sections": brief.sections,
            "links": [{"title": title, "domain": domain}
                      for title, domain in brief.link_targets],
            "http_calls": 0, "db_writes": 0, "llm_calls": 0,
        }, ensure_ascii=True))
        return 0

    if not brief.has_content:
        print(json.dumps({"status": "NO_CONTENT", "http_calls": 0}, ensure_ascii=True))
        return 0
    webhook = os.environ.get("DSIH_FEISHU_WEBHOOK_URL")
    if not webhook:
        print(json.dumps({"status": "BLOCKED", "reason": "FEISHU_WEBHOOK_NOT_CONFIGURED",
                          "http_calls": 0}, ensure_ascii=True))
        return 1
    try:
        receipt = sender_class(webhook).send(brief.payload)
    except FeishuSendError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": exc.code,
                          "http_status": exc.http_status, "http_calls": 1}, ensure_ascii=True))
        return 1
    print(json.dumps({"status": "SENT", "http_status": receipt.http_status,
                      "provider_code": receipt.provider_code, "http_calls": 1}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
