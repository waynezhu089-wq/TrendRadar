from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import or_, select

from app.db.database import SessionLocal
from app.db.models import MarketAnnouncement, MarketAnnouncementDocument
from .announcement_reader import Extraction, read_official_document


@dataclass(frozen=True)
class ReadResult:
    announcement_id: int
    title: str
    status: str
    char_count: int
    error_code: str | None
    skipped: bool


def read_latest_announcements(limit: int = 3, session_factory=SessionLocal,
                              reader: Callable[[str], Extraction] = read_official_document) -> list[ReadResult]:
    if not 1 <= limit <= 3:
        raise ValueError("Light read limit must be between 1 and 3")
    with session_factory() as session:
        announcements = [(row.id, row.title, row.url) for row in session.scalars(
            select(MarketAnnouncement).where(
                MarketAnnouncement.symbol == "002782", MarketAnnouncement.market == "SZ")
            .order_by(MarketAnnouncement.published_at.desc(), MarketAnnouncement.id).limit(limit))]
    return _read_selected(announcements, session_factory, reader)


def read_pending_announcements(symbol: str, market: str, limit: int = 3,
                               session_factory=SessionLocal,
                               reader: Callable[[str], Extraction] = read_official_document) -> list[ReadResult]:
    """Read at most three newest documents that have no terminal extraction status."""
    if not 1 <= limit <= 3:
        raise ValueError("Light read limit must be between 1 and 3")
    with session_factory() as session:
        announcements = [(row.id, row.title, row.url) for row in session.scalars(
            select(MarketAnnouncement).outerjoin(
                MarketAnnouncementDocument,
                MarketAnnouncementDocument.announcement_id == MarketAnnouncement.id)
            .where(MarketAnnouncement.symbol == symbol, MarketAnnouncement.market == market,
                   or_(MarketAnnouncementDocument.id.is_(None),
                       MarketAnnouncementDocument.status == "FAILED"))
            .order_by(MarketAnnouncement.published_at.desc(), MarketAnnouncement.id)
            .limit(limit))]
    return _read_selected(announcements, session_factory, reader)


def _read_selected(announcements, session_factory, reader) -> list[ReadResult]:
    results = []
    for announcement_id, title, url in announcements:
        with session_factory() as session:
            existing = session.scalar(select(MarketAnnouncementDocument).where(
                MarketAnnouncementDocument.announcement_id == announcement_id))
            if existing is not None and existing.status in ("READABLE", "SKIPPED_COMPLEX"):
                results.append(ReadResult(announcement_id, title, existing.status,
                                          existing.char_count, existing.error_code, True))
                continue
        try:
            extraction = reader(url)
        except Exception:
            extraction = Extraction("FAILED", None, 0, "READ_ERROR")
        with session_factory() as session:
            document = session.scalar(select(MarketAnnouncementDocument).where(
                MarketAnnouncementDocument.announcement_id == announcement_id))
            if document is None:
                document = MarketAnnouncementDocument(
                    announcement_id=announcement_id, status=extraction.status,
                    text=extraction.text, char_count=extraction.char_count,
                    extractor="pypdf", error_code=extraction.error_code)
                session.add(document)
            else:
                document.status = extraction.status
                document.text = extraction.text
                document.char_count = extraction.char_count
                document.error_code = extraction.error_code
                document.updated_at = datetime.now(timezone.utc)
            session.commit()
        results.append(ReadResult(announcement_id, title, extraction.status,
                                  extraction.char_count, extraction.error_code, False))
    return results
