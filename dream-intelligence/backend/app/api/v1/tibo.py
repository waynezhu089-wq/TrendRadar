"""Subscription feed and non-secret preferences; saving never runs collection."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictInt, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import MonitoredPost, PostNotification, TiboMonitorState
from app.monitors.tibo import LABELS,load_tibo_config
from app.monitors.tibo_sources import ACCOUNT,aware
from app.monitors.tibo_settings import POLL_MINUTES, INTERVAL_OPTIONS, save_poll_minutes, settings_status

router=APIRouter(prefix='/tibo-monitor')


@router.get('')
def monitor_status(db:Session=Depends(get_db)):
    config=load_tibo_config();state=db.get(TiboMonitorState,ACCOUNT)
    rows=db.scalars(select(MonitoredPost).where(MonitoredPost.account==ACCOUNT).order_by(
        func.coalesce(MonitoredPost.published_at,MonitoredPost.reported_at).desc(),MonitoredPost.id.desc()).limit(20)).all()
    return {'account':ACCOUNT,'enabled':bool(config),'browser_enabled':bool(config and config.browser_enabled),
        'poll_minutes':config.poll_minutes if config else POLL_MINUTES,'last_polled_at':aware(state.last_polled_at) if state else None,
        'last_success_at':aware(state.last_success_at) if state else None,
        'errors':state.errors if state else [],'posts':[{
            'id':post.id,'url':post.url,'title_zh':post.title_zh,'translation_zh':post.translation_zh,
            'original_text':post.original_text,'reason_zh':post.reason_zh,'signal':post.signal,
            'signal_label':LABELS.get(post.signal,'待中文整理'),'source_kind':post.source_kind,
            'source_url':post.source_url,'published_at':aware(post.published_at),'reported_at':aware(post.reported_at),
            'captured_at':aware(post.captured_at),'delivery_statuses':list(db.scalars(
                select(PostNotification.status).where(PostNotification.post_id==post.id)))} for post in rows]}


class SubscriptionSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    poll_minutes: StrictInt

    @field_validator('poll_minutes')
    @classmethod
    def supported_interval(cls, value):
        if value not in INTERVAL_OPTIONS:
            raise ValueError('Unsupported interval')
        return value


@router.get('/settings')
def get_settings():
    return settings_status()


@router.post('/settings')
def update_settings(body: SubscriptionSettings):
    try:
        save_poll_minutes(body.poll_minutes)
    except (OSError, ValueError, TypeError):
        raise HTTPException(409, 'Subscription settings unavailable') from None
    return settings_status()


@router.post('/login')
def login():
    try:
        from app.commands.x_login import open_login
        open_login()
        return {'status':'OPENED'}
    except Exception:raise HTTPException(409,'Dedicated Chrome unavailable') from None
