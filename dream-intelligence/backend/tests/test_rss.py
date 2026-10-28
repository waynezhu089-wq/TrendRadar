import json
import unittest
from unittest.mock import patch

import feedparser
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commands.collect_rss import save_collection
from app.connectors.rss import FEEDS, MAX_ITEMS, RSSConnector
from app.db.database import Base, initialize_database
from app.db.models import Analysis, Item, Source


RSS = b'''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<title>Official News</title><link>https://example.com</link><description>Test</description>
<item><guid>release-1</guid><title>Release One</title><link>https://example.com/one#top</link>
<pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate><author>News Team</author>
<content:encoded><![CDATA[<p>Useful <b>release</b>.</p><script>ignore me</script>]]></content:encoded></item>
<item><guid>release-2</guid><title>Release Two</title><link>https://example.com/two</link>
<description><![CDATA[<p>Summary &amp; details</p>]]></description></item>
<item><guid>release-3</guid><title>Release Three</title><link>https://example.com/three</link></item>
<item><guid>release-4</guid><title>Release Four</title><link>https://example.com/four</link></item>
</channel></rss>'''

ATOM = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Official Atom</title>
<entry><id>atom-1</id><title>Atom One</title><link rel="alternate" href="https://example.com/atom#fragment" />
<updated>2026-09-28T09:00:00Z</updated><content type="html">&lt;p&gt;Atom &lt;b&gt;body&lt;/b&gt;&lt;/p&gt;</content></entry>
</feed>'''


class RSSTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.connector = RSSConnector()

    def tearDown(self):
        self.engine.dispose()

    def test_rss_parse_normalize_html_and_missing_date(self):
        entries = feedparser.parse(RSS).entries
        first = self.connector.normalize("OpenAI News", entries[0])
        self.assertEqual(first.title, "Release One")
        self.assertEqual(first.url, "https://example.com/one")
        self.assertEqual(first.content, "Useful release .")
        self.assertNotIn("ignore me", first.content)
        self.assertEqual(first.author, "News Team")
        self.assertIsNotNone(first.published_at)
        self.assertEqual(first.raw_json["id"], "release-1")
        self.assertIsNone(self.connector.normalize("OpenAI News", entries[1]).published_at)
        self.assertEqual(self.connector.normalize("OpenAI News", entries[1]).content, "Summary & details")

    def test_atom_compatibility_and_stable_external_id(self):
        entry = feedparser.parse(ATOM).entries[0]
        first = self.connector.normalize("Google DeepMind Blog", entry)
        second = self.connector.normalize("Google DeepMind Blog", entry)
        self.assertEqual(first.external_id, second.external_id)
        self.assertEqual(first.content, "Atom body")
        self.assertEqual(first.url, "https://example.com/atom")
        self.assertIsNone(first.published_at)
        self.assertNotEqual(first.external_id, self.connector.normalize("Hugging Face Blog", entry).external_id)
        no_guid = {"title": "No ID", "link": "https://example.com/a#one"}
        same_link = {"title": "Renamed", "link": "https://example.com/a#two"}
        self.assertEqual(self.connector.normalize("OpenAI News", no_guid).external_id,
                         self.connector.normalize("OpenAI News", same_link).external_id)
        no_link = {"title": "No link"}
        self.assertEqual(self.connector.normalize("OpenAI News", no_link).external_id,
                         self.connector.normalize("OpenAI News", no_link).external_id)

    def test_max_three_duplicate_insertion_and_raw_json(self):
        with patch.object(self.connector, "_fetch", return_value=feedparser.parse(RSS)):
            results = self.connector.collect()
        self.assertTrue(all(result.received == MAX_ITEMS for result in results))
        first = save_collection(results, self.sessions)
        second = save_collection(results, self.sessions)
        self.assertEqual((first["inserted"], second["inserted"], second["skipped"]), (9, 0, 9))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Source)), 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 9)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)
            source = session.scalar(select(Source).where(Source.name == "OpenAI News"))
            self.assertEqual((source.type, source.category, source.url), ("rss", "AI", FEEDS["OpenAI News"]))
            item = session.scalar(select(Item).where(Item.title == "Release One"))
            self.assertEqual(item.raw_json["id"], "release-1")

    def test_one_feed_failure_does_not_block_others(self):
        def fetch(url):
            if url == FEEDS["Google DeepMind Blog"]:
                raise ValueError("Feed HTTP 503")
            return feedparser.parse(ATOM)
        with patch.object(self.connector, "_fetch", side_effect=fetch):
            report = save_collection(self.connector.collect(), self.sessions)
        self.assertEqual((report["failed"], report["inserted"]), (1, 2))
        self.assertEqual([row["status"] for row in report["sources"]], ["OK", "FAILED", "OK"])

    def test_existing_database_adds_raw_json_without_changing_rows(self):
        Base.metadata.drop_all(self.engine)
        with self.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, source_id INTEGER, external_id VARCHAR UNIQUE, title VARCHAR, url VARCHAR, content TEXT, author VARCHAR, published_at DATETIME, captured_at DATETIME)")
            conn.exec_driver_sql("INSERT INTO items (id, source_id, external_id, title, url, content) VALUES (7, 3, 'old', 'Old item', 'https://example.com', 'Original content')")
        initialize_database(self.engine)
        initialize_database(self.engine)
        with self.engine.connect() as conn:
            names = [column[1] for column in conn.exec_driver_sql("PRAGMA table_info(items)")]
            row = conn.exec_driver_sql("SELECT id, external_id, title, content, raw_json FROM items WHERE id=7").one()
            self.assertIn("raw_json", names)
            self.assertEqual(row, (7, "old", "Old item", "Original content", None))


if __name__ == "__main__":
    unittest.main()
