"""One bounded real check; isolated SQLite, never business scheduler/notifications."""
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.database import DATA_DIR, Base
from app.db.models import Analysis, Item, ResearchPlan, ResearchRun, Source
from app.research.collection import run_research_plan
from app.research.douban import DoubanBrowserCollector


class CapturedCollector:
    def __init__(self):
        self.cache = {}
        self.received = 0
        self.errors = []

    def collect(self, site, topics):
        if site not in self.cache:
            collector = DoubanBrowserCollector()
            self.cache[site] = (collector.collect(site, topics), collector.errors)
        pages, self.errors = self.cache[site]
        self.received = len(pages)
        return pages


class SavedSummary:
    """Replay the verified result only to check duplicate persistence offline."""
    def __init__(self, summary):
        self.summary = summary

    def analyze(self, _):
        return json.dumps(self.summary, ensure_ascii=False)


if __name__ == '__main__':
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    path = DATA_DIR / f'douban-validation-{stamp}.db'
    engine = create_engine(f'sqlite:///{path.as_posix()}')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db, db.begin():
        plan = ResearchPlan(name='豆瓣书影链路验证（隔离）', topics=['肖申克的救赎', '三体'],
            websites=['https://movie.douban.com/subject/1292052/', 'https://book.douban.com/subject/2567698/'],
            purpose='比较图书与电影评论的观点与分歧，为书影音视频选题提炼可核对的切入点')
        db.add(plan); db.flush(); ident = plan.id
    collector = CapturedCollector()
    first = run_research_plan(ident, sessions=sessions, douban_collector=collector)
    with sessions() as db:
        run = db.get(ResearchRun, first)
        result = {'db_path':str(path),'real_run':{'status':run.status,'received':run.received,
            'inserted':run.inserted,'errors':run.errors},'summary_overview':(run.summary or {}).get('overview')}
        summary = run.summary
    if summary:
        second = run_research_plan(ident, sessions=sessions, douban_collector=collector,
                                  client=SavedSummary(summary))
        with sessions() as db:
            run = db.get(ResearchRun, second)
            result['cached_replay'] = {'status':run.status,'inserted':run.inserted,
                'note':'Replay of same captured evidence and saved analysis; no additional website/model calls'}
    with sessions() as db:
        result['counts'] = {model.__tablename__:db.scalar(select(func.count()).select_from(model))
                           for model in [Source,Item,Analysis]}
        result['samples'] = [{'title':item.title,'url':item.url,'content_length':len(item.content),
            'published_at':item.published_at.isoformat() if item.published_at else None}
            for item in db.scalars(select(Item).order_by(Item.id)).all()]
    output = DATA_DIR / f'douban-validation-{stamp}.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))
    engine.dispose()
