import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.commands import run_scheduler
from app.commands.send_feishu_brief import main as manual_brief_main
from app.db.database import Base
from app.db.models import NotificationDelivery
from app.feishu.brief import BriefItem, build_daily_brief
from app.feishu.schedule import load_brief_schedule_config, run_scheduled_brief
from app.feishu.sender import FeishuSendError, SendReceipt


WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/FAKE-SECRET"
CONFIG = {"DSIH_FEISHU_WEBHOOK_URL": WEBHOOK,
          "DSIH_FEISHU_BRIEF_TIME": "08:30",
          "DSIH_FEISHU_BRIEF_TIMEZONE": "Asia/Shanghai"}


def sample_brief(empty=False):
    items = [] if empty else [BriefItem("Example", "Existing summary", "https://example.org")]
    return build_daily_brief(items, [], [], [],
                             datetime(2026, 9, 29, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai")))


class BriefScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name, 'brief.db').as_posix()}")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.config = load_brief_schedule_config(CONFIG)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def delivery_rows(self):
        with self.factory() as session:
            return session.scalars(select(NotificationDelivery)).all()

    def test_config_validates_time_zone_and_webhook_without_http(self):
        self.assertEqual((self.config.send_time.hour, self.config.send_time.minute), (8, 30))
        self.assertEqual(self.config.zone.key, "Asia/Shanghai")
        for update in ({"DSIH_FEISHU_BRIEF_TIME": "25:00"},
                       {"DSIH_FEISHU_BRIEF_TIME": "8:30"},
                       {"DSIH_FEISHU_BRIEF_TIME": "08:60"},
                       {"DSIH_FEISHU_BRIEF_TIMEZONE": "Invalid/Zone"},
                       {"DSIH_FEISHU_WEBHOOK_URL": "https://example.org/hook"}):
            with self.subTest(update=update):
                self.assertIsNone(load_brief_schedule_config({**CONFIG, **update}))
        for missing in CONFIG:
            with self.subTest(missing=missing):
                self.assertIsNone(load_brief_schedule_config(
                    {key: value for key, value in CONFIG.items() if key != missing}))

    def test_seventh_cron_is_configured_and_six_jobs_are_unchanged(self):
        anchor = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
        with patch.dict(os.environ, {}, clear=True):
            before = run_scheduler.create_scheduler(anchor, run_scheduler.FORMAL_PROFILE)
        with patch.dict(os.environ, CONFIG, clear=True):
            after = run_scheduler.create_scheduler(anchor, run_scheduler.FORMAL_PROFILE)
            accelerated = run_scheduler.create_scheduler(anchor, run_scheduler.PHASE_G_PROFILE)
        existing = {job.id: job for job in before.get_jobs()}
        configured = {job.id: job for job in after.get_jobs()}
        self.assertEqual(len(existing), 8)
        self.assertEqual(len(configured), 9)
        self.assertEqual(set(configured) - set(existing), {"feishu_daily_brief"})
        for name, old in existing.items():
            new = configured[name]
            self.assertEqual((str(new.trigger), new.max_instances, new.coalesce),
                             (str(old.trigger), old.max_instances, old.coalesce))
        brief = configured["feishu_daily_brief"]
        fields = {field.name: str(field) for field in brief.trigger.fields}
        self.assertEqual((fields["hour"], fields["minute"], fields["day_of_week"]),
                         ("8", "30", "*"))
        self.assertEqual(brief.trigger.timezone.key, "Asia/Shanghai")
        self.assertEqual((brief.max_instances, brief.coalesce), (1, True))
        self.assertEqual(brief.trigger.get_next_fire_time(None, anchor),
                         datetime(2026, 9, 29, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai")))
        accelerated_brief = accelerated.get_job("feishu_daily_brief")
        self.assertEqual(len(accelerated.get_jobs()), 9)
        self.assertEqual((str(accelerated_brief.trigger), accelerated_brief.trigger.timezone.key,
                          accelerated_brief.max_instances, accelerated_brief.coalesce),
                         (str(brief.trigger), brief.trigger.timezone.key,
                          brief.max_instances, brief.coalesce))

    def test_success_same_day_guard_and_next_day_timezone(self):
        sender = Mock()
        sender.return_value.send.return_value = SendReceipt(200, 0)
        builder = Mock(return_value=sample_brief())
        # Still September 29 in Shanghai, although UTC is September 28.
        first_instant = datetime(2026, 9, 28, 17, tzinfo=timezone.utc)
        first = run_scheduled_brief(self.config, self.factory, first_instant, builder, sender)
        second = run_scheduled_brief(self.config, self.factory, first_instant, builder, sender)
        self.assertEqual((first["status"], first["delivery_date"], first["http_calls"]),
                         ("SENT", "2026-09-29", 1))
        self.assertEqual((second["status"], second["http_calls"]),
                         ("SKIP_ALREADY_SENT_TODAY", 0))
        self.assertEqual(sender.return_value.send.call_count, 1)
        self.assertEqual(builder.call_count, 1)
        rows = self.delivery_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].channel, rows[0].notification_type,
                          rows[0].delivery_date, rows[0].status),
                         ("feishu", "daily_brief", date(2026, 9, 29), "SENT"))

        next_day = run_scheduled_brief(self.config, self.factory,
                                       datetime(2026, 9, 29, 17, tzinfo=timezone.utc),
                                       builder, sender)
        self.assertEqual((next_day["status"], next_day["delivery_date"]),
                         ("SENT", "2026-09-30"))
        self.assertEqual(len(self.delivery_rows()), 2)

    def test_failure_does_not_record_sent_and_empty_brief_does_not_send(self):
        failing = Mock()
        failing.return_value.send.side_effect = FeishuSendError("NETWORK_ERROR")
        builder = Mock(return_value=sample_brief())
        failed = run_scheduled_brief(self.config, self.factory,
                                     datetime(2026, 9, 29, tzinfo=timezone.utc),
                                     builder, failing)
        self.assertEqual((failed["status"], failed["http_calls"]), ("FAILED", 1))
        self.assertEqual(len(self.delivery_rows()), 0)
        empty_sender = Mock()
        empty = run_scheduled_brief(self.config, self.factory,
                                    datetime(2026, 9, 29, tzinfo=timezone.utc),
                                    Mock(return_value=sample_brief(empty=True)), empty_sender)
        self.assertEqual((empty["status"], empty["http_calls"]), ("NO_CONTENT", 0))
        empty_sender.assert_not_called()
        self.assertEqual(len(self.delivery_rows()), 0)

    def test_missing_config_and_manual_dry_run_are_write_free(self):
        sender = Mock()
        with patch.dict(os.environ, {}, clear=True):
            blocked = run_scheduled_brief(session_factory=self.factory,
                                          builder=Mock(), sender_class=sender)
        self.assertEqual(blocked, {"status": "FEISHU_BRIEF_SCHEDULE_NOT_CONFIGURED",
                                   "http_calls": 0})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manual_brief_main(["--dry-run"],
                             builder=lambda: sample_brief(), sender_class=sender), 0)
        sender.assert_not_called()
        self.assertEqual(len(self.delivery_rows()), 0)

    def test_once_brief_runs_only_brief_and_never_llm(self):
        output = io.StringIO()
        with (patch.object(run_scheduler, "initialize_database"),
              patch.object(run_scheduler, "run_scheduled_brief",
                           return_value={"status": "SKIP_ALREADY_SENT_TODAY",
                                         "http_calls": 0}) as brief,
              patch.object(run_scheduler, "run_once") as collectors,
              patch.object(run_scheduler, "run_analysis_job") as analysis,
              patch.object(run_scheduler, "run_market_job") as market,
              patch.object(run_scheduler, "run_market_announcements_job") as announcements,
              patch("app.intelligence.analyzer.Analyzer") as analyzer,
              contextlib.redirect_stdout(output)):
            self.assertEqual(run_scheduler.main(["--once-brief"]), 0)
        brief.assert_called_once_with()
        for other in (collectors, analysis, market, announcements, analyzer):
            other.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["http_calls"], 0)


if __name__ == "__main__":
    unittest.main()
