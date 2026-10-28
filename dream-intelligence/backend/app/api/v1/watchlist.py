from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Watchlist
from app.schemas.watchlist import WatchlistInput, WatchlistOutput

router = APIRouter()


def normalize_value(value: str) -> str:
    return " ".join(value.split()).lower()


@router.get("/watchlist", response_model=list[WatchlistOutput])
def list_watchlist(db: Session = Depends(get_db)):
    return db.scalars(select(Watchlist).order_by(
        Watchlist.type, Watchlist.created_at, Watchlist.id)).all()


@router.post("/watchlist", response_model=WatchlistOutput, status_code=201)
def add_watchlist(payload: WatchlistInput, db: Session = Depends(get_db)):
    entry = Watchlist(type=payload.type, value=payload.value,
                      normalized_value=normalize_value(payload.value))
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Watchlist item already exists")
    db.refresh(entry)
    return entry


@router.delete("/watchlist/{entry_id}", status_code=204)
def delete_watchlist(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(Watchlist, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=204)
