from app.schemas.analysis import AnalysisOutput

PRIORITY_VERSION = "v0.1-no-hotness"

def calculate_priority(scores: AnalysisOutput) -> int:
    # 20% each relevance score = 40% of their average.
    # Integer arithmetic provides deterministic half-up rounding (not bankers' rounding).
    weighted = (20 * scores.personal_relevance + 20 * scores.dreamstream_relevance
                + 20 * scores.importance + 15 * scores.actionability
                + 10 * scores.novelty + 15 * scores.credibility)
    return max(0, min(100, (weighted + 50) // 100))
