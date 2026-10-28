import os
from contextlib import closing
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.environ.get("DSIH_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'dsih.db').as_posix()}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session

def initialize_database(target_engine=engine):
    """Create tables and apply the small, idempotent legacy column migrations."""
    from .models import Item, Source
    from sqlalchemy import MetaData
    from sqlalchemy.schema import CreateTable
    import sqlite3
    from datetime import datetime, timezone

    Base.metadata.create_all(target_engine)
    connection = target_engine.raw_connection()
    try:
        columns = connection.execute('PRAGMA table_info(items)').fetchall()
        legacy_metadata = any(c[1] in ('author', 'published_at') and c[3] for c in columns)
        needs_raw_json = not any(c[1] == 'raw_json' for c in columns)
        plan_columns = connection.execute('PRAGMA table_info(research_plans)').fetchall()
        needs_collection_type = not any(c[1] == 'collection_type' for c in plan_columns)
        if not legacy_metadata and not needs_raw_json and not needs_collection_type:
            return
        # Backup before changing the table; preserve existing IDs and analyses.
        path = target_engine.url.database
        if path and path != ':memory:':
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            with closing(sqlite3.connect(f'{path}.pre-dsih-007-{stamp}.bak')) as backup:
                connection.driver_connection.backup(backup)
        if legacy_metadata:
            connection.execute('PRAGMA foreign_keys=OFF')
            connection.execute('BEGIN IMMEDIATE')
            metadata = MetaData()
            Source.__table__.to_metadata(metadata)
            table = Item.__table__.to_metadata(metadata, name='items_dsih003')
            connection.execute(str(CreateTable(table).compile(dialect=target_engine.dialect)))
            names = ', '.join('"' + c[1] + '"' for c in columns)
            connection.execute(f'INSERT INTO items_dsih003 ({names}) SELECT {names} FROM items')
            connection.execute('DROP TABLE items')
            connection.execute('ALTER TABLE items_dsih003 RENAME TO items')
        elif needs_raw_json:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('ALTER TABLE items ADD COLUMN raw_json JSON')
        if needs_collection_type:
            if not legacy_metadata and not needs_raw_json:
                connection.execute('BEGIN IMMEDIATE')
            connection.execute("ALTER TABLE research_plans ADD COLUMN collection_type VARCHAR NOT NULL DEFAULT 'research'")
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key check failed during metadata migration')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.close()
