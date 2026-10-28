import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.db.models import Item, Source, Analysis
from app.today_rules import today_bucket

class TodayTests(unittest.TestCase):
    def test_must_read_threshold(self):
        self.assertEqual(today_bucket(70, 0), "MUST_READ")
        self.assertEqual(today_bucket(69, 0), "RELEVANT")
    def test_relevant_by_priority(self):
        self.assertEqual(today_bucket(40, 0), "RELEVANT")
    def test_relevant_by_dreamstream(self):
        self.assertEqual(today_bucket(0, 50), "RELEVANT")
    def test_other(self):
        self.assertEqual(today_bucket(39, 49), "OTHER")

    def test_ordering_stats_raw_exclusion_and_ignore_not_filtered(self):
        engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        Base.metadata.create_all(engine)
        session=Session(engine)
        source=Source(name="Test",type="test",category="OTHER")
        session.add(source);session.flush()
        expected=[]
        for n,(priority,relevance,day) in enumerate([(70,10,1),(50,60,1),(50,70,1),(50,70,2),(2,1,1)]):
            item=Item(source_id=source.id,external_id=str(n),title=str(n),url="",content="",published_at=None)
            session.add(item);session.flush();expected.append(item.id)
            session.add(Analysis(item_id=item.id,category="OTHER",summary="Test",why_it_matters="Test",
                importance=1,novelty=1,credibility=1,personal_relevance=1,dreamstream_relevance=relevance,
                actionability=1,priority=priority,tags=[],recommended_action="IGNORE",analyzer_version="test",
                analyzed_at=datetime(2026,1,day)))
        session.add(Item(source_id=source.id,external_id="raw",title="not analyzed",url="",content=""))
        session.commit()
        app.dependency_overrides[get_db]=lambda:session
        try:
            client=TestClient(app)
            response=client.get("/api/v1/today")
            self.assertEqual(response.status_code,200)
            body=response.json()
            self.assertEqual(body["stats"],dict(raw_items=6,analyzed=5,relevant=3,must_read=1))
            self.assertEqual([x["id"] for x in body["items"]],[expected[i] for i in (0,3,2,1,4)])
            self.assertTrue(all(x["published_at"] is None for x in body["items"]))
            self.assertEqual([x["today_bucket"] for x in body["items"]],["MUST_READ","RELEVANT","RELEVANT","RELEVANT","OTHER"])
            client.close()
        finally:
            app.dependency_overrides.clear();session.close();engine.dispose()
