from datetime import datetime, timedelta, timezone, date
from sqlalchemy import select

from app.connectors.commissions import CommissionConnector, SOURCES, SOURCE_COVERAGE
from app.db.models import CommissionLead, CommissionCollection


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def lead_output(row, today=None, now=None):
    now = now or datetime.now(timezone.utc)
    today = today or (now+timedelta(hours=8)).date()
    payload = dict(row.payload)
    deadline = payload.get('deadline')
    expired = bool(deadline and date.fromisoformat(deadline) < today)
    if payload.get('deadline_at'):
        expired = datetime.fromisoformat(payload['deadline_at']) <= now
    status = 'EXPIRED' if expired else payload.get('source_status', 'UNKNOWN')
    return dict(payload, id=row.id, status=status, captured_at=utc(row.captured_at),
        checked_at=utc(row.checked_at))


def list_leads(db):
    rows = db.scalars(select(CommissionLead).order_by(CommissionLead.checked_at.desc()).limit(500)).all()
    results = [lead_output(row) for row in rows]
    results.sort(key=lambda row: (row.get('published_on') or '', row['id']), reverse=True)
    latest = db.scalar(select(CommissionCollection).order_by(CommissionCollection.id.desc()).limit(1))
    return {'leads': results, 'latest': None if not latest else dict(id=latest.id,
        started_at=utc(latest.started_at), finished_at=utc(latest.finished_at) if latest.finished_at else None,
        **latest.report), 'sources': [{'id': key, 'name': value[0], 'url': value[1],
            'coverage': SOURCE_COVERAGE[key]} for key,value in SOURCES.items()]}


def collect_leads(db, connector=None):
    connector = connector or CommissionConnector()
    run = CommissionCollection(report={'status': 'RUNNING'})
    db.add(run); db.commit(); db.refresh(run)
    reports = []
    inserted = updated = 0
    for source in SOURCES:
        try:
            rows, report = connector.collect_source(source)
            now = datetime.now(timezone.utc)
            new = changed = 0
            for payload in rows:
                row = db.scalar(select(CommissionLead).where(CommissionLead.url == payload['url']))
                if row is None:
                    db.add(CommissionLead(url=payload['url'], payload=payload, checked_at=now))
                    new += 1
                else:
                    row.payload = payload
                    row.checked_at = now
                    changed += 1
            db.commit()
            inserted += new; updated += changed
            reports.append(report)
        except Exception:
            db.rollback()
            reports.append({'source': source, 'name': SOURCES[source][0], 'url': SOURCES[source][1],
                'status': 'FAILED', 'checked': 0, 'accepted': 0, 'errors': ['SOURCE_UNAVAILABLE'],
                'coverage': SOURCE_COVERAGE[source]})
    run = db.get(CommissionCollection, run.id)
    successful = sum(report['status'] != 'FAILED' for report in reports)
    run.finished_at = datetime.now(timezone.utc)
    run.report = {'status': 'FAILED' if not successful else 'COMPLETED' if all(r['status']=='OK' for r in reports) else 'PARTIAL',
        'sources': reports, 'inserted': inserted, 'updated': updated,
        'received': sum(report['accepted'] for report in reports)}
    db.commit()
    return list_leads(db)
