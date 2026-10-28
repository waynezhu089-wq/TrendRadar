import contextlib
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commands import analyze_queue
from app.db.database import Base
from app.db.models import Analysis, Item, Source, Watchlist
from app.intelligence.candidates import MAX_TOTAL, Selection, select_analysis_candidates
from app.llm.base import LLMError


NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
VALID = dict(category="AI", summary="Supported summary", why_it_matters="Possible project relevance",
             importance=50, novelty=50, credibility=60, personal_relevance=50,
             dreamstream_relevance=55, actionability=45, tags=["test"], recommended_action="WATCH")


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def analyze(self, messages):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session, session.begin():
            for name, kind in (("GitHub", "github"), ("RSS", "rss"), ("NewsNow", "newsnow")):
                session.add(Source(name=name, type=kind, category="AI"))

    def tearDown(self):
        self.engine.dispose()

    def add_item(self, kind, title, *, published=None, captured=None, content="", url=None):
        with self.sessions() as session, session.begin():
            source = session.scalar(select(Source).where(Source.type == kind))
            item = Item(source_id=source.id, external_id=f"test-{title}", title=title,
                        url=url or "https://example.com/" + title, content=content, author=None,
                        published_at=published, captured_at=captured or NOW)
            session.add(item)
            session.flush()
            return item.id

    def add_watchlist(self, value, kind="project"):
        with self.sessions() as session, session.begin():
            session.add(Watchlist(type=kind, value=value,
                                  normalized_value=" ".join(value.split()).lower()))

    def analyze_directly(self, item_id):
        with self.sessions() as session, session.begin():
            session.add(Analysis(item_id=item_id, **VALID, priority=51, analyzer_version="test"))

    def test_only_unanalyzed_recent_items_and_null_time_fallback(self):
        done = self.add_item("github", "already", published=NOW)
        old = self.add_item("rss", "old", published=NOW - timedelta(days=8))
        fallback = self.add_item("rss", "fallback", captured=NOW - timedelta(days=1))
        no_gate = self.add_item("newsnow", "ordinary gossip", published=NOW)
        matching = self.add_item("newsnow", "aGeNt workflow", published=NOW,
                                 content="AI automation")
        self.analyze_directly(done)
        selected = select_analysis_candidates(self.sessions, NOW)
        self.assertEqual([c.item_id for c in selected.candidates], [fallback, matching])
        self.assertEqual(selected.candidates[0].effective_time, NOW - timedelta(days=1))
        self.assertEqual(selected.candidates[1].gate_matches, ("AI", "Agent", "workflow"))
        self.assertEqual(selected.stats, {"already_analyzed": 1, "too_old": 1,
                                           "newsnow_no_gate_match": 1, "selected": 2})
        self.assertTrue(all(not candidate.watchlist_hit and candidate.watchlist_matches == ()
                            for candidate in selected.candidates))
        self.assertEqual([candidate.selection_reason for candidate in selected.candidates],
                         ["RSS_RECENT", "NEWSNOW_GATE_MATCH: AI, Agent, workflow"])

    def test_tier_quota_total_limit_and_deterministic_order(self):
        for n in range(4):
            self.add_item("github", f"github-{n}", published=NOW - timedelta(minutes=n))
            self.add_item("rss", f"rss-{n}", published=NOW - timedelta(minutes=n))
            self.add_item("newsnow", f"AI-{n}", published=NOW - timedelta(minutes=n))
        first = select_analysis_candidates(self.sessions, NOW)
        second = select_analysis_candidates(self.sessions, NOW)
        self.assertEqual(first, second)
        self.assertEqual(len(first.candidates), MAX_TOTAL)
        self.assertEqual([c.source_type for c in first.candidates], ["github"] * 3 + ["rss"] * 3)
        self.assertEqual([c.title for c in first.candidates],
                         ["github-0", "github-1", "github-2", "rss-0", "rss-1", "rss-2"])

    def test_newsnow_match_count_order_and_max_two(self):
        rss = self.add_item("rss", "rss", published=NOW)
        one = self.add_item("newsnow", "AI only", published=NOW)
        two = self.add_item("newsnow", "AI Agent", published=NOW - timedelta(days=1))
        self.add_item("newsnow", "AI", published=NOW - timedelta(hours=1))
        selected = select_analysis_candidates(self.sessions, NOW)
        self.assertEqual([c.item_id for c in selected.candidates], [rss, two, one])
        self.assertEqual(sum(c.source_type == "newsnow" for c in selected.candidates), 2)

    def test_dry_run_has_no_provider_calls_or_writes(self):
        self.add_item("rss", "title", published=NOW)
        self.add_watchlist("title")
        tables = ("sources", "items", "analysis", "feedback", "watchlist")
        with self.engine.connect() as conn:
            before = {table: conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all()
                      for table in tables}
        with (patch.object(analyze_queue, "select_analysis_candidates",
                           return_value=select_analysis_candidates(self.sessions, NOW)),
              patch.object(analyze_queue, "OpenAICompatibleClient") as provider,
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(analyze_queue.main(["--dry-run"]), 0)
        provider.assert_not_called()
        with self.engine.connect() as conn:
            for table in tables:
                self.assertEqual(before[table], conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY id").all())
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)

    def test_watchlist_matches_source_title_content_url_case_and_whitespace(self):
        self.add_watchlist("Orion")
        self.add_watchlist("Orion Studio", "topic")
        with self.sessions() as session, session.begin():
            source = session.scalar(select(Source).where(Source.type == "github"))
            source.name = "ORION feed"
        source_hit = self.add_item("github", "plain release", published=NOW)
        title_hit = self.add_item("rss", "orion   STUDIO update", published=NOW)
        content_hit = self.add_item("newsnow", "ordinary content story", published=NOW,
                                    content="News about oRiOn")
        url_hit = self.add_item("newsnow", "ordinary url story", published=NOW - timedelta(minutes=1),
                                url="https://example.com/orion")
        selection = select_analysis_candidates(self.sessions, NOW)
        by_id = {candidate.item_id: candidate for candidate in selection.candidates}
        self.assertEqual(set(by_id), {source_hit, title_hit, content_hit, url_hit})
        self.assertEqual(by_id[source_hit].watchlist_matches, ("Orion",))
        self.assertEqual(by_id[title_hit].watchlist_matches, ("Orion", "Orion Studio"))
        self.assertEqual(by_id[title_hit].watchlist_match_count, 2)
        self.assertEqual(by_id[title_hit].as_report()["watchlist_match_count"], 2)
        self.assertEqual(by_id[content_hit].watchlist_matches, ("Orion",))
        self.assertEqual(by_id[url_hit].watchlist_matches, ("Orion",))
        self.assertTrue(all(candidate.watchlist_hit for candidate in by_id.values()))
        self.assertTrue(all(candidate.gate_matches == () for candidate in
                            (by_id[content_hit], by_id[url_hit])))

    def test_watchlist_hit_precedes_tier_and_newsnow_bypasses_gate(self):
        self.add_watchlist("Orion")
        rss_nonhit = self.add_item("rss", "ordinary newest", published=NOW)
        github_hit = self.add_item("github", "Orion release", published=NOW - timedelta(days=1))
        newsnow_hit = self.add_item("newsnow", "Orion release notes", published=NOW - timedelta(days=2))
        selection = select_analysis_candidates(self.sessions, NOW)
        self.assertEqual([candidate.item_id for candidate in selection.candidates],
                         [github_hit, newsnow_hit, rss_nonhit])
        self.assertEqual(selection.candidates[1].gate_matches, ())
        self.assertEqual(selection.candidates[1].selection_reason, "WATCHLIST_MATCH: Orion")
        self.assertEqual(selection.candidates[2].selection_reason, "RSS_RECENT")

    def test_watchlist_hit_does_not_use_match_count_as_extra_weight(self):
        self.add_watchlist("Orion")
        self.add_watchlist("Studio", "topic")
        one_match = self.add_item("newsnow", "Orion launch", published=NOW)
        two_matches = self.add_item("newsnow", "Orion Studio launch", published=NOW - timedelta(minutes=1))
        selected = select_analysis_candidates(self.sessions, NOW).candidates
        self.assertEqual([candidate.item_id for candidate in selected], [one_match, two_matches])
        self.assertEqual([candidate.watchlist_match_count for candidate in selected], [1, 2])

    def test_watchlist_boost_preserves_quotas_total_and_lookback(self):
        self.add_watchlist("Orion")
        for n in range(4):
            self.add_item("github", f"plain github {n}", published=NOW - timedelta(minutes=n))
            self.add_item("rss", f"plain rss {n}", published=NOW - timedelta(minutes=n))
            self.add_item("newsnow", f"Orion topic {n}", published=NOW - timedelta(minutes=n))
        too_old = self.add_item("newsnow", "Orion old", published=NOW - timedelta(days=8))
        selection = select_analysis_candidates(self.sessions, NOW)
        self.assertEqual(len(selection.candidates), MAX_TOTAL)
        self.assertEqual([candidate.source_type for candidate in selection.candidates],
                         ["newsnow", "newsnow", "github", "github", "github", "rss"])
        self.assertTrue(all(candidate.watchlist_hit for candidate in selection.candidates[:2]))
        self.assertNotIn(too_old, [candidate.item_id for candidate in selection.candidates])
        self.assertEqual(selection.stats["too_old"], 1)

    def test_watchlist_and_gate_reasons_are_both_reported_without_priority_change(self):
        self.add_watchlist("ComfyUI")
        item_id = self.add_item("newsnow", "ComfyUI AI update", published=NOW)
        selection = select_analysis_candidates(self.sessions, NOW)
        candidate = selection.candidates[0]
        self.assertEqual(candidate.item_id, item_id)
        self.assertEqual(candidate.watchlist_matches, ("ComfyUI",))
        self.assertEqual(candidate.gate_matches, ("AI", "ComfyUI"))
        self.assertEqual(candidate.selection_reason,
                         "WATCHLIST_MATCH: ComfyUI | NEWSNOW_GATE_MATCH: AI, ComfyUI")
        with self.sessions() as session:
            self.assertIsNone(session.scalar(select(Analysis).where(Analysis.item_id == item_id)))

    def test_one_failure_isolated_and_repair_bounded(self):
        first = self.add_item("rss", "first", published=NOW)
        second = self.add_item("rss", "second", published=NOW - timedelta(minutes=1))
        selection = select_analysis_candidates(self.sessions, NOW)
        fake = FakeLLM(["bad JSON", "still bad", json.dumps(VALID)])
        report = analyze_queue.run_selected(selection, fake, self.sessions)
        self.assertEqual((report["selected"], report["analyzed"], report["failed"]), (2, 1, 1))
        self.assertEqual(report["repair_count"], 1)
        self.assertEqual(report["total_provider_calls"], 3)
        self.assertEqual([r["item_id"] for r in report["results"]], [first, second])
        self.assertEqual([r["provider_calls"] for r in report["results"]], [2, 1])
        with self.sessions() as session:
            self.assertIsNone(session.scalar(select(Analysis).where(Analysis.item_id == first)))
            self.assertIsNotNone(session.scalar(select(Analysis).where(Analysis.item_id == second)))

    def test_stale_candidate_is_skipped_without_llm(self):
        item_id = self.add_item("github", "new", published=NOW)
        selection = select_analysis_candidates(self.sessions, NOW)
        self.analyze_directly(item_id)
        fake = FakeLLM([])
        report = analyze_queue.run_selected(selection, fake, self.sessions)
        self.assertEqual((report["skipped"], report["total_provider_calls"]), (1, 0))

    def test_provider_failure_aborts_remaining_candidates(self):
        for n in range(3):
            self.add_item("rss", f"provider-{n}", published=NOW - timedelta(minutes=n))
        selection = select_analysis_candidates(self.sessions, NOW)
        fake = FakeLLM([LLMError("Provider HTTP 503"), json.dumps(VALID), json.dumps(VALID)])
        report = analyze_queue.run_selected(selection, fake, self.sessions)
        self.assertTrue(report["provider_unavailable"])
        self.assertEqual((report["failed"], report["aborted_remaining"], report["total_provider_calls"]),
                         (1, 2, 1))
        self.assertEqual(fake.calls, 1)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)

    def test_zero_candidates_never_constructs_provider(self):
        with patch.object(analyze_queue, "OpenAICompatibleClient") as provider:
            _, report = analyze_queue.run_queue_once(Selection((), {}), session_factory=self.sessions)
        self.assertEqual((report["selected"], report["total_provider_calls"]), (0, 0))
        provider.assert_not_called()

    def test_rejects_more_than_six_even_if_caller_passes_them(self):
        for n in range(7):
            self.add_item("github", f"more-{n}", published=NOW)
        candidate = select_analysis_candidates(self.sessions, NOW).candidates[0]
        with self.assertRaises(ValueError):
            analyze_queue.run_selected(Selection((candidate,) * 7, {}), FakeLLM([]), self.sessions)


if __name__ == "__main__":
    unittest.main()
