"""Explicit one-shot A-share snapshot collection."""

import argparse
import json
from dataclasses import asdict

from app.db.database import initialize_database
from app.market.collection import collect_backfill, collect_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect A-share daily snapshots")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="latest available trading day only")
    mode.add_argument("--backfill", type=int, metavar="DAYS", help="up to 30 recent trading days")
    args = parser.parse_args()
    if args.backfill is not None and not 1 <= args.backfill <= 30:
        parser.error("--backfill must be between 1 and 30")
    initialize_database()
    results = collect_once() if args.once else collect_backfill(args.backfill)
    for result in results:
        print(json.dumps(asdict(result), ensure_ascii=False))
    print(json.dumps({"inserted": sum(row.inserted for row in results),
                      "skipped": sum(row.skipped for row in results),
                      "failed": sum(row.failed for row in results)}, ensure_ascii=False))
    return 1 if any(row.failed for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
