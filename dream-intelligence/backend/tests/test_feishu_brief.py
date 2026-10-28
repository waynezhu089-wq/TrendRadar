import contextlib
import io
import json
import os
import unittest
from datetime import date, datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commands.send_feishu_brief import build_current_brief, main
from app.db.database import Base
from app.db.models import MarketAnnouncement, MarketAnnouncementRead, MarketWatchlist
from app.feishu.brief import (BriefAnnouncement, BriefItem, BriefMarket,
                              build_daily_brief)
from app.feishu.sender import FeishuSendError, FeishuWebhookSender, SendReceipt

NOW = datetime(2026, 9, 29, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
OFFICIAL = "https://disc.static.szse.cn/announcement.PDF"
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/SECRET-DO-NOT-LOG"


def fixture_brief(must_count=5, relevant_count=4, unread_count=7):
    return build_daily_brief(
        [BriefItem(f"Must {i}", "Existing summary", "https://example.org/story")
         for i in range(must_count)],
        [BriefItem(f"Relevant {i}", "Existing summary", "http://127.0.0.1:5173/story")
         for i in range(relevant_count)],
        [BriefMarket("可立克", "002782", "SZ", date(2026, 9, 28), None, None, None, None)],
        [BriefAnnouncement(f"Official {i}", NOW, OFFICIAL) for i in range(5)],
        NOW, unread_total=unread_count)


class BriefBuilderTests(unittest.TestCase):
    def test_limits_overflow_external_links_and_missing_values(self):
        brief = fixture_brief()
        encoded = json.dumps(brief.payload, ensure_ascii=False)
        self.assertEqual(brief.shown, {"must_read": 3, "relevant": 3,
                                       "market": 1, "unread_announcements": 3})
        self.assertEqual(brief.totals["unread_announcements"], 7)
        self.assertIn("另有 2 条", encoded)
        self.assertIn("另有 1 条", encoded)
        self.assertIn("另有 4 条", encoded)
        self.assertIn("[查看原文](https://example.org/story)", encoded)
        self.assertIn("[查看官方公告](https://disc.static.szse.cn/announcement.PDF)", encoded)
        self.assertNotIn("127.0.0.1", encoded)
        self.assertNotIn("localhost", encoded)
        self.assertIn("收盘：—", encoded)
        self.assertIn("距 MA20：—", encoded)
        self.assertEqual(brief.payload["msg_type"], "interactive")

    def test_missing_and_local_item_urls_omitted_empty_brief_is_valid(self):
        brief = build_daily_brief(
            [BriefItem("No URL", "summary", None),
             BriefItem("Local URL", "summary", "http://localhost:5173/story")],
            [], [], [], NOW)
        text = json.dumps(brief.payload, ensure_ascii=False)
        self.assertNotIn("[查看原文]", text)
        self.assertNotIn("localhost", text)
        self.assertTrue(brief.has_content)
        empty = build_daily_brief([], [], [], [], NOW)
        self.assertFalse(empty.has_content)
        self.assertEqual(empty.totals["unread_announcements"], 0)
        self.assertEqual(len(empty.sections), 4)

    def test_current_brief_is_read_only_and_excludes_read_announcements(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        with factory() as session:
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="可立克"))
            for number in range(1, 5):
                session.add(MarketAnnouncement(
                    symbol="002782", market="SZ", external_id=str(number),
                    title=f"Official {number}", url=OFFICIAL,
                    published_at=datetime(2026, 9, number), source="SZSE",
                    raw_json={"annId": number}))
            session.commit()
            session.add(MarketAnnouncementRead(announcement_id=4))
            session.commit()
        with engine.connect() as connection:
            tables = ("market_watchlist", "market_announcements", "market_announcement_reads")
            before = {table: connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all()
                      for table in tables}
        brief = build_current_brief(factory, NOW)
        encoded = json.dumps(brief.payload, ensure_ascii=False)
        self.assertEqual((brief.totals["unread_announcements"],
                          brief.shown["unread_announcements"]), (3, 3))
        self.assertNotIn("Official 4", encoded)
        self.assertIn("Official 3", encoded)
        self.assertIn("[查看官方公告]", encoded)
        with engine.connect() as connection:
            after = {table: connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all()
                     for table in tables}
        self.assertEqual(after, before)
        engine.dispose()


class SenderAndCliTests(unittest.TestCase):
    def test_sender_success_failure_and_secret_never_in_error(self):
        payload = fixture_brief().payload
        response = Mock(status_code=200)
        response.json.return_value = {"code": 0, "msg": "success"}
        with patch("app.feishu.sender.httpx.post", return_value=response) as request:
            receipt = FeishuWebhookSender(WEBHOOK).send(payload)
        self.assertEqual(receipt, SendReceipt(200, 0))
        request.assert_called_once()
        self.assertFalse(request.call_args.kwargs["follow_redirects"])
        response.json.return_value = {"code": 19024, "msg": "secret detail"}
        with patch("app.feishu.sender.httpx.post", return_value=response):
            with self.assertRaises(FeishuSendError) as failure:
                FeishuWebhookSender(WEBHOOK).send(payload)
        self.assertEqual(failure.exception.code, "FEISHU_19024")
        self.assertNotIn("SECRET-DO-NOT-LOG", str(failure.exception))
        self.assertNotIn("secret detail", str(failure.exception))
        with patch("app.feishu.sender.httpx.post",
                   side_effect=httpx.ConnectError(WEBHOOK)):
            with self.assertRaises(FeishuSendError) as network:
                FeishuWebhookSender(WEBHOOK).send(payload)
        self.assertEqual(network.exception.code, "NETWORK_ERROR")
        self.assertNotIn("SECRET-DO-NOT-LOG", str(network.exception))

    def test_cli_dry_run_zero_http_once_one_http_and_empty_skips(self):
        brief = fixture_brief()
        sender = Mock()
        sender.return_value.send.return_value = SendReceipt(200, 0)
        output = io.StringIO()
        with (patch.dict(os.environ, {"DSIH_FEISHU_WEBHOOK_URL": WEBHOOK}),
              contextlib.redirect_stdout(output)):
            self.assertEqual(main(["--dry-run"], builder=lambda: brief,
                                  sender_class=sender), 0)
            self.assertEqual(main(["--once"], builder=lambda: brief,
                                  sender_class=sender), 0)
        sender.assert_called_once_with(WEBHOOK)
        sender.return_value.send.assert_called_once_with(brief.payload)
        self.assertEqual([json.loads(line)["status"] for line in output.getvalue().splitlines()],
                         ["DRY_RUN", "SENT"])
        self.assertNotIn(WEBHOOK, output.getvalue())
        self.assertNotIn("127.0.0.1", output.getvalue())

        empty = build_daily_brief([], [], [], [], NOW)
        with (patch.dict(os.environ, {"DSIH_FEISHU_WEBHOOK_URL": WEBHOOK}),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(main(["--once"], builder=lambda: empty,
                                  sender_class=sender), 0)
        sender.return_value.send.assert_called_once()

    def test_cli_missing_webhook_blocks_without_sender_or_llm(self):
        sender = Mock()
        output = io.StringIO()
        with (patch.dict(os.environ, {}, clear=True),
              patch("app.intelligence.analyzer.Analyzer") as analyzer,
              contextlib.redirect_stdout(output)):
            result = main(["--once"], builder=fixture_brief, sender_class=sender)
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["reason"],
                         "FEISHU_WEBHOOK_NOT_CONFIGURED")
        sender.assert_not_called()
        analyzer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
