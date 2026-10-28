import json
from dataclasses import asdict
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from app.connectors.github import GitHubConnector, REPOSITORIES
from app.db.database import SessionLocal, initialize_database
from app.db.models import Source, Item

def save_collection(results, session_factory=SessionLocal):
    report = {"sources": [], "received": 0, "inserted": 0, "skipped": 0, "failed": 0}
    for result in results:
        row = {"source": result.source, "received": result.received, "inserted": 0, "skipped": 0,
               "status": "FAILED" if result.error else "OK", "error": result.error}
        if not result.error:
            try:
                with session_factory() as session, session.begin():
                    name, url = REPOSITORIES[result.source], "https://github.com/" + result.source
                    source = session.scalar(select(Source).where(Source.type == "github", Source.url == url))
                    if source is None:
                        source = Source(name=name, type="github", url=url, category="GITHUB", enabled=True)
                        session.add(source)
                        session.flush()
                    for item in result.items:
                        values = asdict(item)
                        values.pop("source")
                        statement = insert(Item).values(source_id=source.id, **values).on_conflict_do_nothing(index_elements=["external_id"])
                        inserted = session.execute(statement).rowcount
                        row["inserted"] += inserted
                        row["skipped"] += 1 - inserted
            except Exception as error:
                row.update(status="FAILED", error="Database write failed", inserted=0, skipped=0)
        report["sources"].append(row)
        report["received"] += row["received"]
        report["inserted"] += row["inserted"]
        report["skipped"] += row["skipped"]
        report["failed"] += row["status"] == "FAILED"
    return report

def main():
    initialize_database()
    connector = GitHubConnector()
    report = save_collection(connector.collect())
    report["auth_mode"] = connector.auth_mode
    print("GitHub collection")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["failed"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
