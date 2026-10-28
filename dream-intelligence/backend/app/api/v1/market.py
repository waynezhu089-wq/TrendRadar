from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (MarketAnnouncement, MarketAnnouncementDocument,
                           MarketAnnouncementRead, MarketSnapshot, MarketWatchlist)
from app.market.symbols import normalize_symbol
from app.market.technical import compute_technical_state
from app.schemas.market import (MarketAnnouncementOutput, MarketAnnouncementReadOutput,
                                MarketAnnouncementTextOutput,
                                MarketItemOutput, MarketOutput,
                                MarketWatchlistInput, MarketWatchlistOutput, TechnicalOutput)

router = APIRouter()


@router.get("/market/watchlist", response_model=list[MarketWatchlistOutput])
def list_market_watchlist(db: Session = Depends(get_db)):
    return db.scalars(select(MarketWatchlist).order_by(MarketWatchlist.id)).all()


@router.post("/market/watchlist", response_model=MarketWatchlistOutput, status_code=201)
def add_market_watchlist(payload: MarketWatchlistInput, db: Session = Depends(get_db)):
    try:
        symbol, market = normalize_symbol(payload.symbol, payload.market)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entry = MarketWatchlist(symbol=symbol, market=market, name=payload.name)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Market watchlist item already exists") from exc
    db.refresh(entry)
    return entry


@router.delete("/market/watchlist/{entry_id}", status_code=204)
def delete_market_watchlist(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(MarketWatchlist, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Market watchlist item not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=204)


@router.get("/market", response_model=MarketOutput)
def get_market(db: Session = Depends(get_db)):
    items = []
    for entry in db.scalars(select(MarketWatchlist).order_by(MarketWatchlist.id)):
        history = db.scalars(select(MarketSnapshot).where(
            MarketSnapshot.symbol == entry.symbol,
            MarketSnapshot.market == entry.market,
        ).order_by(MarketSnapshot.date.desc()).limit(30)).all()
        latest = history[0] if history else None
        values = {field: getattr(latest, field) if latest is not None else None
                  for field in ("date", "open", "high", "low", "close", "volume", "amount", "turnover", "source")}
        announcements = db.scalars(select(MarketAnnouncement).where(
            MarketAnnouncement.symbol == entry.symbol,
            MarketAnnouncement.market == entry.market,
        ).order_by(MarketAnnouncement.published_at.desc(), MarketAnnouncement.id).limit(5)).all()
        documents = {row.announcement_id: row for row in db.scalars(
            select(MarketAnnouncementDocument).where(
                MarketAnnouncementDocument.announcement_id.in_([row.id for row in announcements])))}
        reads = {row.announcement_id for row in db.scalars(
            select(MarketAnnouncementRead).where(
                MarketAnnouncementRead.announcement_id.in_([row.id for row in announcements])))}
        unread_count = db.scalar(select(func.count()).select_from(MarketAnnouncement).outerjoin(
            MarketAnnouncementRead,
            MarketAnnouncementRead.announcement_id == MarketAnnouncement.id).where(
                MarketAnnouncement.symbol == entry.symbol,
                MarketAnnouncement.market == entry.market,
                MarketAnnouncementRead.id.is_(None))) or 0
        items.append(MarketItemOutput(symbol=entry.symbol, market=entry.market,
                                      name=entry.name, **values,
                                      technical=TechnicalOutput(**compute_technical_state(history).__dict__),
                                      unread_announcement_count=unread_count,
                                      announcements=[MarketAnnouncementOutput(
                                          id=row.id, title=row.title, url=row.url,
                                          published_at=row.published_at, source=row.source,
                                          read_status=documents[row.id].status if row.id in documents else None,
                                          text_available=(row.id in documents and
                                                          documents[row.id].status == "READABLE" and
                                                          bool(documents[row.id].text)),
                                          is_read=row.id in reads)
                                          for row in announcements]))
    return MarketOutput(items=items)


@router.get("/market/announcements/{announcement_id}/text",
            response_model=MarketAnnouncementTextOutput)
def get_market_announcement_text(announcement_id: int, db: Session = Depends(get_db)):
    announcement = db.get(MarketAnnouncement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    document = db.scalar(select(MarketAnnouncementDocument).where(
        MarketAnnouncementDocument.announcement_id == announcement_id))
    if document is None or document.status != "READABLE" or not document.text:
        raise HTTPException(status_code=409, detail="text unavailable; use official URL")
    return MarketAnnouncementTextOutput(id=announcement.id, title=announcement.title,
                                        text=document.text)


@router.post("/market/announcements/{announcement_id}/read",
             response_model=MarketAnnouncementReadOutput)
def mark_market_announcement_read(announcement_id: int, db: Session = Depends(get_db)):
    if db.get(MarketAnnouncement, announcement_id) is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    read = db.scalar(select(MarketAnnouncementRead).where(
        MarketAnnouncementRead.announcement_id == announcement_id))
    if read is None:
        read = MarketAnnouncementRead(announcement_id=announcement_id)
        db.add(read)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            read = db.scalar(select(MarketAnnouncementRead).where(
                MarketAnnouncementRead.announcement_id == announcement_id))
            if read is None:
                raise
        else:
            db.refresh(read)
    return MarketAnnouncementReadOutput(announcement_id=announcement_id,
                                        is_read=True, read_at=read.read_at)


@router.delete("/market/announcements/{announcement_id}/read", status_code=204)
def mark_market_announcement_unread(announcement_id: int, db: Session = Depends(get_db)):
    if db.get(MarketAnnouncement, announcement_id) is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    read = db.scalar(select(MarketAnnouncementRead).where(
        MarketAnnouncementRead.announcement_id == announcement_id))
    if read is not None:
        db.delete(read)
        db.commit()
    return Response(status_code=204)
