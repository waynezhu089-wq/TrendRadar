from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import MarketAnnouncement, MarketWatchlist
from .announcements import MarketAnnouncementProvider, SZSEAnnouncementProvider, official_url


@dataclass(frozen=True)
class AnnouncementCollectionResult:
    symbol: str
    market: str
    received: int
    inserted: int
    skipped: int
    failed: int
    source: str
    error: str | None = None


def collect_announcements_once(provider: MarketAnnouncementProvider | None = None,
                               session_factory=SessionLocal) -> list[AnnouncementCollectionResult]:
    provider = provider or SZSEAnnouncementProvider()
    with session_factory() as session:
        stocks = [(entry.symbol, entry.market) for entry in session.scalars(
            select(MarketWatchlist).where(MarketWatchlist.enabled.is_(True)).order_by(MarketWatchlist.id))]
    results = []
    for symbol, market in stocks:
        received = inserted = skipped = 0
        try:
            announcements = provider.fetch_recent(symbol, market, limit=10)
            received = len(announcements)
            for announcement in announcements:
                # Validate even injected providers before any persistent write.
                url = official_url(announcement.url)
                with session_factory() as session:
                    exists = session.scalar(select(MarketAnnouncement.id).where(
                        MarketAnnouncement.symbol == symbol,
                        MarketAnnouncement.market == market,
                        MarketAnnouncement.external_id == announcement.external_id))
                    if exists is not None:
                        skipped += 1
                        continue
                    session.add(MarketAnnouncement(
                        symbol=symbol, market=market, external_id=announcement.external_id,
                        title=announcement.title, url=url, published_at=announcement.published_at,
                        source="SZSE", raw_json=announcement.raw_json))
                    try:
                        session.commit()
                        inserted += 1
                    except IntegrityError:
                        session.rollback()
                        skipped += 1
            results.append(AnnouncementCollectionResult(
                symbol, market, received, inserted, skipped, 0, "SZSE"))
        except Exception as exc:
            # Do not echo HTTP response bodies or provider exception text into logs.
            results.append(AnnouncementCollectionResult(
                symbol, market, received, inserted, skipped, 1, "SZSE", type(exc).__name__))
    return results
