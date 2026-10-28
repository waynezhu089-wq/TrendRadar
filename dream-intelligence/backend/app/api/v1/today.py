from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from app.today_rules import today_bucket
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Source, Item, Analysis, Feedback
from app.schemas.intelligence import IntelligenceCard, TodayResponse, TodayStats

router = APIRouter()

@router.get("/today", response_model=TodayResponse)
def today(db: Session = Depends(get_db)):
    rows = db.execute(select(Item, Source, Analysis, Feedback)
        .join(Source, Item.source_id == Source.id)
        .join(Analysis, Analysis.item_id == Item.id)
        .outerjoin(Feedback, Feedback.item_id == Item.id)
        .order_by(Analysis.priority.desc(), Analysis.dreamstream_relevance.desc(),
                  Analysis.analyzed_at.desc().nulls_last(), Item.id)).all()
    cards = [IntelligenceCard(id=item.id, title=item.title, url=item.url,
        category=a.category, summary=a.summary, why_it_matters=a.why_it_matters,
        priority=a.priority, dreamstream_relevance=a.dreamstream_relevance,
        source=source.name, source_type=source.type, published_at=item.published_at,
        tags=a.tags, recommended_action=a.recommended_action, analyzer_version=a.analyzer_version,
        today_bucket=today_bucket(a.priority, a.dreamstream_relevance),
        feedback=feedback.feedback if feedback else None)
        for item, source, a, feedback in rows]
    return TodayResponse(stats=TodayStats(
        raw_items=db.scalar(select(func.count()).select_from(Item)),
        analyzed=len(cards),
        relevant=sum(c.today_bucket == "RELEVANT" for c in cards),
        must_read=sum(c.today_bucket == "MUST_READ" for c in cards)), items=cards)
