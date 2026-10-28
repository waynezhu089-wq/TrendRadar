from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.research import manual_run_lock
from app.db.database import get_db
from app.research.commissions import collect_leads, list_leads

router = APIRouter()


@router.get('/commissions')
def saved_commissions(db: Session = Depends(get_db)):
    # Reading this page never collects data or calls a model.
    return list_leads(db)


@router.post('/commissions/collect')
def collect_commissions(db: Session = Depends(get_db)):
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, 'COLLECTION_BUSY')
    try:
        return collect_leads(db)
    finally:
        manual_run_lock.release()
