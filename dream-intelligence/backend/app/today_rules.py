from typing import Literal

TodayBucket = Literal["MUST_READ", "RELEVANT", "OTHER"]
MUST_READ_PRIORITY = 70
RELEVANT_PRIORITY = 40
RELEVANT_DREAMSTREAM = 50

def today_bucket(priority: int, dreamstream_relevance: int) -> TodayBucket:
    if priority >= MUST_READ_PRIORITY:
        return "MUST_READ"
    if priority >= RELEVANT_PRIORITY or dreamstream_relevance >= RELEVANT_DREAMSTREAM:
        return "RELEVANT"
    return "OTHER"
