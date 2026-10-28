"""Manually import a MediaCrawler Bilibili JSONL file into one research plan."""

import argparse
from pathlib import Path

from app.db.database import SessionLocal
from app.db.models import ResearchRun
from app.research.mediacrawler import import_bilibili_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id", type=int, required=True)
    parser.add_argument("--input", type=Path, required=True,
                        help="MediaCrawler Bilibili search_contents JSONL file")
    args = parser.parse_args()
    run_id = import_bilibili_jsonl(args.plan_id, args.input)
    with SessionLocal() as session:
        run = session.get(ResearchRun, run_id)
        print(f"run={run.id} status={run.status} received={run.received} "
              f"matched={run.matched} inserted={run.inserted} "
              f"errors={len(run.errors)}")


if __name__ == "__main__":
    main()
