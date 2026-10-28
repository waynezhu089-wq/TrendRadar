import unittest
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import MarketSnapshot, MarketWatchlist
from app.db.seed import seed
from app.main import app
from app.commands import run_scheduler
from app.market.collection import collect_backfill, collect_once
from app.market.provider import DailySnapshot, TencentDailyProvider, normalize_tencent_day
from app.market.symbols import normalize_symbol
from app.market.technical import compute_technical_state


class FakeProvider:
    def __init__(self, failing=()):
        self.failing = set(failing)

    def fetch_daily(self, symbol, market):
        if symbol in self.failing:
            raise RuntimeError("provider unavailable")
        return DailySnapshot(date(2026, 9, 28), Decimal("14.96"), Decimal("15.00"),
                             Decimal("13.95"), Decimal("14.14"), Decimal("9616700"),
                             Decimal("136900600"), Decimal("1.96"), "fake")


def fixture_days(count=30):
    start = date(2026, 8, 30)
    return [DailySnapshot(
        start + timedelta(days=index), Decimal(index), Decimal(index + 1),
        Decimal(index - 1), Decimal(index), Decimal(index * 100),
        Decimal(index * 1000), None, "fake",
    ) for index in range(1, count + 1)]


class FakeHistoryProvider:
    def __init__(self):
        self.days = fixture_days()
        self.daily_calls = 0
        self.history_calls = 0

    def fetch_daily(self, symbol, market):
        self.daily_calls += 1
        return self.days[-1]

    def fetch_recent_daily(self, symbol, market, limit=30):
        self.history_calls += 1
        return self.days[-limit:]


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as session:
            seed(session)
        self.session = self.factory()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        self.before = self._intelligence_rows()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def _intelligence_rows(self):
        with self.engine.connect() as connection:
            return {table: connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all()
                    for table in ("sources", "items", "analysis", "feedback", "watchlist")}

    def test_symbol_normalization_and_invalid_symbol(self):
        self.assertEqual(normalize_symbol(" 002782.sz ", "sz"), ("002782", "SZ"))
        for symbol, market in (("600000", "SH"), ("002782", "SZ"), ("430047", "BJ")):
            self.assertEqual(normalize_symbol(symbol, market), (symbol, market))
        for symbol, market in (("abc", "SZ"), ("002782", "SH"), ("002782.HK", "SZ"),
                               ("002782", "HK"), ("1234567", "SZ")):
            with self.assertRaises(ValueError):
                normalize_symbol(symbol, market)

    def test_watchlist_crud_duplicate_and_empty_market(self):
        self.assertEqual(self.client.get("/api/v1/market").json(), {"items": []})
        first = self.client.post("/api/v1/market/watchlist",
                                 json={"symbol": "002782.SZ", "market": "sz", "name": "可立克"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["symbol"], "002782")
        self.assertEqual(first.json()["market"], "SZ")
        self.assertEqual(self.client.post("/api/v1/market/watchlist",
            json={"symbol": "002782", "market": "SZ", "name": "Duplicate"}).status_code, 409)
        for bad in ({"symbol": "002782", "market": "SH", "name": "Bad"},
                    {"symbol": "abcdef", "market": "SZ", "name": "Bad"},
                    {"symbol": "002782", "market": "HK", "name": "Bad"}):
            self.assertEqual(self.client.post("/api/v1/market/watchlist", json=bad).status_code, 422)
        self.assertEqual(len(self.client.get("/api/v1/market/watchlist").json()), 1)
        item = self.client.get("/api/v1/market").json()["items"][0]
        self.assertIsNone(item["date"])
        self.assertIsNone(item["close"])
        self.assertEqual(item["technical"]["sample_days"], 0)
        self.assertIsNone(item["technical"]["ma20"])
        self.assertEqual(self.client.delete("/api/v1/market/watchlist/9999").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/market/watchlist/{first.json()['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/market/watchlist").json(), [])
        self.assertEqual(self._intelligence_rows(), self.before)

    def test_provider_normalization_snapshot_persistence_and_dedup(self):
        normalized = normalize_tencent_day(
            ["2026-09-28", "14.96", "14.14", "14.96", "13.95", "96167.00", {},
             "1.96", "13690.06"])
        self.assertEqual(normalized.volume, Decimal("9616700.00"))
        self.assertEqual(normalized.amount, Decimal("136900600.00"))
        self.assertEqual(normalized.turnover, Decimal("1.96"))
        with self.factory() as session:
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="可立克"))
            session.commit()
        first = collect_once(FakeProvider(), self.factory)
        second = collect_once(FakeProvider(), self.factory)
        self.assertEqual((first[0].inserted, first[0].skipped), (1, 0))
        self.assertEqual((second[0].inserted, second[0].skipped), (0, 1))
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketSnapshot)), 1)
        item = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(item["date"], "2026-09-28")
        self.assertEqual(item["close"], 14.14)
        self.assertEqual(item["source"], "fake")
        self.assertEqual(item["technical"]["sample_days"], 1)
        self.assertIsNone(item["technical"]["change_pct"])
        self.assertEqual(self._intelligence_rows(), self.before)

    def test_backfill_dedup_latest_only_and_market_api(self):
        with self.factory() as session:
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="可立克"))
            session.commit()
        provider = FakeHistoryProvider()
        once = collect_once(provider, self.factory)
        self.assertEqual((once[0].inserted, once[0].skipped), (1, 0))
        self.assertEqual((provider.daily_calls, provider.history_calls), (1, 0))
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketSnapshot)), 1)
        first = collect_backfill(30, provider, self.factory)
        second = collect_backfill(30, provider, self.factory)
        self.assertEqual((first[0].inserted, first[0].skipped), (29, 1))
        self.assertEqual((second[0].inserted, second[0].skipped), (0, 30))
        self.assertEqual(provider.history_calls, 2)
        with self.factory() as session:
            rows = session.scalars(select(MarketSnapshot).order_by(MarketSnapshot.date)).all()
            self.assertEqual([row.date for row in rows], [day.date for day in provider.days])
        item = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(item["technical"]["sample_days"], 30)
        self.assertEqual(item["technical"]["ma20"], 20.5)
        self.assertEqual(item["technical"]["volume_ratio_5d"], 1.1111)
        self.assertEqual(self._intelligence_rows(), self.before)

    def test_provider_failure_isolated(self):
        with self.factory() as session:
            session.add_all((MarketWatchlist(symbol="600000", market="SH", name="One"),
                             MarketWatchlist(symbol="002782", market="SZ", name="Two")))
            session.commit()
        results = collect_once(FakeProvider({"600000"}), self.factory)
        self.assertEqual([(row.symbol, row.failed, row.inserted) for row in results],
                         [("600000", 1, 0), ("002782", 0, 1)])
        self.assertEqual(self._intelligence_rows(), self.before)

    def test_provider_history_normalizes_and_sorts_days(self):
        provider = TencentDailyProvider()
        year = date.today().year
        rows = [
            ["2026-09-28", "14.96", "14.14", "14.96", "13.95", "96167", {}, "1.96", "13690.06"],
            ["2026-09-24", "15.43", "14.96", "15.43", "14.93", "68359", {}, "1.40", "10333.08"],
        ]
        response = type("Response", (), {
            "text": f"kline_day{year}=" + json.dumps({"code": 0, "data": {"sz002782": {"day": rows}}}),
            "raise_for_status": lambda self: None,
        })()
        with patch("app.market.provider.httpx.get", return_value=response) as request:
            days = provider.fetch_recent_daily("002782", "SZ", limit=30)
            self.assertEqual([day.date.isoformat() for day in days], ["2026-09-24", "2026-09-28"])
            self.assertEqual(days[-1].volume, Decimal("9616700"))
            self.assertIn("sz002782,day,,,30,", request.call_args.kwargs["params"]["param"])
            self.assertEqual(provider.fetch_daily("002782", "SZ").date, date(2026, 9, 28))

    def test_command_once_and_backfill_dispatch(self):
        from app.commands.collect_market import main
        with patch("app.commands.collect_market.initialize_database"), \
             patch("app.commands.collect_market.collect_once", return_value=[]) as once, \
             patch("app.commands.collect_market.collect_backfill", return_value=[]) as backfill:
            with patch.object(sys, "argv", ["collect_market", "--once"]), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            once.assert_called_once_with()
            backfill.assert_not_called()
            with patch.object(sys, "argv", ["collect_market", "--backfill", "30"]), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            backfill.assert_called_once_with(30)

    def test_scheduled_new_day_is_immediately_used_by_technical_api(self):
        days = fixture_days(21)
        with self.factory() as session:
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="可立克"))
            for daily in days[:20]:
                session.add(MarketSnapshot(symbol="002782", market="SZ", **daily.__dict__))
            session.commit()
        before = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(before["date"], days[19].date.isoformat())

        class NewDayProvider:
            def fetch_daily(self, symbol, market):
                return days[20]

        with patch.object(run_scheduler, "collect_market_once",
                          side_effect=lambda: collect_once(NewDayProvider(), self.factory)), \
             patch.object(run_scheduler, "run_auto_analysis_job") as analysis, \
             redirect_stdout(io.StringIO()):
            result = run_scheduler.run_market_job()
        self.assertEqual((result["inserted"], result["failed"]), (1, 0))
        analysis.assert_not_called()
        after = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(after["date"], days[20].date.isoformat())
        self.assertEqual(after["technical"]["change_pct"], 5.0)
        self.assertEqual(after["technical"]["ma20"], 11.5)
        self.assertEqual(self._intelligence_rows(), self.before)


if __name__ == "__main__":
    unittest.main()
