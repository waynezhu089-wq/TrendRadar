import argparse
from app.db.database import initialize_database
from app.intelligence.analyzer import Analyzer
from app.llm.openai_compatible import LLMSettings, ConfigurationError, OpenAICompatibleClient

def bounded_limit(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("limit must be an integer") from None
    if not 1 <= result <= 20:
        raise argparse.ArgumentTypeError("limit must be 1..20")
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze a small batch of pending raw items")
    parser.add_argument("--limit", type=bounded_limit, default=5)
    args = parser.parse_args(argv)
    try:
        settings = LLMSettings.from_env()
    except ConfigurationError as error:
        print(str(error))
        return 2
    initialize_database()
    analyzer = Analyzer(OpenAICompatibleClient(settings))
    ids = analyzer.pending_ids(args.limit)
    print(f"Pending: {len(ids)}")
    results = []
    for position, item_id in enumerate(ids, 1):
        result = analyzer.analyze_one(item_id)
        results.append(result)
        detail = f"priority={result.priority} category={result.category}" if result.status == "OK" else result.reason
        print(f"[{position}] {result.status} item={item_id} {detail}")
    for label, status in (("Analyzed", "OK"), ("Skipped", "SKIP"), ("Failed", "FAIL")):
        print(f"{label}: {sum(r.status == status for r in results)}")
    return 1 if any(r.status == "FAIL" for r in results) else 0

if __name__ == "__main__":
    raise SystemExit(main())
