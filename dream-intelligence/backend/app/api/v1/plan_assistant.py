from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ResearchPlan, ResearchPlanSource
from app.research.source_connections import configured_catalog, validate_bindings
from app.llm.openai_compatible import ConfigurationError
from app.research.plan_assistant import propose_plan
from app.schemas.plan_assistant import (PlanAssistantInput, PlanAssistantOutput,
                                       ConfirmPlanInput, ConfirmPlanOutput)

router = APIRouter(prefix='/research-plan-assistant')
planning_lock = Lock()
creation_lock = Lock()


@router.post('/draft', response_model=PlanAssistantOutput)
def draft_plan(payload: PlanAssistantInput, db: Session = Depends(get_db)):
    if not planning_lock.acquire(blocking=False):
        raise HTTPException(409, 'Plan assistant is already thinking')
    try:
        return propose_plan(payload, source_catalog=configured_catalog(db))
    except ConfigurationError:
        raise HTTPException(503, 'Plan assistant model is not configured') from None
    except Exception:
        raise HTTPException(502, 'Plan assistant unavailable; no plan was created') from None
    finally:
        planning_lock.release()


@router.post('/create', response_model=ConfirmPlanOutput)
def confirm_plan(payload: ConfirmPlanInput, db: Session = Depends(get_db)):
    # Explicit confirmation only. No crawler, model or scheduler is called here.
    values = payload.plan.model_dump()
    try:validate_bindings(db,payload.plan.source_bindings)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    bindings = values.pop('source_bindings',[])
    with creation_lock:
        existing = db.scalars(select(ResearchPlan).where(ResearchPlan.enabled.is_(True),
            ResearchPlan.name==values['name'], ResearchPlan.purpose==values['purpose'])).all()
        for plan in existing:
            if (plan.topics == values['topics'] and plan.websites == values['websites']
                    and plan.collection_type == values['collection_type']
                    and [dict(connection_id=row.connection_id,query=row.query,sort=row.sort,limit=row.limit)
                         for row in plan.source_bindings] == bindings):
                return ConfirmPlanOutput(plan=plan, created=False)
        plan = ResearchPlan(**values,source_bindings=[ResearchPlanSource(**value) for value in bindings])
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return ConfirmPlanOutput(plan=plan, created=True)
