import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.database import Base
from app.db.models import Source, Item, Analysis
from app.db.seed import seed
from app.schemas.analysis import AnalysisOutput
from app.intelligence.priority import calculate_priority, PRIORITY_VERSION
from app.intelligence.analyzer import Analyzer, ANALYZER_VERSION
from app.llm.base import LLMError
from app.llm.openai_compatible import LLMSettings, OpenAICompatibleClient, ConfigurationError
from app.commands.analyze_pending import main

VALID = dict(category="AI_VIDEO", summary="Test summary", why_it_matters="Test relevance",
    importance=80, novelty=70, credibility=85, personal_relevance=75,
    dreamstream_relevance=90, actionability=80, tags=["Video"], recommended_action="READ")
SCORES = ("importance", "novelty", "credibility", "personal_relevance", "dreamstream_relevance", "actionability")

# Test-only provider: never imported by production modules or commands.
class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0
    def analyze(self, messages):
        self.calls += 1
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result

class SchemaPriorityTests(unittest.TestCase):
    def test_priority_formula_half_up(self):
        self.assertEqual(PRIORITY_VERSION, "v0.1-no-hotness")
        self.assertEqual(calculate_priority(AnalysisOutput(**VALID)), 81)
        for score in (0, 100):
            self.assertEqual(calculate_priority(AnalysisOutput(**(VALID | dict.fromkeys(SCORES, score)))), score)
        self.assertEqual(calculate_priority(AnalysisOutput(**(VALID | dict.fromkeys(SCORES, 0) | {"novelty": 5}))), 1)

    def test_scores_strict_validation(self):
        for name in SCORES:
            for bad in (-1, 101, 80.5, "80", True, None):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValidationError):
                    AnalysisOutput(**(VALID | {name: bad}))

    def test_valid_json_and_model_priority_ignored(self):
        output = AnalysisOutput.model_validate_json(json.dumps(VALID | {"priority": 1}))
        self.assertNotIn("priority", output.model_dump())
        self.assertEqual(calculate_priority(output), 81)

    def test_invalid_json_and_enums(self):
        for raw in ("not JSON", "```json\n{}\n```", "{}", "[]",
                    json.dumps(VALID | {"category": "SPORT"}),
                    json.dumps(VALID | {"recommended_action": "BUY"})):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValidationError):
                AnalysisOutput.model_validate_json(raw)

class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            seed(session)
            source = Source(name="Test raw source", type="newsnow", category="CHINA_TRENDS")
            session.add(source)
            session.flush()
            for n in range(3):
                session.add(Item(source_id=source.id, external_id=f"raw-{n}", title=f"Raw title {n}",
                    url=f"https://example.com/{n}", content="", author=None, published_at=None))
            session.commit()
            self.ids = list(session.scalars(select(Item.id).where(Item.source_id == source.id).order_by(Item.id)))
        with self.engine.connect() as conn:
            self.before = conn.exec_driver_sql("SELECT * FROM items ORDER BY id").all()

    def tearDown(self):
        self.engine.dispose()

    def test_fake_end_to_end_no_raw_mutation_and_repeated_skip(self):
        fake = FakeLLM([json.dumps(VALID | {"priority": 100})] * 3)
        analyzer = Analyzer(fake, self.sessions, profile="Test project")
        self.assertEqual(analyzer.pending_ids(), self.ids)
        results = analyzer.analyze_pending(3)
        self.assertEqual([r.status for r in results], ["OK"] * 3)
        self.assertEqual([r.priority for r in results], [81] * 3)
        for item_id in self.ids:
            self.assertEqual(analyzer.analyze_one(item_id).status, "SKIP")
        self.assertEqual(analyzer.analyze_pending(3), [])
        self.assertEqual(fake.calls, 3)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 4)
            result = session.scalar(select(Analysis).where(Analysis.item_id == self.ids[0]))
            self.assertEqual(result.analyzer_version, ANALYZER_VERSION)
            self.assertEqual(result.tags, ["Video"])
        with self.engine.connect() as conn:
            self.assertEqual(self.before, conn.exec_driver_sql("SELECT * FROM items ORDER BY id").all())

    def test_single_item_failures_preserve_later_success(self):
        fake = FakeLLM(["invalid JSON", "still invalid", LLMError("private response must not be logged"), json.dumps(VALID)])
        results = Analyzer(fake, self.sessions, profile="Test").analyze_pending(3)
        self.assertEqual([r.status for r in results], ["FAIL", "FAIL", "OK"])
        self.assertEqual(fake.calls, 4)
        self.assertEqual(results[0].error_type, "JSON_PARSE_ERROR")
        self.assertTrue(results[0].repair_invoked)
        self.assertEqual(results[1].error_type, "LLM_REQUEST_ERROR")
        self.assertFalse(results[1].repair_invoked)
        self.assertNotIn("private response", str(results))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 2)

    def test_invalid_score_not_written(self):
        results = Analyzer(FakeLLM([json.dumps(VALID | {"importance": 200}),
                                    json.dumps(VALID | {"importance": 200})]), self.sessions, profile="Test").analyze_pending(1)
        self.assertEqual(results[0].status, "FAIL")
        self.assertEqual(results[0].error_type, "SCHEMA_VALIDATION_ERROR")
        self.assertIn("importance", results[0].reason)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 1)

    def test_valid_json_does_not_repair(self):
        fake = FakeLLM([json.dumps(VALID)])
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual(result.status, "OK")
        self.assertFalse(result.repair_invoked)
        self.assertEqual(fake.calls, 1)

    def test_invalid_json_repairs_once_without_mutating_raw(self):
        fake = FakeLLM(["{broken", json.dumps(VALID)])
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual((result.status, result.initial_error_type, result.repair_invoked),
                         ("OK", "JSON_PARSE_ERROR", True))
        self.assertEqual(fake.calls, 2)
        with self.engine.connect() as conn:
            self.assertEqual(self.before, conn.exec_driver_sql("SELECT * FROM items ORDER BY id").all())

    def test_schema_invalid_repairs_once(self):
        fake = FakeLLM([json.dumps(VALID | {"importance": "80"}), json.dumps(VALID)])
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual((result.status, result.initial_error_type, result.repair_invoked),
                         ("OK", "SCHEMA_VALIDATION_ERROR", True))
        self.assertEqual(fake.calls, 2)

    def test_repair_failure_stops_after_one_and_redacts_secrets(self):
        secret = "test-secret-must-not-appear"
        fake = FakeLLM(["{broken " + secret, "{still broken " + secret])
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.error_type, "JSON_PARSE_ERROR")
        self.assertIn("line 1, column", result.reason)
        self.assertNotIn(secret, str(result))
        self.assertEqual(fake.calls, 2)

    def test_schema_diagnostic_omits_secret_input(self):
        secret = "test-secret-must-not-appear"
        fake = FakeLLM([json.dumps(VALID | {"importance": secret})] * 2)
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual(result.error_type, "SCHEMA_VALIDATION_ERROR")
        self.assertIn("importance", result.reason)
        self.assertNotIn(secret, str(result))

    def test_provider_http_status_is_reported_without_response_body(self):
        fake = FakeLLM([LLMError("Provider HTTP 422")])
        result = Analyzer(fake, self.sessions, profile="Test").analyze_one(self.ids[0])
        self.assertEqual((result.error_type, result.reason, result.repair_invoked),
                         ("LLM_REQUEST_ERROR", "Provider HTTP 422", False))
        self.assertEqual(fake.calls, 1)

    def test_mock_skipped_and_limit_bounded(self):
        fake = FakeLLM([])
        analyzer = Analyzer(fake, self.sessions, profile="Test")
        self.assertEqual(analyzer.analyze_one(1).status, "SKIP")
        self.assertEqual(fake.calls, 0)
        self.assertEqual(len(analyzer.pending_ids(1)), 1)
        for limit in (0, 21, True):
            with self.assertRaises(ValueError):
                analyzer.pending_ids(limit)

class ProviderTests(unittest.TestCase):
    def test_missing_environment_fails_without_database_or_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch("app.commands.analyze_pending.initialize_database") as db:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([]), 2)
            self.assertIn("REAL_LLM_NOT_VALIDATED", output.getvalue())
            db.assert_not_called()

    def test_transport_contract_without_network_or_key(self):
        client = OpenAICompatibleClient(LLMSettings("https://example.com/v1", "", "test-model", 15))
        raw = json.dumps({"choices": [{"message": {"content": json.dumps(VALID)}, "finish_reason": "stop"}]}).encode()
        with patch.object(client.opener, "open", return_value=io.BytesIO(raw)) as request:
            self.assertEqual(json.loads(client.analyze([{"role": "user", "content": "Test"}])), VALID)
        args, kwargs = request.call_args
        self.assertEqual(args[0].full_url, "https://example.com/v1/chat/completions")
        self.assertEqual(args[0].get_method(), "POST")
        payload = json.loads(args[0].data)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(kwargs["timeout"], 15)

    def test_provider_error_redacted(self):
        client = OpenAICompatibleClient(LLMSettings("https://example.com/v1", "", "test-model"))
        error = HTTPError("https://example.com/private", 401, "private body", {}, None)
        with patch.object(client.opener, "open", side_effect=error), self.assertRaises(LLMError) as caught:
            client.analyze([])
        self.assertEqual(str(caught.exception), "Provider HTTP 401")

if __name__ == "__main__":
    unittest.main()
