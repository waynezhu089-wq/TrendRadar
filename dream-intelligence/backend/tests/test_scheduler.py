import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commands import run_scheduler
from app.db.database import Base
from app.db.models import MarketSnapshot, MarketWatchlist
from app.intelligence.candidates import ANALYSIS_GATE_TERMS, LOOKBACK_DAYS, MAX_TOTAL, SOURCE_QUOTAS, Selection
from app.market.collection import collect_once
from app.market.provider import DailySnapshot


class SchedulerTests(unittest.TestCase):
    def test_frozen_selector_policy_constants(self):
        self.assertEqual((LOOKBACK_DAYS, MAX_TOTAL), (7, 6))
        self.assertEqual(SOURCE_QUOTAS, {"github": 3, "rss": 3, "newsnow": 2})
        self.assertEqual(ANALYSIS_GATE_TERMS, (
            "AI", "人工智能", "大模型", "LLM", "模型", "视频生成", "图生视频",
            "ComfyUI", "MiniMax", "Seedance", "Agent", "智能体", "MCP",
            "workflow", "工作流", "browser", "浏览器自动化", "自动化", "开源", "GitHub"))

    def test_registers_six_jobs_and_preserves_existing_five_configs(self):
        anchor = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
        with patch.dict(os.environ, {}, clear=True):
            scheduler = run_scheduler.create_scheduler(anchor, run_scheduler.FORMAL_PROFILE)
        jobs = {job.id: job for job in scheduler.get_jobs()}
        self.assertEqual(set(jobs), {"newsnow", "github", "rss", "auto_analysis",
                                     "market", "market_announcements", "youtube_discovery", "youtube_heartbeat"})
        existing = {name: job for name, job in jobs.items()
                    if name not in ("market", "market_announcements", "youtube_discovery", "youtube_heartbeat")}
        self.assertEqual(jobs['youtube_discovery'].trigger.interval,timedelta(minutes=5))
        self.assertEqual(jobs['youtube_discovery'].max_instances,1)
        self.assertEqual({name: int(job.trigger.interval.total_seconds() / 60)
                          for name, job in existing.items()},
                         {"newsnow": 60, "github": 120, "rss": 240, "auto_analysis": 240})
        self.assertEqual(jobs["auto_analysis"].trigger.start_date - jobs["rss"].trigger.start_date,
                         timedelta(minutes=12))
        for job in existing.values():
            self.assertEqual(job.max_instances, 1)
            self.assertTrue(job.coalesce)
            self.assertGreater(job.trigger.get_next_fire_time(None, anchor), anchor)
        market = jobs["market"]
        self.assertEqual({field.name: str(field) for field in market.trigger.fields
                          if field.name in ("day_of_week", "hour", "minute")},
                         {"day_of_week": "mon-fri", "hour": "16", "minute": "10"})
        self.assertEqual(market.trigger.timezone.key, "Asia/Shanghai")
        self.assertEqual((market.max_instances, market.coalesce), (1, True))
        next_fire = market.trigger.get_next_fire_time(None, anchor)
        self.assertEqual(next_fire, datetime(2026, 9, 29, 16, 10, tzinfo=ZoneInfo("Asia/Shanghai")))
        announcements = jobs["market_announcements"]
        self.assertEqual({field.name: str(field) for field in announcements.trigger.fields
                          if field.name in ("day_of_week", "hour", "minute")},
                         {"day_of_week": "mon-fri", "hour": "18,22", "minute": "30"})
        self.assertEqual(announcements.trigger.timezone.key, "Asia/Shanghai")
        self.assertEqual((announcements.max_instances, announcements.coalesce), (1, True))
        self.assertEqual(announcements.trigger.get_next_fire_time(None, anchor),
                         datetime(2026, 9, 28, 22, 30, tzinfo=ZoneInfo("Asia/Shanghai")))
        shanghai = ZoneInfo("Asia/Shanghai")
        self.assertEqual(announcements.trigger.get_next_fire_time(
            None, datetime(2026, 9, 28, 8, tzinfo=shanghai)),
            datetime(2026, 9, 28, 18, 30, tzinfo=shanghai))
        self.assertEqual(announcements.trigger.get_next_fire_time(
            None, datetime(2026, 10, 2, 22, 31, tzinfo=shanghai)),
            datetime(2026, 10, 5, 18, 30, tzinfo=shanghai))

    def test_phase_g_profile_only_changes_requested_triggers_and_expires(self):
        anchor = datetime(2026, 9, 29, 3, tzinfo=ZoneInfo("Asia/Shanghai"))
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "phase_g.json"
            state.write_text(json.dumps({"active": True, "start_at": anchor.isoformat(),
                                         "end_at": (anchor + timedelta(hours=48)).isoformat()}),
                             encoding="utf-8")
            self.assertEqual(run_scheduler.load_schedule_profile(anchor, state),
                             run_scheduler.PHASE_G_PROFILE)
            state.write_text(state.read_text(encoding="utf-8"), encoding="utf-8-sig")
            self.assertEqual(run_scheduler.load_schedule_profile(anchor, state),
                             run_scheduler.PHASE_G_PROFILE)
            self.assertEqual(run_scheduler.load_schedule_profile(
                anchor + timedelta(hours=48), state), run_scheduler.FORMAL_PROFILE)
            state.write_text('{"active":true,"start_at":"bad"}', encoding="utf-8")
            self.assertEqual(run_scheduler.load_schedule_profile(anchor, state),
                             run_scheduler.FORMAL_PROFILE)
        with patch.dict(os.environ, {}, clear=True):
            formal = run_scheduler.create_scheduler(anchor, run_scheduler.FORMAL_PROFILE)
            accelerated = run_scheduler.create_scheduler(anchor, run_scheduler.PHASE_G_PROFILE)
        before = {job.id: job for job in formal.get_jobs()}
        after = {job.id: job for job in accelerated.get_jobs()}
        self.assertEqual(set(before), set(after))
        self.assertEqual({name: int(after[name].trigger.interval.total_seconds() / 60)
                          for name in ("newsnow", "github", "rss", "auto_analysis")},
                         {"newsnow": 15, "github": 30, "rss": 60, "auto_analysis": 120})
        self.assertEqual(after["auto_analysis"].trigger.start_date -
                         after["rss"].trigger.start_date, timedelta(minutes=12))
        fields = {field.name: str(field) for field in after["market_announcements"].trigger.fields}
        self.assertEqual((fields["day_of_week"], fields["hour"], fields["minute"]),
                         ("mon-fri", "8,10,12,14,16,18,20,22", "30"))
        self.assertEqual(after["market_announcements"].trigger.timezone.key, "Asia/Shanghai")
        for name in ("market",):
            self.assertEqual(str(after[name].trigger), str(before[name].trigger))
        self.assertEqual(len(after), 8)

    def test_once_reuses_job_functions_and_isolates_failure(self):
        success = {"received": 3, "inserted": 0, "skipped": 3, "failed": 0}
        first = Mock(side_effect=RuntimeError("secret-never-log"))
        second = Mock(return_value=success)
        third = Mock(return_value=success)
        output = io.StringIO()
        with (patch.object(run_scheduler, "JOBS", (("NewsNow", 60, first),
                                                   ("GitHub", 120, second), ("RSS", 240, third))),
              patch.object(run_scheduler, "initialize_database"), contextlib.redirect_stdout(output)):
            self.assertEqual(run_scheduler.main(["--once"]), 1)
        for collect in (first, second, third):
            collect.assert_called_once_with()
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([row["status"] for row in rows], ["FAILED", "OK", "OK"])
        self.assertEqual((rows[1]["received"], rows[1]["inserted"], rows[1]["skipped"]), (3, 0, 3))
        self.assertNotIn("secret-never-log", output.getvalue())
        self.assertTrue(all(row["started_at"] and row["finished_at"] for row in rows))

    def test_jobs_delegate_to_existing_collectors_without_analyzer(self):
        summary = {"received": 0, "inserted": 0, "skipped": 0, "failed": 0}
        for connector_name, saver_name, job in (
            ("NewsNowConnector", "save_newsnow", run_scheduler.collect_newsnow_job),
            ("GitHubConnector", "save_github", run_scheduler.collect_github_job),
            ("RSSConnector", "save_rss", run_scheduler.collect_rss_job),
        ):
            with (self.subTest(job=job.__name__),
                  patch.object(run_scheduler, connector_name) as connector,
                  patch.object(run_scheduler, saver_name, return_value=summary) as saver,
                  patch("app.intelligence.analyzer.Analyzer") as analyzer):
                connector.return_value.collect.return_value = ["fake collection"]
                self.assertEqual(job(), summary)
                saver.assert_called_once_with(["fake collection"])
                analyzer.assert_not_called()

    def test_empty_success_logs_zero_without_claiming_insert(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = run_scheduler.run_job("RSS", lambda: {
                "received": 0, "inserted": 0, "skipped": 0, "failed": 0})
        self.assertEqual((result["received"], result["inserted"], result["status"]), (0, 0, "OK"))
        self.assertIn('"inserted": 0', output.getvalue())

    def test_keyboard_interrupt_waits_for_clean_shutdown(self):
        fake = Mock()
        fake.running = True
        fake.start.side_effect = KeyboardInterrupt
        fake.get_jobs.return_value = [Mock() for _ in range(7)]
        with (patch.object(run_scheduler, "initialize_database"),
              patch.object(run_scheduler, "scheduler_instance_lock") as lock,
              patch.object(run_scheduler, "create_scheduler", return_value=fake),
              contextlib.redirect_stdout(io.StringIO())):
            lock.return_value.__enter__.return_value = True
            self.assertEqual(run_scheduler.main([]), 0)
        fake.shutdown.assert_called_once_with(wait=True)

    def test_once_remains_collectors_only(self):
        summary = {"received": 0, "inserted": 0, "skipped": 0, "failed": 0}
        collectors = [Mock(return_value=summary) for _ in range(3)]
        jobs = tuple((name, minutes, fn) for (name, minutes, _), fn in zip(run_scheduler.JOBS, collectors))
        with (patch.object(run_scheduler, "JOBS", jobs),
              patch.object(run_scheduler, "run_auto_analysis_job") as analyze,
              patch.object(run_scheduler, "initialize_database"),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(run_scheduler.main(["--once"]), 0)
        analyze.assert_not_called()
        for fn in collectors:
            fn.assert_called_once_with()

    def test_once_analysis_reuses_scheduled_job_and_not_collectors(self):
        report = {"selected": 0, "analyzed": 0, "skipped": 0, "failed": 0,
                  "normal_calls": 0, "repair_count": 0, "provider_unavailable": False,
                  "aborted_remaining": 0, "results": []}
        with (patch.object(run_scheduler, "run_auto_analysis_job", return_value=report) as analyze,
              patch.object(run_scheduler, "run_once") as collectors,
              patch.object(run_scheduler, "initialize_database"),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(run_scheduler.main(["--once-analysis"]), 0)
        analyze.assert_called_once_with()
        collectors.assert_not_called()

    def test_once_market_runs_only_market_job(self):
        with (patch.object(run_scheduler, "run_market_job", return_value={"status": "OK"}) as market,
              patch.object(run_scheduler, "run_once") as collectors,
              patch.object(run_scheduler, "run_analysis_job") as analysis,
              patch.object(run_scheduler, "initialize_database")):
            self.assertEqual(run_scheduler.main(["--once-market"]), 0)
        market.assert_called_once_with()
        collectors.assert_not_called()
        analysis.assert_not_called()

    def test_market_job_reuses_collector_dedups_isolates_failure_and_never_analyzes(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        with factory() as session:
            session.add_all((MarketWatchlist(symbol="600000", market="SH", name="fails"),
                             MarketWatchlist(symbol="002782", market="SZ", name="works")))
            session.commit()

        class FakeProvider:
            def fetch_daily(self, symbol, market):
                if symbol == "600000":
                    raise RuntimeError("secret-never-log")
                return DailySnapshot(date(2026, 9, 28), Decimal(14), Decimal(15),
                                     Decimal(13), Decimal(14), Decimal(100),
                                     Decimal(1000), Decimal(1), "fake")

        output = io.StringIO()
        with (patch.object(run_scheduler, "collect_market_once",
                           side_effect=lambda: collect_once(FakeProvider(), factory)) as collector,
              patch.object(run_scheduler, "run_auto_analysis_job") as analysis,
              contextlib.redirect_stdout(output)):
            first = run_scheduler.run_market_job()
            second = run_scheduler.run_market_job()
            other = run_scheduler.run_job("RSS", lambda: {
                "received": 0, "inserted": 0, "skipped": 0, "failed": 0})
        self.assertEqual(collector.call_count, 2)
        analysis.assert_not_called()
        self.assertEqual((first["watchlist_count"], first["received"], first["inserted"],
                          first["skipped"], first["failed"], first["status"]),
                         (2, 1, 1, 0, 1, "WARNING"))
        self.assertEqual((second["inserted"], second["skipped"], second["failed"]),
                         (0, 1, 1))
        self.assertEqual(other["status"], "OK")
        self.assertNotIn("secret-never-log", output.getvalue())
        with factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketSnapshot)), 1)
        engine.dispose()

    def test_market_job_unexpected_error_does_not_affect_other_jobs(self):
        output = io.StringIO()
        with (patch.object(run_scheduler, "collect_market_job",
                           side_effect=RuntimeError("secret-never-log")),
              contextlib.redirect_stdout(output)):
            market = run_scheduler.run_market_job()
            other = run_scheduler.run_job("NewsNow", lambda: {
                "received": 0, "inserted": 0, "skipped": 0, "failed": 0})
        self.assertEqual(market["status"], "FAILED")
        self.assertEqual(other["status"], "OK")
        self.assertNotIn("secret-never-log", output.getvalue())

    def test_analysis_job_reuses_existing_queue_service(self):
        report = {"selected": 0, "analyzed": 0, "skipped": 0, "failed": 0,
                  "normal_calls": 0, "repair_count": 0, "provider_unavailable": False,
                  "aborted_remaining": 0, "results": []}
        with patch.object(run_scheduler, "run_queue_once", return_value=(Selection((), {}), report)) as queue:
            self.assertEqual(run_scheduler.run_auto_analysis_job()["selected"], 0)
        queue.assert_called_once_with()

    def test_provider_abort_log_and_collector_independence(self):
        report = {"selected": 3, "analyzed": 0, "skipped": 0, "failed": 1,
                  "normal_calls": 1, "repair_count": 0, "provider_unavailable": True,
                  "aborted_remaining": 2, "results": []}
        collector = Mock(return_value={"received": 0, "inserted": 0, "skipped": 0, "failed": 0})
        with (patch.object(run_scheduler, "run_auto_analysis_job", return_value=report),
              patch.object(run_scheduler, "JOBS", (("NewsNow", 60, collector),)),
              contextlib.redirect_stdout(io.StringIO())):
            result = run_scheduler.run_analysis_job()
            run_scheduler.run_once()
        self.assertEqual((result["status"], result["aborted_remaining"]),
                         ("PROVIDER_UNAVAILABLE", 2))
        collector.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
