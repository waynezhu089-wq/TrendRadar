from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Feedback, Item, utcnow
from app.schemas.feedback import FeedbackInput, FeedbackOutput

router = APIRouter()


@router.post("/feedback", response_model=FeedbackOutput)
def save_feedback(payload: FeedbackInput, db: Session = Depends(get_db)):
    if db.get(Item, payload.item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    now = utcnow()
    statement = insert(Feedback).values(
        item_id=payload.item_id,
        feedback=payload.feedback,
        created_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=[Feedback.item_id],
        set_={"feedback": payload.feedback, "updated_at": now},
    )
    db.execute(statement)
    db.commit()
    return FeedbackOutput(item_id=payload.item_id, feedback=payload.feedback)
