from datetime import datetime, timedelta, timezone
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db, DATA_DIR
from app.db.models import ResearchPlan, ResearchVideo, ResearchRunVideo, ResearchRun, VideoSchedule, VideoFavorite
from app.connectors.youtube import api_key, YouTubeError
from app.research.videos import INTERVALS, list_videos, utc

router=APIRouter()


def video_plan(db,ident):
    plan=db.get(ResearchPlan,ident)
    if not plan or not plan.enabled or plan.collection_type!='videos':
        raise HTTPException(404,'Video plan not found')
    return plan


def configured():
    try:
        api_key();return True
    except YouTubeError:
        return False


@router.get('/research-plans/{plan_id}/videos')
def saved_videos(plan_id:int,favorites:bool=False,db:Session=Depends(get_db)):
    video_plan(db,plan_id)
    return list_videos(db,plan_id,favorites)


class ScheduleInput(BaseModel):
    enabled:bool=Field(strict=True)
    interval_minutes:int=Field(strict=True)


def runtime_status():
    try:
        state=json.loads((DATA_DIR/'youtube-scheduler-runtime.json').read_text())
        elapsed=datetime.now(timezone.utc)-datetime.fromisoformat(state['updated_at'])
        return timedelta(0)<=elapsed<timedelta(seconds=90),bool(state['configured'])
    except (OSError,ValueError,TypeError,KeyError):
        return False,False


@router.get('/research-plans/{plan_id}/video-schedule')
def schedule_status(plan_id:int,db:Session=Depends(get_db)):
    video_plan(db,plan_id);row=db.get(VideoSchedule,plan_id)
    connected,scheduler_configured=runtime_status()
    return {'enabled':bool(row and row.enabled),'interval_minutes':row.interval_minutes if row else 1440,
        'interval_options':list(INTERVALS),'configured':configured(),'scheduler_connected':connected,
        'scheduler_configured':scheduler_configured,'next_run_at':utc(row.next_run_at) if row else None}


@router.post('/research-plans/{plan_id}/video-schedule')
def save_schedule(plan_id:int,body:ScheduleInput,db:Session=Depends(get_db)):
    video_plan(db,plan_id)
    if body.interval_minutes not in INTERVALS:
        raise HTTPException(422,'Unsupported interval')
    if body.enabled and not configured():
        raise HTTPException(409,'YOUTUBE_NOT_CONFIGURED')
    row=db.get(VideoSchedule,plan_id)
    if row is None:
        row=VideoSchedule(plan_id=plan_id);db.add(row)
    changed=row.enabled!=body.enabled or row.interval_minutes!=body.interval_minutes
    row.enabled=body.enabled;row.interval_minutes=body.interval_minutes
    if changed:
        row.next_run_at=datetime.now(timezone.utc)+timedelta(minutes=body.interval_minutes) if body.enabled else None
    db.commit()
    return schedule_status(plan_id,db)


@router.post('/research-plans/{plan_id}/videos/{video_id}/favorite')
def favorite_video(plan_id:int,video_id:int,db:Session=Depends(get_db)):
    video_plan(db,plan_id)
    if not db.scalar(select(ResearchRunVideo.id).join(ResearchRun).where(
            ResearchRun.plan_id==plan_id,ResearchRunVideo.video_id==video_id)):
        raise HTTPException(404,'Video not in this plan')
    existing=db.scalar(select(VideoFavorite).where(VideoFavorite.plan_id==plan_id,VideoFavorite.video_id==video_id))
    if existing is None:
        db.add(VideoFavorite(plan_id=plan_id,video_id=video_id));db.commit()
    return {'favorite':True}


@router.delete('/research-plans/{plan_id}/videos/{video_id}/favorite')
def unfavorite_video(plan_id:int,video_id:int,db:Session=Depends(get_db)):
    video_plan(db,plan_id)
    row=db.scalar(select(VideoFavorite).where(VideoFavorite.plan_id==plan_id,VideoFavorite.video_id==video_id))
    if row:
        db.delete(row);db.commit()
    return {'favorite':False}
