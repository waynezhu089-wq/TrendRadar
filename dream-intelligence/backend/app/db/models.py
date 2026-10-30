from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)


class CommissionLead(Base):
    """Public commissioning evidence, separate from analyzed news and research media."""
    __tablename__ = "commission_leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommissionCollection(Base):
    __tablename__ = "commission_collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class Analysis(Base):
    __tablename__ = "analysis"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), unique=True)
    category: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer)
    novelty: Mapped[int] = mapped_column(Integer)
    credibility: Mapped[int] = mapped_column(Integer)
    personal_relevance: Mapped[int] = mapped_column(Integer)
    dreamstream_relevance: Mapped[int] = mapped_column(Integer)
    actionability: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(JSON)
    recommended_action: Mapped[str] = mapped_column(String)
    analyzer_version: Mapped[str] = mapped_column(String)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_feedback_item_id"),
        CheckConstraint("feedback IN ('useful', 'not_useful', 'watch')", name="ck_feedback_value"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    feedback: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("type", "normalized_value", name="uq_watchlist_type_normalized_value"),
        CheckConstraint("type IN ('keyword', 'project', 'company', 'model', 'topic')", name="ck_watchlist_type"),
        CheckConstraint("length(trim(value)) > 0", name="ck_watchlist_value"),
        CheckConstraint("length(normalized_value) > 0", name="ck_watchlist_normalized_value"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    normalized_value: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketWatchlist(Base):
    __tablename__ = "market_watchlist"
    __table_args__ = (
        UniqueConstraint("symbol", "market", name="uq_market_watchlist_symbol_market"),
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="ck_market_watchlist_market"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(6), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "market", "date", name="uq_market_snapshot_symbol_market_date"),
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="ck_market_snapshot_market"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(6), nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(22, 2), nullable=True)
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketAnnouncement(Base):
    __tablename__ = "market_announcements"
    __table_args__ = (
        UniqueConstraint("symbol", "market", "external_id", name="uq_market_announcement_external_id"),
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="ck_market_announcement_market"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(6), nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class MarketAnnouncementDocument(Base):
    __tablename__ = "market_announcement_documents"
    __table_args__ = (
        UniqueConstraint("announcement_id", name="uq_market_announcement_document"),
        CheckConstraint("status IN ('READABLE', 'SKIPPED_COMPLEX', 'FAILED')",
                        name="ck_market_announcement_document_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("market_announcements.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extractor: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketAnnouncementRead(Base):
    __tablename__ = "market_announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", name="uq_market_announcement_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("market_announcements.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("channel", "notification_type", "delivery_date",
                         name="uq_notification_delivery_day"),
        CheckConstraint("status = 'SENT'", name="ck_notification_delivery_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    notification_type: Mapped[str] = mapped_column(String, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ResearchPlan(Base):
    __tablename__ = "research_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    websites: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    collection_type: Mapped[str] = mapped_column(String, default='research', server_default='research', nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_bindings: Mapped[list['ResearchPlanSource']] = relationship(lazy='selectin', cascade='all, delete-orphan')


class SourceConnection(Base):
    __tablename__ = 'source_connections'
    id: Mapped[int] = mapped_column(primary_key=True)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)


class ResearchPlanSource(Base):
    __tablename__ = 'research_plan_sources'
    __table_args__ = (UniqueConstraint('plan_id', 'connection_id', name='uq_plan_source'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('research_plans.id'), nullable=False)
    connection_id: Mapped[int] = mapped_column(ForeignKey('source_connections.id'), nullable=False)
    query: Mapped[str] = mapped_column(String(256), default='')
    sort: Mapped[str] = mapped_column(String(40), default='')
    limit: Mapped[int] = mapped_column(Integer, default=6)


class ResearchSourceReport(Base):
    __tablename__ = 'research_source_reports'
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), primary_key=True)
    reports: Mapped[list[dict]] = mapped_column(JSON, default=list)


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("research_plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ResearchRunItem(Base):
    __tablename__ = "research_run_items"
    __table_args__ = (UniqueConstraint("run_id", "item_id", name="uq_research_run_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)


class ResearchVideo(Base):
    __tablename__ = 'research_videos'
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    channel: Mapped[str] = mapped_column(String, default='')
    thumbnail_url: Mapped[str] = mapped_column(String, default='')
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchRunVideo(Base):
    __tablename__ = 'research_run_videos'
    __table_args__ = (UniqueConstraint('run_id','video_id',name='uq_run_video'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey('research_videos.id'), nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String, default='待整理')


class VideoSearchReport(Base):
    __tablename__ = 'video_search_reports'
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), primary_key=True)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)


class VideoFavorite(Base):
    __tablename__ = 'video_favorites'
    __table_args__ = (UniqueConstraint('plan_id','video_id',name='uq_plan_video_favorite'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('research_plans.id'), nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey('research_videos.id'), nullable=False)


class VideoSchedule(Base):
    __tablename__ = 'video_schedules'
    plan_id: Mapped[int] = mapped_column(ForeignKey('research_plans.id'), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchImage(Base):
    __tablename__ = 'research_images'
    __table_args__ = (UniqueConstraint('provider', 'external_id', name='uq_research_image_identity'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String, nullable=False)
    creator: Mapped[str] = mapped_column(String, default='')
    license: Mapped[str] = mapped_column(String, default='')
    license_url: Mapped[str] = mapped_column(String, default='')
    attribution: Mapped[str] = mapped_column(Text, default='')
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchRunImage(Base):
    __tablename__ = 'research_run_images'
    __table_args__ = (UniqueConstraint('run_id', 'image_id', name='uq_research_run_image'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), nullable=False)
    image_id: Mapped[int] = mapped_column(ForeignKey('research_images.id'), nullable=False)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text, default='')
    usage_notes: Mapped[str] = mapped_column(Text, default='')
    position: Mapped[int] = mapped_column(Integer, default=0)


class ResearchImageSummary(Base):
    __tablename__ = 'research_image_summaries'
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), primary_key=True)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchImageVisualReport(Base):
    __tablename__ = 'research_image_visual_reports'
    run_id: Mapped[int] = mapped_column(ForeignKey('research_runs.id'), primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_hash: Mapped[str] = mapped_column(String, nullable=False)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitoredPost(Base):
    __tablename__ = 'monitored_posts'
    __table_args__ = (UniqueConstraint('account','external_id',name='uq_monitored_post'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal: Mapped[str] = mapped_column(String, default='NONE')
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    feed_signal: Mapped[str] = mapped_column(String, default='NONE')
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    translation_attempts: Mapped[int] = mapped_column(Integer, default=0)


class TiboMonitorState(Base):
    __tablename__ = 'tibo_monitor_state'
    id: Mapped[str] = mapped_column(String, primary_key=True, default='thsottiaux')
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list)


class PostNotification(Base):
    __tablename__ = 'post_notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('monitored_posts.id'), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
