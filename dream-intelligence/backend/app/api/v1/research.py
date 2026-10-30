from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import get_db
from app.db.models import (Item, ResearchPlan, ResearchRun, ResearchRunItem, Source,
                           ResearchImage, ResearchImageSummary, ResearchPlanSource, ResearchSourceReport)
from app.research.source_connections import validate_bindings, snapshots_from_reports
from app.schemas.source_connections import SourceBindingsInput
from app.research.collection import run_research_plan, reanalyze_research_run
from datetime import datetime, timezone
from threading import Lock
from app.schemas.research import (ResearchItemOutput, ResearchPlanInput,
                                  ResearchPlanOutput, ResearchRunOutput, ImageSourcesInput)
from app.schemas.image_vision import VisualReportOutput
from app.llm.openai_compatible import ConfigurationError

router = APIRouter()
manual_run_lock = Lock()
image_download_lock = Lock()


@router.get('/image-vision/status')
def image_vision_status():
    from app.llm.vision import vision_status
    return vision_status()


@router.post('/research-plans/{plan_id}/runs/{run_id}/vision', response_model=VisualReportOutput)
def analyze_visual_references(plan_id: int, run_id: int, db: Session = Depends(get_db)):
    from app.research.image_vision import analyze_run_images, VisionError
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, 'VISION_RUN_BUSY')
    try:
        return analyze_run_images(plan_id,run_id,sessions=sessionmaker(bind=db.get_bind()))
    except ConfigurationError:
        raise HTTPException(409, 'VISION_NOT_CONFIGURED') from None
    except VisionError as error:
        status=409 if error.code in ('VISION_RUN_BUSY','VISION_INPUT_CHANGED') else 422 if error.code in (
            'VISION_RUN_NOT_FOUND','VISION_NO_IMAGES') else 502
        raise HTTPException(status,error.code) from None
    except Exception:
        raise HTTPException(502,'VISION_FAILED') from None
    finally:
        manual_run_lock.release()


@router.post('/research-sources/douban/login')
def login_douban():
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, 'Research is running; close it before login')
    try:
        from app.commands.douban_login import open_login
        open_login()
        return {'status': 'OPENED'}
    except Exception:
        raise HTTPException(409, 'Close the dedicated window or check Chrome installation') from None
    finally:
        manual_run_lock.release()


@router.get("/research-plans", response_model=list[ResearchPlanOutput])
def list_research_plans(db: Session = Depends(get_db)):
    return db.scalars(select(ResearchPlan).where(ResearchPlan.enabled.is_(True))
                      .order_by(ResearchPlan.id.desc())).all()


@router.post("/research-plans", response_model=ResearchPlanOutput, status_code=201)
def create_research_plan(payload: ResearchPlanInput, db: Session = Depends(get_db)):
    try:validate_bindings(db,payload.source_bindings)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    values = payload.model_dump()
    bindings = values.pop('source_bindings',[])
    plan = ResearchPlan(**values,source_bindings=[ResearchPlanSource(**value) for value in bindings])
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/research-plans/{plan_id}", status_code=204)
def remove_research_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(ResearchPlan, plan_id)
    if plan is None or not plan.enabled:
        raise HTTPException(404, "Research plan not found")
    plan.enabled = False  # Keep prior run provenance.
    db.commit()
    return Response(status_code=204)


@router.post('/research-plans/{plan_id}/source-bindings', response_model=ResearchPlanOutput)
def update_source_bindings(plan_id: int, body: SourceBindingsInput, db: Session = Depends(get_db)):
    if not manual_run_lock.acquire(blocking=False):raise HTTPException(409,'SOURCE_CONFIG_BUSY')
    try:
        plan=db.get(ResearchPlan,plan_id)
        if not plan or not plan.enabled or plan.collection_type!='research':raise HTTPException(404,'Research plan not found')
        try:
            ResearchPlanInput(name=plan.name,topics=plan.topics,websites=plan.websites,purpose=plan.purpose,source_bindings=body.bindings)
            validate_bindings(db,body.bindings)
        except ValueError:raise HTTPException(422,'SOURCE_BINDINGS_INVALID') from None
        existing={row.connection_id:row for row in plan.source_bindings}
        updated=[]
        for binding in body.bindings:
            row=existing.get(binding.connection_id) or ResearchPlanSource(connection_id=binding.connection_id)
            row.query,row.sort,row.limit=binding.query,binding.sort,binding.limit
            updated.append(row)
        plan.source_bindings=updated
        db.commit();db.refresh(plan)
        return plan
    finally:manual_run_lock.release()


@router.post('/research-plans/{plan_id}/image-sources', response_model=ResearchPlanOutput)
def update_image_sources(plan_id: int, body: ImageSourcesInput, db: Session = Depends(get_db)):
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, 'Research is running')
    try:
        plan=db.get(ResearchPlan,plan_id)
        if not plan or not plan.enabled or plan.collection_type!='images':
            raise HTTPException(404, 'Image plan not found')
        if db.scalar(select(ResearchRun.id).where(ResearchRun.plan_id==plan_id,ResearchRun.status=='RUNNING')):
            raise HTTPException(409, 'Research is running')
        plan.websites=body.websites
        db.commit();db.refresh(plan)
        return plan
    finally:
        manual_run_lock.release()


def run_output(db: Session, run: ResearchRun) -> ResearchRunOutput:
    from app.db.models import VideoSearchReport
    from app.research.images import saved_candidates
    from app.research.image_vision import visual_output
    from app.schemas.research import ResearchImageOutput, ImageSummaryOutput
    rows = db.execute(select(Item, Source).join(ResearchRunItem,
        ResearchRunItem.item_id == Item.id).join(Source, Source.id == Item.source_id)
        .where(ResearchRunItem.run_id == run.id).order_by(
            Item.published_at.desc().nulls_last(), Item.id.desc())).all()
    image_rows=saved_candidates(db,run.id)
    image_summary=db.get(ResearchImageSummary,run.id)
    video_search=db.get(VideoSearchReport,run.id)
    source_report=db.get(ResearchSourceReport,run.id)
    reports=source_report.reports if source_report else []
    snapshots=snapshots_from_reports(reports)
    return ResearchRunOutput(id=run.id, plan_id=run.plan_id, status=run.status,
        started_at=run.started_at, finished_at=run.finished_at,
        received=run.received, matched=run.matched, inserted=run.inserted,
        errors=run.errors, summary=run.summary,visual_analysis=visual_output(db,run.id),
        video_search=video_search.report if video_search else None, source_reports=reports,
        image_summary=ImageSummaryOutput(overview=image_summary.overview,limitations=image_summary.limitations,
            kind='analysis' if run.status in ('COMPLETED','PARTIAL') else 'search') if image_summary else None,
        images=[ResearchImageOutput(id=image.id,provider=image.provider,title=image.title,source_url=image.source_url,
            image_url=image.image_url,thumbnail_url=image.thumbnail_url,creator=image.creator,
            license=image.license,license_url=image.license_url,attribution=image.attribution,
            width=image.width,height=image.height,favorite=image.favorite,downloaded=bool(image.local_path),
            recommended=link.recommended,reason=link.reason,usage_notes=link.usage_notes) for image,link in image_rows],
        items=[observed_item(item,source,snapshots) for item,source in rows])


def observed_item(item,source,snapshots):
    snapshot=snapshots.get(item.id)
    if snapshot:
        published=datetime.fromisoformat(snapshot['published_at']) if snapshot.get('published_at') else None
        return ResearchItemOutput(id=item.id,title=snapshot['title'],url=snapshot['url'],
                                  source=snapshot['source_name'],published_at=published)
    published=item.published_at.replace(tzinfo=timezone.utc) if item.published_at and item.published_at.tzinfo is None else item.published_at
    return ResearchItemOutput(id=item.id,title=item.title,url=item.url,source=source.name,published_at=published)


@router.get('/research-plans/{plan_id}/favorite-images')
def favorite_images(plan_id: int, db: Session = Depends(get_db)):
    from app.db.models import ResearchRunImage
    from app.schemas.research import ResearchImageOutput
    if db.get(ResearchPlan,plan_id) is None:raise HTTPException(404,'Plan not found')
    # Match each favorite to its latest run for this plan, including older saved runs.
    rows=db.execute(select(ResearchImage,ResearchRunImage).join(ResearchRunImage,
        ResearchRunImage.image_id==ResearchImage.id).join(ResearchRun,
        ResearchRun.id==ResearchRunImage.run_id).where(ResearchRun.plan_id==plan_id,
        ResearchImage.favorite.is_(True)).order_by(ResearchRun.id.desc(),ResearchRunImage.position)).all()
    seen=set();images=[]
    for image,link in rows:
        if image.id in seen:continue
        seen.add(image.id)
        images.append(ResearchImageOutput(id=image.id,provider=image.provider,title=image.title,source_url=image.source_url,
            image_url=image.image_url,thumbnail_url=image.thumbnail_url,creator=image.creator,
            license=image.license,license_url=image.license_url,attribution=image.attribution,
            width=image.width,height=image.height,favorite=True,downloaded=bool(image.local_path),
            recommended=link.recommended,reason=link.reason,usage_notes=link.usage_notes))
        if len(images)>=100:break
    return images


@router.get("/research-plans/{plan_id}/runs", response_model=list[ResearchRunOutput])
def list_research_runs(plan_id: int, db: Session = Depends(get_db)):
    if db.get(ResearchPlan, plan_id) is None:
        raise HTTPException(404, "Research plan not found")
    runs = db.scalars(select(ResearchRun).where(ResearchRun.plan_id == plan_id)
                      .order_by(ResearchRun.id.desc()).limit(10)).all()
    return [run_output(db, run) for run in runs]


@router.post("/research-plans/{plan_id}/run", response_model=ResearchRunOutput)
def run_research(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(ResearchPlan, plan_id)
    if plan is None or not plan.enabled:
        raise HTTPException(404, "Research plan not found")
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, "Another research plan is already running")
    try:
        if plan.collection_type == 'videos':
            from app.research.videos import run_video_plan
            from app.connectors.youtube import YouTubeError
            try:
                run_id=run_video_plan(plan_id,sessions=sessionmaker(bind=db.get_bind()))
            except YouTubeError:
                raise HTTPException(409,'YOUTUBE_NOT_CONFIGURED') from None
        elif plan.collection_type == 'images':
            from app.research.images import run_image_plan
            run_id = run_image_plan(plan_id,sessions=sessionmaker(bind=db.get_bind()))
        else:
            run_id = run_research_plan(plan_id, sessions=sessionmaker(bind=db.get_bind()))
    except RuntimeError:
        raise HTTPException(409, "Research plan is already running") from None
    finally:
        manual_run_lock.release()
    db.expire_all()
    return run_output(db, db.get(ResearchRun, run_id))


@router.post("/research-plans/{plan_id}/runs/{run_id}/analyze", response_model=ResearchRunOutput)
def analyze_saved_research(plan_id: int, run_id: int, db: Session = Depends(get_db)):
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, "Another research request is running")
    try:
        plan=db.get(ResearchPlan,plan_id)
        if plan and plan.collection_type=='videos':
            raise HTTPException(422,'Use a new video collection; saved video metadata remains readable')
        if plan and plan.collection_type=='images':
            from app.research.images import reanalyze_images
            reanalyze_images(plan_id,run_id,sessions=sessionmaker(bind=db.get_bind()))
        else:
            reanalyze_research_run(plan_id, run_id, sessions=sessionmaker(bind=db.get_bind()))
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(422, "No saved evidence for this plan and run") from None
    except RuntimeError:
        raise HTTPException(409, "Research run is still collecting") from None
    except Exception:
        raise HTTPException(502, "Analysis failed; previous result preserved") from None
    finally:
        manual_run_lock.release()
    db.expire_all()
    return run_output(db, db.get(ResearchRun, run_id))


@router.post('/research-images/{image_id}/favorite')
def favorite_image(image_id: int, db: Session = Depends(get_db)):
    image=db.get(ResearchImage,image_id)
    if image is None:raise HTTPException(404,'Image not found')
    image.favorite=True;db.commit()
    return {'favorite':True}


@router.delete('/research-images/{image_id}/favorite')
def unfavorite_image(image_id: int, db: Session = Depends(get_db)):
    image=db.get(ResearchImage,image_id)
    if image is None:raise HTTPException(404,'Image not found')
    image.favorite=False;db.commit()
    return {'favorite':False}


@router.post('/research-images/{image_id}/download')
def prepare_image_download(image_id: int, db: Session = Depends(get_db)):
    image=db.get(ResearchImage,image_id)
    if image is None:raise HTTPException(404,'Image not found')
    if not image_download_lock.acquire(blocking=False):raise HTTPException(409,'Download is busy')
    try:
        from app.research.images import download_image
        path,digest=download_image(image)
        image.local_path=str(path);image.sha256=digest;db.commit()
        return {'downloaded':True}
    except Exception:
        raise HTTPException(502,'Image unavailable, too large or unsupported; check original source') from None
    finally:
        image_download_lock.release()


@router.get('/research-images/{image_id}/file')
def image_file(image_id: int, db: Session = Depends(get_db)):
    from pathlib import Path
    from fastapi.responses import FileResponse
    from app.research.images import ASSET_DIR
    image=db.get(ResearchImage,image_id)
    if image is None or not image.local_path:raise HTTPException(404,'Download first')
    path=Path(image.local_path).resolve()
    if not path.is_relative_to(ASSET_DIR.resolve()) or not path.is_file():
        raise HTTPException(404,'Local image unavailable')
    return FileResponse(path,media_type='application/octet-stream',filename=f'dsih-image-{image_id}{path.suffix}')
