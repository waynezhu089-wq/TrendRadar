"""Explicit one-shot collection of official SZSE announcement metadata."""

import argparse
import json
from dataclasses import asdict

from app.db.database import initialize_database
from app.market.announcement_collection import collect_announcements_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect recent official SZSE announcements")
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    initialize_database()
    rows = collect_announcements_once()
    for row in rows:
        print(json.dumps(asdict(row), ensure_ascii=False))
    print(json.dumps({
        "received": sum(row.received for row in rows),
        "inserted": sum(row.inserted for row in rows),
        "skipped": sum(row.skipped for row in rows),
        "failed": sum(row.failed for row in rows),
    }, ensure_ascii=False))
    return 1 if any(row.failed for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
