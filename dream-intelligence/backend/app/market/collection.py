from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import MarketSnapshot, MarketWatchlist
from .provider import MarketProvider, TencentDailyProvider


@dataclass(frozen=True)
class CollectionResult:
    symbol: str
    market: str
    date: str | None
    inserted: int
    skipped: int
    failed: int
    source: str | None
    error: str | None = None


def collect_once(provider: MarketProvider | None = None, session_factory=SessionLocal) -> list[CollectionResult]:
    return _collect(provider or TencentDailyProvider(), session_factory, limit=None)


def collect_backfill(limit: int, provider: MarketProvider | None = None,
                     session_factory=SessionLocal) -> list[CollectionResult]:
    if not 1 <= limit <= 30:
        raise ValueError("Backfill limit must be between 1 and 30")
    return _collect(provider or TencentDailyProvider(), session_factory, limit=limit)


def _collect(provider: MarketProvider, session_factory, limit: int | None) -> list[CollectionResult]:
    with session_factory() as session:
        stocks = [(entry.symbol, entry.market) for entry in session.scalars(
            select(MarketWatchlist).where(MarketWatchlist.enabled.is_(True)).order_by(MarketWatchlist.id))]
    results = []
    for symbol, market in stocks:
        try:
            days = ([provider.fetch_daily(symbol, market)] if limit is None
                    else provider.fetch_recent_daily(symbol, market, limit))
            if not days:
                raise ValueError("Provider returned no daily snapshots")
            inserted = skipped = 0
            for daily in sorted(days, key=lambda row: row.date):
                with session_factory() as session:
                    existing = session.scalar(select(MarketSnapshot.id).where(
                        MarketSnapshot.symbol == symbol, MarketSnapshot.market == market,
                        MarketSnapshot.date == daily.date))
                    if existing is not None:
                        skipped += 1
                        continue
                    session.add(MarketSnapshot(symbol=symbol, market=market, **daily.__dict__))
                    try:
                        session.commit()
                        inserted += 1
                    except IntegrityError:
                        session.rollback()
                        skipped += 1
            latest = max(days, key=lambda row: row.date)
            results.append(CollectionResult(symbol, market, latest.date.isoformat(),
                                            inserted, skipped, 0, latest.source))
        except Exception as exc:
            results.append(CollectionResult(symbol, market, None, 0, 0, 1, None,
                                            f"{type(exc).__name__}: {exc}"))
    return results
