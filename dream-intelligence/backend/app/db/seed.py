from sqlalchemy import select
from .models import Source, Item, Analysis, utcnow

def seed(session):
    if session.scalar(select(Item).where(Item.external_id == "day1-mock-minimax")):
        return
    source = Source(name="Mock Source", type="mock", url="https://example.com/mock", category="AI_VIDEO")
    session.add(source)
    session.flush()
    item = Item(source_id=source.id, external_id="day1-mock-minimax",
                title="MiniMax releases new video capability", url="https://example.com/mock/minimax",
                content="Mock content for DSIH Day 1.", author="Mock Source", published_at=utcnow())
    session.add(item)
    session.flush()
    session.add(Analysis(item_id=item.id, category="AI_VIDEO",
        summary="MiniMax released a new video capability. This is mock data, not a verified release.",
        why_it_matters="It may improve Dream Stream Video Studio. This is a mock assessment.",
        importance=85, novelty=82, credibility=90, personal_relevance=88,
        dreamstream_relevance=96, actionability=86, priority=91,
        tags=["MiniMax", "Video"], recommended_action="READ", analyzer_version="mock-v1"))
    session.commit()

