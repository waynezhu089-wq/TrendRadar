"""Explicit, bounded plain-text reading of the latest official SZSE PDFs."""

import argparse
import json
from dataclasses import asdict

from app.db.database import initialize_database
from app.market.announcement_documents import read_latest_announcements


def main() -> int:
    parser = argparse.ArgumentParser(description="Read up to three latest official SZSE PDFs")
    parser.add_argument("--latest", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.latest <= 3:
        parser.error("--latest must be between 1 and 3")
    initialize_database()
    results = read_latest_announcements(args.latest)
    for result in results:
        print(json.dumps(asdict(result), ensure_ascii=False))
    return 1 if any(row.status == "FAILED" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
