import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.connectors.newsnow import NewsNowConnector, PLATFORMS
from app.commands.collect_newsnow import save_collection
from app.db.database import Base, initialize_database
from app.db.models import Item, Source, Analysis
from app.db.seed import seed

class NewsNowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.connector = NewsNowConnector()

    def tearDown(self):
        self.engine.dispose()

    def test_request_contract(self):
        import io
        from urllib.parse import urlsplit, parse_qsl
        connector = NewsNowConnector("https://example.com/api/s?custom=yes&id=old&latest=false")
        with patch("app.connectors.newsnow.urlopen", return_value=io.BytesIO(b'{"status":"cache","items":[]}')) as request:
            connector._fetch("zhihu")
        args, kwargs = request.call_args
        req = args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(parse_qsl(urlsplit(req.full_url).query, keep_blank_values=True),
                         [("custom", "yes"), ("id", "zhihu"), ("latest", "")])
        headers = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(headers["accept"], "application/json, text/plain, */*")
        self.assertEqual(headers["cache-control"], "no-cache")
        self.assertIn("zh-CN", headers["accept-language"])
        self.assertTrue(headers["user-agent"].startswith("Mozilla/5.0"))
        self.assertEqual(kwargs["timeout"], 10)

    def test_normalize_unknown_metadata(self):
        item = self.connector.normalize("weibo", {"title": " News ", "url": " https://example.com/a#rank "})
        self.assertEqual(item.title, "News")
        self.assertEqual(item.url, "https://example.com/a")
        self.assertEqual(item.content, "")
        self.assertIsNone(item.author)
        self.assertIsNone(item.published_at)
        self.assertIsNotNone(item.captured_at.tzinfo)

    def test_stable_external_id_and_source_namespace(self):
        a = self.connector.normalize("weibo", {"title": "old", "url": "https://example.com/a#x"})
        b = self.connector.normalize("weibo", {"title": "new", "url": " https://example.com/a "})
        self.assertEqual(a.external_id, b.external_id)
        no_url = {"title": "missing URL"}
        self.assertEqual(self.connector.normalize("weibo", no_url).external_id, self.connector.normalize("weibo", no_url).external_id)
        self.assertNotEqual(self.connector.normalize("weibo", no_url).external_id, self.connector.normalize("zhihu", no_url).external_id)

    def test_duplicate_insertion_does_not_create_analysis(self):
        with patch.object(self.connector, "_fetch", return_value={"items": [{"title": "headline", "url": "https://example.com/a"}]}):
            results = self.connector.collect()
        first = save_collection(results, self.sessions)
        second = save_collection(results, self.sessions)
        self.assertEqual((first["inserted"], second["inserted"], second["skipped"]), (3, 0, 3))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Source)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)

    def test_connector_failure_isolation(self):
        def fetch(source):
            if source == "weibo":
                raise TimeoutError("simulated outage")
            return {"items": [{"title": "headline", "url": "https://example.com/a"}]}
        with patch.object(self.connector, "_fetch", side_effect=fetch):
            report = save_collection(self.connector.collect(), self.sessions)
        self.assertEqual((report["failed"], report["inserted"]), (1, 2))
        self.assertEqual([r["status"] for r in report["sources"]], ["FAILED", "OK", "OK"])

    def test_health_failure(self):
        with patch.object(self.connector, "_fetch", side_effect=TimeoutError()):
            self.assertFalse(self.connector.health())

    def test_legacy_schema_migration_preserves_mock(self):
        from sqlalchemy import MetaData
        Base.metadata.drop_all(self.engine)
        legacy = MetaData()
        for table in Base.metadata.sorted_tables:
            table.to_metadata(legacy)
        legacy.tables["items"].c.author.nullable = False
        legacy.tables["items"].c.published_at.nullable = False
        legacy.create_all(self.engine)
        with self.sessions() as session:
            seed(session)
        initialize_database(self.engine)
        initialize_database(self.engine)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 1)
            self.assertEqual(session.scalar(select(Item)).title, "MiniMax releases new video capability")
        with self.engine.connect() as conn:
            cols = conn.exec_driver_sql("PRAGMA table_info(items)").all()
            self.assertTrue(all(not c[3] for c in cols if c[1] in ("author", "published_at")))

    def test_initialize_does_not_seed(self):
        initialize_database(self.engine)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 0)

    def test_seed_module_execution_does_not_insert_mock(self):
        import runpy
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*found in sys.modules.*", category=RuntimeWarning)
            runpy.run_module("app.db.seed", run_name="__main__")
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 0)

if __name__ == "__main__":
    unittest.main()
