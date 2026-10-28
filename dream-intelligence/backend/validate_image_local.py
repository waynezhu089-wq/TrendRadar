"""Explicit small real image search/model acceptance in a separate SQLite database.

Does not download image files, create user plans, or run business jobs.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.database import DATA_DIR, Base
from app.db.models import Analysis, Item, NotificationDelivery, ResearchImage, ResearchPlan, ResearchRun
from app.research.images import run_image_plan, saved_candidates
from app.research.plan_assistant import propose_plan
from app.schemas.plan_assistant import PlanAssistantInput


if __name__=='__main__':
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    output={'kind':'isolated acceptance sample','downloads_attempted':0}
    proposal=propose_plan(PlanAssistantInput(messages=[{'role':'user','content':
        '请建立图片参考素材方案：为奇幻短片的场景设计寻找雾中森林参考图，优先横图，保留作者和许可信息。先使用已经接入的图片来源。'}]))
    if not proposal.plan or proposal.plan.collection_type!='images':
        output['status']='PLAN_NOT_READY'
    else:
        path=DATA_DIR/f'image-validation-{stamp}.db'
        engine=create_engine(f'sqlite:///{path.as_posix()}');Base.metadata.create_all(engine)
        sessions=sessionmaker(bind=engine)
        with sessions() as db,db.begin():
            plan=ResearchPlan(**proposal.plan.model_dump());db.add(plan);db.flush();ident=plan.id
        rid=run_image_plan(ident,sessions=sessions)
        from app.api.v1.research import run_output
        with sessions() as db:
            run=db.get(ResearchRun,rid);data=run_output(db,run)
            output|={'db_path':str(path),'plan':proposal.plan.model_dump(),'status':run.status,
                'received':run.received,'recommended':run.matched,'inserted':run.inserted,
                'errors':run.errors,'image_summary':data.image_summary.model_dump() if data.image_summary else None,
                'samples':[image.model_dump() for image in data.images[:3]],
                'counts':{model.__tablename__:db.scalar(select(func.count()).select_from(model))
                          for model in [ResearchImage,Item,Analysis,NotificationDelivery]}}
        engine.dispose()
    (DATA_DIR/f'image-validation-{stamp}.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True,indent=2))
