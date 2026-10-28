import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.db.models import Item
from app.db.seed import seed

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        seed(self.session)
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_today_accepts_null_published_at_without_mutating_item(self):
        item = self.session.scalar(select(Item))
        item.published_at = None
        self.session.commit()
        before = {column.name: getattr(item, column.name) for column in Item.__table__.columns}
        response = self.client.get("/api/v1/today")
        self.assertEqual(response.status_code, 200)
        card = response.json()["items"][0]
        self.assertEqual(card["id"], item.id)
        self.assertIn("published_at", card)
        self.assertIsNone(card["published_at"])
        self.session.refresh(item)
        self.assertEqual(before, {column.name: getattr(item, column.name) for column in Item.__table__.columns})

    def test_today_reads_database_and_seed_is_idempotent(self):
        seed(self.session)
        item = self.session.scalar(select(Item))
        item.title = "SQLite test title"
        self.session.commit()
        response = self.client.get("/api/v1/today")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["title"], "SQLite test title")
        self.assertEqual(data["items"][0]["priority"], 91)
        self.assertEqual(data["stats"], dict(raw_items=1, analyzed=1, relevant=0, must_read=1))

if __name__ == "__main__":
    unittest.main()
