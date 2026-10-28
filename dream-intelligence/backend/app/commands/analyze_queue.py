import argparse
import json

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Analysis
from app.intelligence.analyzer import Analyzer
from app.intelligence.candidates import MAX_TOTAL, Selection, select_analysis_candidates
from app.llm.openai_compatible import ConfigurationError, LLMSettings, OpenAICompatibleClient


class BoundedClient:
    def __init__(self, client):
        self.client = client
        self.calls = 0
        self.item_calls = 0

    def begin_item(self):
        self.item_calls = 0

    def analyze(self, messages):
        if self.item_calls >= 2 or self.calls >= MAX_TOTAL * 2:
            raise RuntimeError("Provider call budget exceeded")
        self.calls += 1
        self.item_calls += 1
        return self.client.analyze(messages)


def run_selected(selection: Selection, client, session_factory=SessionLocal):
    if len(selection.candidates) > MAX_TOTAL:
        raise ValueError("Candidate limit exceeded")
    bounded = BoundedClient(client)
    analyzer = Analyzer(bounded, session_factory)
    results = []
    provider_unavailable = False
    for candidate in selection.candidates:
        bounded.begin_item()
        try:
            result = analyzer.analyze_one(candidate.item_id)
            row = {"item_id": candidate.item_id, "result": result.status,
                   "category": result.category, "priority": result.priority,
                   "error_type": result.error_type, "reason": result.reason,
                   "repair_used": result.repair_invoked}
        except Exception:
            row = {"item_id": candidate.item_id, "result": "FAIL", "category": None,
                   "priority": None, "error_type": "ANALYSIS_ERROR",
                   "reason": "Analysis failed", "repair_used": False}
        row["provider_calls"] = bounded.item_calls
        row["dreamstream_relevance"] = None
        row["recommended_action"] = None
        if row["result"] == "OK":
            with session_factory() as session:
                analysis = session.scalar(select(Analysis).where(Analysis.item_id == candidate.item_id))
                row["dreamstream_relevance"] = analysis.dreamstream_relevance
                row["recommended_action"] = analysis.recommended_action
        results.append(row)
        if row["error_type"] == "LLM_REQUEST_ERROR":
            provider_unavailable = True
            break
    return {"selected": len(selection.candidates),
            "analyzed": sum(row["result"] == "OK" for row in results),
            "skipped": sum(row["result"] == "SKIP" for row in results),
            "failed": sum(row["result"] == "FAIL" for row in results),
            "normal_calls": sum(row["provider_calls"] - int(row["repair_used"]) for row in results),
            "repair_count": sum(row["repair_used"] for row in results),
            "total_provider_calls": bounded.calls,
            "provider_unavailable": provider_unavailable,
            "aborted_remaining": len(selection.candidates) - len(results),
            "results": results}


def run_queue_once(selection: Selection | None = None, client=None, session_factory=SessionLocal):
    selection = selection if selection is not None else select_analysis_candidates(session_factory)
    if not selection.candidates:
        return selection, {"selected": 0, "analyzed": 0, "skipped": 0, "failed": 0,
                           "normal_calls": 0, "repair_count": 0, "total_provider_calls": 0,
                           "provider_unavailable": False, "aborted_remaining": 0, "results": []}
    if client is None:
        client = OpenAICompatibleClient(LLMSettings.from_env())
    return selection, run_selected(selection, client, session_factory)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview or analyze a bounded raw item queue")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    selection = select_analysis_candidates()
    print(json.dumps({"mode": "dry-run" if args.dry_run else "once", **selection.as_report()},
                     ensure_ascii=False), flush=True)
    if args.dry_run or not selection.candidates:
        return 0
    try:
        _, report = run_queue_once(selection)
    except ConfigurationError as error:
        print(json.dumps({"error": str(error)}))
        return 2
    for row in report["results"]:
        print(json.dumps({"kind": "analysis", **row}, ensure_ascii=False), flush=True)
    print(json.dumps({"kind": "summary", **{key: value for key, value in report.items()
                                            if key != "results"}}, ensure_ascii=False), flush=True)
    return 1 if report["failed"] or report["provider_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
