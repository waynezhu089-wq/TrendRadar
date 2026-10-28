import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import (MarketAnnouncement, MarketAnnouncementDocument,
                           MarketAnnouncementRead, MarketWatchlist)
from app.main import app


class MarketAnnouncementReadTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as session:
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="fixture"))
            for number in range(1, 11):
                session.add(MarketAnnouncement(
                    symbol="002782", market="SZ", external_id=str(number),
                    title=f"Official announcement {number}",
                    url=f"https://disc.static.szse.cn/{number}.PDF",
                    published_at=datetime(2026, 9, number, tzinfo=timezone.utc),
                    source="SZSE", raw_json={"annId": number}))
            session.commit()
            session.add(MarketAnnouncementDocument(
                announcement_id=1, status="READABLE", text="Existing body",
                char_count=13, extractor="pypdf"))
            session.commit()
        self.session = self.factory()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        with self.engine.connect() as connection:
            self.metadata_before = connection.exec_driver_sql(
                "SELECT * FROM market_announcements ORDER BY id").all()
            self.documents_before = connection.exec_driver_sql(
                "SELECT * FROM market_announcement_documents ORDER BY id").all()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_default_unread_total_idempotent_read_reset_and_persistence(self):
        initial = self.client.get("/api/v1/market")
        self.assertEqual(initial.status_code, 200)
        item = initial.json()["items"][0]
        self.assertEqual(item["unread_announcement_count"], 10)
        self.assertEqual([row["id"] for row in item["announcements"]], [10, 9, 8, 7, 6])
        self.assertTrue(all(not row["is_read"] for row in item["announcements"]))

        # An older announcement outside the five-item list must still affect the total.
        first = self.client.post("/api/v1/market/announcements/1/read")
        again = self.client.post("/api/v1/market/announcements/1/read")
        self.assertEqual((first.status_code, again.status_code), (200, 200))
        self.assertEqual(first.json(), again.json())
        self.assertEqual(first.json()["announcement_id"], 1)
        self.assertTrue(first.json()["is_read"])
        self.assertTrue(first.json()["read_at"])
        self.assertEqual(self.client.get("/api/v1/market").json()["items"][0][
            "unread_announcement_count"], 9)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncementRead)), 1)

        latest = self.client.post("/api/v1/market/announcements/10/read")
        self.assertEqual(latest.status_code, 200)
        after = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual(after["unread_announcement_count"], 8)
        self.assertTrue(after["announcements"][0]["is_read"])
        self.assertFalse(after["announcements"][1]["is_read"])

        self.assertEqual(self.client.delete("/api/v1/market/announcements/10/read").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/market/announcements/1/read").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/market/announcements/1/read").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/market").json()["items"][0][
            "unread_announcement_count"], 10)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncementRead)), 0)

        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql(
                "SELECT * FROM market_announcements ORDER BY id").all(), self.metadata_before)
            self.assertEqual(connection.exec_driver_sql(
                "SELECT * FROM market_announcement_documents ORDER BY id").all(),
                             self.documents_before)

    def test_nonexistent_announcement_is_404(self):
        self.assertEqual(self.client.post("/api/v1/market/announcements/999/read").status_code, 404)
        self.assertEqual(self.client.delete("/api/v1/market/announcements/999/read").status_code, 404)


if __name__ == "__main__":
    unittest.main()
