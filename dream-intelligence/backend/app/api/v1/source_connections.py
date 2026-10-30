from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import SourceConnection
from app.schemas.source_connections import SourceDefinition, SourceConnectionOutput
from app.research.source_connections import (GITHUB_TEMPLATE, RSS_TEMPLATE, JSON_TEMPLATE,
                                             connection_output, configured_catalog)

router = APIRouter(prefix='/source-connections')


@router.get('/templates')
def templates():
    return [dict(id=key, definition=value.model_dump()) for key,value in
            [('github',GITHUB_TEMPLATE),('rss',RSS_TEMPLATE),('json_api',JSON_TEMPLATE)]]


@router.get('/catalog')
def catalog(db: Session = Depends(get_db)):
    return configured_catalog(db)


@router.get('', response_model=list[SourceConnectionOutput])
def connections(db: Session = Depends(get_db)):
    return [connection_output(row) for row in db.scalars(select(SourceConnection).order_by(SourceConnection.id))]


def save_definition(db, definition, ident=None):
    from .research import manual_run_lock
    if not manual_run_lock.acquire(blocking=False):
        raise HTTPException(409, 'SOURCE_CONFIG_BUSY')
    try:
        row = db.get(SourceConnection, ident) if ident else SourceConnection()
        if row is None:
            raise HTTPException(404, 'SOURCE_NOT_FOUND')
        row.definition = definition.model_dump()
        db.add(row); db.commit(); db.refresh(row)
        return connection_output(row)
    finally:
        manual_run_lock.release()


@router.post('', response_model=SourceConnectionOutput, status_code=201)
def create(definition: SourceDefinition, db: Session = Depends(get_db)):
    return save_definition(db, definition)


@router.post('/{connection_id}', response_model=SourceConnectionOutput)
def update(connection_id: int, definition: SourceDefinition, db: Session = Depends(get_db)):
    return save_definition(db, definition, connection_id)
