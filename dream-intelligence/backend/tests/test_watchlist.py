import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import Feedback, Item
from app.db.seed import seed
from app.main import app


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        seed(self.session)
        item = self.session.scalar(select(Item))
        self.session.add(Feedback(item_id=item.id, feedback="watch"))
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        self.before = self._existing_rows()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def _existing_rows(self):
        with self.engine.connect() as connection:
            return {table: connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all()
                    for table in ("sources", "items", "analysis", "feedback")}

    def test_create_list_delete_duplicate_and_existing_data_isolation(self):
        self.assertEqual(self.client.get("/api/v1/watchlist").json(), [])
        first = self.client.post("/api/v1/watchlist", json={"type": "project", "value": "ComfyUI"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual((first.json()["type"], first.json()["value"]), ("project", "ComfyUI"))
        self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "project", "value": " comfyui "}).status_code, 409)
        self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "project", "value": "COMFYUI"}).status_code, 409)
        same_value_other_type = self.client.post("/api/v1/watchlist", json={"type": "topic", "value": "ComfyUI"})
        self.assertEqual(same_value_other_type.status_code, 201)
        self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "project", "value": "browser-use"}).status_code, 201)
        listed = self.client.get("/api/v1/watchlist")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([(row["type"], row["value"]) for row in listed.json()],
                         [("project", "ComfyUI"), ("project", "browser-use"), ("topic", "ComfyUI")])
        self.assertEqual(self.client.delete(f"/api/v1/watchlist/{same_value_other_type.json()['id']}").status_code, 204)
        self.assertEqual(len(self.client.get("/api/v1/watchlist").json()), 2)
        self.assertEqual(self._existing_rows(), self.before)

    def test_validation_and_missing_delete(self):
        self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "other", "value": "OpenAI"}).status_code, 422)
        for blank in ("", "  \t  "):
            self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "company", "value": blank}).status_code, 422)
        self.assertEqual(self.client.delete("/api/v1/watchlist/99999").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/watchlist").json(), [])
        self.assertEqual(self._existing_rows(), self.before)

    def test_normalization_collapses_whitespace_and_get_order_is_stable(self):
        for kind, value in (("topic", "AI video"), ("project", "First"),
                            ("company", "OpenAI"), ("project", "Second"),
                            ("keyword", "MiniMax"), ("model", "Seedance")):
            self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": kind, "value": value}).status_code, 201)
        self.assertEqual(self.client.post("/api/v1/watchlist", json={"type": "topic", "value": " ai  VIDEO "}).status_code, 409)
        expected = [("company", "OpenAI"), ("keyword", "MiniMax"), ("model", "Seedance"),
                    ("project", "First"), ("project", "Second"), ("topic", "AI video")]
        for _ in range(2):
            self.assertEqual([(row["type"], row["value"]) for row in self.client.get("/api/v1/watchlist").json()], expected)

    def test_frontend_preflight_allows_post_and_delete(self):
        for method in ("POST", "DELETE"):
            response = self.client.options("/api/v1/watchlist", headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            })
            self.assertEqual(response.status_code, 200)
            self.assertIn(method, response.headers["access-control-allow-methods"])

    def test_watchlist_crud_does_not_change_today_or_priority(self):
        before = self.client.get("/api/v1/today")
        self.assertEqual(before.status_code, 200)
        created = self.client.post("/api/v1/watchlist", json={"type": "project", "value": "ComfyUI"})
        self.assertEqual(created.status_code, 201)
        after_create = self.client.get("/api/v1/today")
        self.assertEqual(after_create.json(), before.json())
        self.assertEqual(self.client.delete(f"/api/v1/watchlist/{created.json()['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/today").json(), before.json())


if __name__ == "__main__":
    unittest.main()
