"""Existing resident Scheduler polls due video plans; no independent background service."""
from datetime import datetime, timezone
from sqlalchemy import select

from app.db.database import DATA_DIR, SessionLocal
from app.db.models import ResearchPlan, VideoSchedule
from app.connectors.youtube import api_key, YouTubeError
from app.monitors.tibo_settings import atomic_json
from .videos import run_video_plan


def write_video_heartbeat(now=None):
    ready=True
    try:
        api_key()
    except YouTubeError:
        ready=False
    atomic_json(DATA_DIR/'youtube-scheduler-runtime.json',{
        'updated_at':(now or datetime.now(timezone.utc)).isoformat(),'configured':ready})


def run_due_video_plans(sessions=SessionLocal,runner=run_video_plan,now=None):
    instant=now or datetime.now(timezone.utc)
    try:
        api_key()
    except YouTubeError:
        return {'status':'NOT_CONFIGURED','runs':[]}
    with sessions() as db:
        ids=list(db.scalars(select(VideoSchedule.plan_id).join(ResearchPlan).where(
            ResearchPlan.enabled.is_(True),ResearchPlan.collection_type=='videos',VideoSchedule.enabled.is_(True),
            VideoSchedule.next_run_at<=instant,
            VideoSchedule.lease_until.is_(None)|(VideoSchedule.lease_until<=instant)
        ).order_by(VideoSchedule.next_run_at).limit(3)))
    results=[]
    for ident in ids:
        try:
            results.append({'plan_id':ident,'run_id':runner(ident,sessions=sessions,now=instant,scheduled=True)})
        except Exception:
            # Never log provider exceptions or payloads, and keep other plans eligible.
            results.append({'plan_id':ident,'status':'FAILED_OR_BUSY'})
    return {'status':'OK','runs':results}
