from datetime import datetime
from pydantic import BaseModel
from app.today_rules import TodayBucket
from app.schemas.feedback import FeedbackValue

class IntelligenceCard(BaseModel):
    id: int
    title: str
    url: str
    category: str
    summary: str
    why_it_matters: str
    priority: int
    dreamstream_relevance: int
    source: str
    source_type: str
    published_at: datetime | None = None
    tags: list[str]
    recommended_action: str
    analyzer_version: str
    today_bucket: TodayBucket
    feedback: FeedbackValue | None = None

class TodayStats(BaseModel):
    raw_items: int
    analyzed: int
    relevant: int
    must_read: int

class TodayResponse(BaseModel):
    stats: TodayStats
    items: list[IntelligenceCard]
