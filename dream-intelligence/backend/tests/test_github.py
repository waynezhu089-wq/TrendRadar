import io
import os
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.connectors.github import GitHubConnector,GitHubError,REPOSITORIES
from app.commands.collect_github import save_collection
from app.db.database import Base
from app.db.models import Item,Analysis,Source

RELEASE={"kind":"release","data":{"id":123,"tag_name":"v1","name":"Version 1","html_url":"https://github.com/example/release/1","body":"Release notes","author":{"login":"author"},"published_at":"2026-09-28T00:00:00Z"}}
COMMIT={"kind":"commit","data":{"sha":"abc123","html_url":"https://github.com/example/commit/abc123","commit":{"message":"First line\nMore detail","author":{"name":"Writer","date":"2026-09-28T00:00:00Z"}}}}
REPO=next(iter(REPOSITORIES))

class GitHubTests(unittest.TestCase):
    def test_release_normalize(self):
        item=GitHubConnector(token="").normalize(REPO,RELEASE)
        self.assertEqual(item.title,REPO+" — Version 1")
        self.assertEqual(item.content,"Release notes")
        self.assertEqual(item.author,"author")
        self.assertIsNotNone(item.published_at.tzinfo)
    def test_commit_fallback_normalize(self):
        connector=GitHubConnector(token="")
        with patch.object(connector,"_request",side_effect=[GitHubError(404),[COMMIT["data"]]]) as request:
            raw=connector._fetch(REPO)
        self.assertEqual(request.call_args.args[0],f"/repos/{REPO}/commits?per_page=1")
        item=connector.normalize(REPO,raw)
        self.assertEqual(item.title,"First line")
        self.assertEqual(item.author,"Writer")
        self.assertTrue(item.external_id.endswith(":commit:abc123"))
    def test_stable_external_id(self):
        connector=GitHubConnector(token="")
        a=connector.normalize(REPO,RELEASE)
        b=connector.normalize(REPO,{"kind":"release","data":RELEASE["data"]|{"name":"Renamed"}})
        self.assertEqual(a.external_id,b.external_id)
    def test_duplicates_and_failure_isolation(self):
        engine=create_engine("sqlite://",poolclass=StaticPool,connect_args={"check_same_thread":False})
        Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine)
        connector=GitHubConnector(token="")
        try:
            with patch.object(connector,"_fetch",side_effect=[RELEASE,RuntimeError("outage"),RELEASE]):
                results=connector.collect()
            first=save_collection(results,sessions);second=save_collection(results,sessions)
            self.assertEqual((first["inserted"],first["failed"]),(2,1))
            self.assertEqual((second["inserted"],second["skipped"]),(0,2))
            with sessions() as s:
                self.assertEqual(s.scalar(select(func.count()).select_from(Item)),2)
                self.assertEqual(s.scalar(select(func.count()).select_from(Source)),2)
                self.assertEqual(s.scalar(select(func.count()).select_from(Analysis)),0)
        finally:engine.dispose()
    def test_optional_token(self):
        for token in ("", "test-only-placeholder"):
            with patch.dict(os.environ,{"GITHUB_TOKEN":token}):
                connector=GitHubConnector()
            with patch.object(connector.opener,"open",return_value=io.BytesIO(b'{}')) as request:
                connector._request("/rate_limit")
            headers={k.lower():v for k,v in request.call_args.args[0].header_items()}
            self.assertEqual("authorization" in headers,bool(token))
    def test_rate_limit_stops_remaining_requests(self):
        connector=GitHubConnector(token="")
        with patch.object(connector,"_fetch",side_effect=GitHubError(429,True)) as fetch:
            results=connector.collect()
        self.assertEqual(fetch.call_count,1)
        self.assertTrue(all(r.error for r in results))
