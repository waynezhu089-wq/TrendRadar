import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import MarketAnnouncement, MarketSnapshot, MarketWatchlist
from app.db.seed import seed
from app.main import app
from app.market.announcement_collection import collect_announcements_once
from app.market.announcements import (SZSEAnnouncementProvider, UnsupportedMarketError,
                                      normalize_szse_announcement, official_url)


def official_row(ann_id=123, date="2026-09-28 00:00:00", title="可立克：官方公告"):
    return {
        "annId": ann_id, "id": f"uuid-{ann_id}", "title": title,
        "publishTime": date, "secCode": ["002782"],
        "attachPath": f"/disc/disk03/finalpage/2026-09-28/{ann_id}.PDF",
    }


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class AnnouncementProviderTests(unittest.TestCase):
    def test_normalize_stable_id_original_title_date_and_official_pdf(self):
        row = official_row(title="  可立克：原始标题  ")
        first = normalize_szse_announcement(row, "002782")
        second = normalize_szse_announcement(row, "002782")
        self.assertEqual(first.external_id, "123")
        self.assertEqual(first.external_id, second.external_id)
        self.assertEqual(first.title, row["title"])
        self.assertEqual(first.url, "https://disc.static.szse.cn/download" + row["attachPath"])
        self.assertEqual(first.published_at.date().isoformat(), "2026-09-28")
        self.assertEqual(first.source, "SZSE")
        self.assertEqual(first.raw_json, row)
        without_id = {key: value for key, value in row.items() if key not in ("annId", "id")}
        fallback = normalize_szse_announcement(without_id, "002782")
        self.assertEqual(len(fallback.external_id), 64)
        self.assertEqual(fallback.external_id,
                         normalize_szse_announcement(without_id, "002782").external_id)
        self.assertIsNone(normalize_szse_announcement(official_row(date=None), "002782").published_at)

    def test_official_domain_enforced(self):
        self.assertEqual(official_url(" https://www.szse.cn/a#fragment "), "https://www.szse.cn/a")
        for url in ("https://szse.cn.evil.example/a", "http://www.szse.cn/a",
                    "https://evil.example/a", "https://www.szse.cn@evil.example/a"):
            with self.assertRaises(ValueError):
                official_url(url)
        bad = official_row()
        bad["attachPath"] = "https://evil.example/fake.pdf"
        with self.assertRaises(ValueError):
            normalize_szse_announcement(bad, "002782")
        bad["attachPath"] = "//evil.example/fake.pdf"
        with self.assertRaises(ValueError):
            normalize_szse_announcement(bad, "002782")

    def test_provider_request_limit_sort_zero_vs_bad_response_and_unsupported_market(self):
        provider = SZSEAnnouncementProvider()
        rows = [official_row(i, f"2026-09-{(i % 28) + 1:02d} 00:00:00") for i in range(1, 13)]
        with patch("app.market.announcements.httpx.post", return_value=FakeResponse(
                {"announceCount": 12, "data": rows})) as request:
            announcements = provider.fetch_recent("002782", "SZ", limit=10)
        self.assertEqual(len(announcements), 10)
        self.assertEqual([row.published_at for row in announcements],
                         sorted([row.published_at for row in announcements], reverse=True))
        self.assertEqual(request.call_args.kwargs["json"]["pageSize"], 10)
        self.assertEqual(request.call_args.kwargs["json"]["stock"], ["002782"])
        self.assertFalse(request.call_args.kwargs["follow_redirects"])
        with patch("app.market.announcements.httpx.post", return_value=FakeResponse(
                {"announceCount": 0, "data": []})):
            self.assertEqual(provider.fetch_recent("002782", "SZ"), [])
        with patch("app.market.announcements.httpx.post", return_value=FakeResponse(
                {"announceCount": 3, "data": []})):
            with self.assertRaises(ValueError):
                provider.fetch_recent("002782", "SZ")
        for market in ("SH", "BJ"):
            with self.assertRaises(UnsupportedMarketError):
                provider.fetch_recent("002782", market)


class AnnouncementCollectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as session:
            seed(session)
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="可立克"))
            session.add(MarketSnapshot(
                symbol="002782", market="SZ", date=datetime(2026, 9, 28).date(),
                close=14.14, source="fake"))
            session.commit()
        self.session = self.factory()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        self.before_rows = self._protected_rows()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def _protected_rows(self):
        with self.engine.connect() as connection:
            return {table: connection.exec_driver_sql(f'SELECT * FROM "{table}" ORDER BY id').all()
                    for table in ("sources", "items", "analysis", "feedback", "watchlist",
                                  "market_watchlist", "market_snapshots")}

    def test_collection_dedup_and_market_api_preserve_snapshot_and_technical(self):
        before = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(before["announcements"], [])
        rows = [official_row(i, f"2026-09-{i:02d} 00:00:00") for i in range(1, 8)]

        class FakeProvider:
            def fetch_recent(self, symbol, market, limit=10):
                return [normalize_szse_announcement(row, symbol) for row in rows[:limit]]

        first = collect_announcements_once(FakeProvider(), self.factory)[0]
        second = collect_announcements_once(FakeProvider(), self.factory)[0]
        self.assertEqual((first.received, first.inserted, first.skipped, first.failed), (7, 7, 0, 0))
        self.assertEqual((second.received, second.inserted, second.skipped, second.failed), (7, 0, 7, 0))
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncement)), 7)
        after = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual([row["published_at"][:10] for row in after["announcements"]],
                         [f"2026-09-{i:02d}" for i in range(7, 2, -1)])
        self.assertEqual(len(after["announcements"]), 5)
        self.assertEqual(after["unread_announcement_count"], 7)
        self.assertTrue(all(not row["is_read"] for row in after["announcements"]))
        self.assertTrue(all(row["url"].startswith("https://disc.static.szse.cn/")
                            for row in after["announcements"]))
        self.assertEqual({key: value for key, value in before.items()
                          if key not in ("announcements", "unread_announcement_count")},
                         {key: value for key, value in after.items()
                          if key not in ("announcements", "unread_announcement_count")})
        self.assertEqual(self._protected_rows(), self.before_rows)

    def test_failure_isolation_and_injected_nonofficial_link_rejected(self):
        with self.factory() as session:
            session.add(MarketWatchlist(symbol="600000", market="SH", name="unsupported"))
            session.commit()
        initial = self._protected_rows()

        class FakeProvider:
            def fetch_recent(self, symbol, market, limit=10):
                if market != "SZ":
                    raise UnsupportedMarketError("unsupported")
                return [normalize_szse_announcement(official_row(), symbol)]

        results = collect_announcements_once(FakeProvider(), self.factory)
        self.assertEqual([(row.market, row.failed, row.inserted) for row in results],
                         [("SZ", 0, 1), ("SH", 1, 0)])
        self.assertEqual(self._protected_rows(), initial)

        class BadProvider:
            def fetch_recent(self, symbol, market, limit=10):
                valid = normalize_szse_announcement(official_row(456), symbol)
                return [valid.__class__(**{**valid.__dict__, "url": "https://evil.example/fake.pdf"})]

        bad = collect_announcements_once(BadProvider(), self.factory)
        self.assertEqual(bad[0].failed, 1)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncement)), 1)


if __name__ == "__main__":
    unittest.main()
