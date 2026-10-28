import contextlib
import io
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commands import run_scheduler
from app.db.database import Base
from app.db.models import (MarketAnnouncement, MarketAnnouncementDocument,
                           MarketAnnouncementRead, MarketWatchlist)
from app.market.announcement_collection import collect_announcements_once
from app.market.announcement_documents import read_pending_announcements
from app.market.announcement_reader import Extraction
from app.market.announcements import Announcement, UnsupportedMarketError


class AnnouncementSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as session:
            session.add_all((
                MarketWatchlist(symbol="600000", market="SH", name="unsupported"),
                MarketWatchlist(symbol="000001", market="SZ", name="source fails"),
                MarketWatchlist(symbol="002782", market="SZ", name="works"),
                MarketWatchlist(symbol="002783", market="SZ", name="disabled", enabled=False),
            ))
            session.commit()

    def tearDown(self):
        self.engine.dispose()

    def test_job_dedup_bounded_reads_retry_isolation_and_unread_boundary(self):
        class FakeProvider:
            def fetch_recent(self, symbol, market, limit=10):
                self_last_limit.append(limit)
                if market != "SZ":
                    raise UnsupportedMarketError("not supported")
                if symbol == "000001":
                    raise RuntimeError("secret-never-log")
                return [Announcement(
                    external_id=str(number), title=f"Document {number}",
                    url=f"https://disc.static.szse.cn/{number}.PDF",
                    published_at=datetime(2026, 9, number), source="SZSE",
                    raw_json={"annId": number}) for number in range(1, 6)][:limit]

        self_last_limit = []
        calls = []

        def reader(url):
            number = int(url.rsplit("/", 1)[-1].split(".")[0])
            calls.append(number)
            if number == 4 and calls.count(4) == 1:
                raise RuntimeError("temporary PDF failure")
            if number == 3:
                return Extraction("SKIPPED_COMPLEX", None, 0, "NO_TEXT_LAYER")
            return Extraction("READABLE", f"Document {number} body", 15, None)

        def collect():
            return collect_announcements_once(FakeProvider(), self.factory)

        def read(symbol, market, limit=3):
            return read_pending_announcements(symbol, market, limit, self.factory, reader)

        output = io.StringIO()
        with (patch.object(run_scheduler, "collect_announcements_once", side_effect=collect),
              patch.object(run_scheduler, "read_pending_announcements", side_effect=read),
              patch("app.intelligence.analyzer.Analyzer") as analyzer,
              contextlib.redirect_stdout(output)):
            first = run_scheduler.run_market_announcements_job()
            second = run_scheduler.run_market_announcements_job()
            other = run_scheduler.run_job("NewsNow", lambda: {
                "received": 0, "inserted": 0, "skipped": 0, "failed": 0})

        self.assertEqual(self_last_limit, [10] * 6)
        self.assertEqual((first["watchlist_count"], first["ann_received"],
                          first["ann_inserted"], first["ann_failed"]), (3, 5, 5, 2))
        self.assertEqual((first["docs_selected"], first["docs_readable"],
                          first["docs_skipped_complex"], first["docs_failed"]), (3, 1, 1, 1))
        self.assertEqual([row["status"] for row in first["documents"]],
                         ["READABLE", "FAILED", "SKIPPED_COMPLEX"])
        self.assertEqual([row["result"] for row in first["stocks"]],
                         ["UNSUPPORTED", "FAILED", "OK"])
        self.assertEqual((second["ann_inserted"], second["ann_skipped"],
                          second["docs_selected"], second["docs_failed"]), (0, 5, 3, 0))
        self.assertEqual(calls, [5, 4, 3, 4, 2, 1])
        self.assertEqual((first["status"], second["status"], other["status"]),
                         ("WARNING", "WARNING", "OK"))
        analyzer.assert_not_called()
        self.assertNotIn("secret-never-log", output.getvalue())
        self.assertNotIn("body", output.getvalue())
        for row in (first, second):
            self.assertTrue(row["started_at"] and row["finished_at"])
            self.assertEqual(row["job"], "market_announcements")
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncement)), 5)
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncementDocument)), 5)
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncementRead)), 0)

    def test_once_announcements_only_invokes_new_job(self):
        with (patch.object(run_scheduler, "run_market_announcements_job",
                           return_value={"status": "WARNING"}) as announcements,
              patch.object(run_scheduler, "run_market_job") as market,
              patch.object(run_scheduler, "run_analysis_job") as analysis,
              patch.object(run_scheduler, "run_once") as collectors,
              patch.object(run_scheduler, "initialize_database")):
            self.assertEqual(run_scheduler.main(["--once-announcements"]), 0)
        announcements.assert_called_once_with()
        market.assert_not_called()
        analysis.assert_not_called()
        collectors.assert_not_called()


if __name__ == "__main__":
    unittest.main()
