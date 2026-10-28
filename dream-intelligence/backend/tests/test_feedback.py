import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import Analysis, Feedback, Item, Source
from app.main import app


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        source = Source(name="Real feed", type="rss", category="AI")
        self.session.add(source)
        self.session.flush()
        self.items = []
        for index, priority in enumerate((80, 40)):
            item = Item(source_id=source.id, external_id=f"feedback-{index}",
                        title=f"Real item {index}", url="https://example.com", content="")
            self.session.add(item)
            self.session.flush()
            self.items.append(item)
            self.session.add(Analysis(item_id=item.id, category="AI", summary="Test",
                why_it_matters="Test", importance=1, novelty=1, credibility=1,
                personal_relevance=1, dreamstream_relevance=1, actionability=1,
                priority=priority, tags=[], recommended_action="WATCH", analyzer_version="test"))
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_create_update_and_unique_current_feedback(self):
        item_id = self.items[0].id
        created = self.client.post("/api/v1/feedback", json={"item_id": item_id, "feedback": "useful"})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json(), {"item_id": item_id, "feedback": "useful"})
        first = self.session.scalar(select(Feedback).where(Feedback.item_id == item_id))
        first_id, created_at = first.id, first.created_at

        updated = self.client.post("/api/v1/feedback", json={"item_id": item_id, "feedback": "not_useful"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["feedback"], "not_useful")
        watched = self.client.post("/api/v1/feedback", json={"item_id": item_id, "feedback": "watch"})
        self.assertEqual(watched.status_code, 200)
        self.session.expire_all()
        current = self.session.scalar(select(Feedback).where(Feedback.item_id == item_id))
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Feedback)), 1)
        self.assertEqual((current.id, current.created_at, current.feedback), (first_id, created_at, "watch"))
        self.assertGreaterEqual(current.updated_at, created_at)

    def test_invalid_feedback_and_nonexistent_item_are_rejected(self):
        invalid = self.client.post("/api/v1/feedback", json={"item_id": self.items[0].id, "feedback": "favorite"})
        missing = self.client.post("/api/v1/feedback", json={"item_id": 99999, "feedback": "useful"})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Feedback)), 0)

    def test_today_returns_null_then_persisted_feedback_without_reordering(self):
        before = self.client.get("/api/v1/today")
        self.assertEqual(before.status_code, 200)
        original = before.json()["items"]
        self.assertTrue(all(card["feedback"] is None for card in original))
        self.client.post("/api/v1/feedback", json={"item_id": self.items[1].id, "feedback": "watch"})
        after = self.client.get("/api/v1/today")
        self.assertEqual(after.status_code, 200)
        cards = after.json()["items"]
        self.assertEqual([card["id"] for card in cards], [card["id"] for card in original])
        self.assertEqual(after.json()["stats"], before.json()["stats"])
        for old, new in zip(original, cards):
            self.assertEqual({key: value for key, value in old.items() if key != "feedback"},
                             {key: value for key, value in new.items() if key != "feedback"})
        self.assertEqual(cards[0]["feedback"], None)
        self.assertEqual(cards[1]["feedback"], "watch")

    def test_frontend_preflight_allows_feedback_post(self):
        response = self.client.options("/api/v1/feedback", headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5173")
        self.assertIn("POST", response.headers["access-control-allow-methods"])


if __name__ == "__main__":
    unittest.main()
