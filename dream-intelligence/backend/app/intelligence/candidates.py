from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Analysis, Item, Source, Watchlist


LOOKBACK_DAYS = 7
MAX_TOTAL = 6
SOURCE_QUOTAS = {"github": 3, "rss": 3, "newsnow": 2}
ANALYSIS_GATE_TERMS = (
    "AI", "人工智能", "大模型", "LLM", "模型", "视频生成", "图生视频",
    "ComfyUI", "MiniMax", "Seedance", "Agent", "智能体", "MCP",
    "workflow", "工作流", "browser", "浏览器自动化", "自动化", "开源", "GitHub",
)


@dataclass(frozen=True)
class Candidate:
    item_id: int
    source: str
    source_type: str
    title: str
    effective_time: datetime
    tier: int
    gate_matches: tuple[str, ...]
    watchlist_matches: tuple[str, ...]
    watchlist_hit: bool
    selection_reason: str

    @property
    def watchlist_match_count(self) -> int:
        return len(self.watchlist_matches)

    def as_report(self):
        return {**asdict(self), "effective_time": self.effective_time.isoformat(),
                "gate_matches": list(self.gate_matches),
                "watchlist_matches": list(self.watchlist_matches),
                "watchlist_match_count": self.watchlist_match_count}


@dataclass(frozen=True)
class Selection:
    candidates: tuple[Candidate, ...]
    stats: dict[str, int]

    def as_report(self):
        return {"candidate_count": len(self.candidates),
                "candidates": [candidate.as_report() for candidate in self.candidates],
                "excluded": self.stats}


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalize_match_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def candidate_order(candidate: Candidate):
    return (-int(candidate.watchlist_hit), candidate.tier,
            -len(candidate.gate_matches) if candidate.source_type == "newsnow" else 0,
            -candidate.effective_time.timestamp(), candidate.item_id)


def select_analysis_candidates(session_factory=SessionLocal, now: datetime | None = None) -> Selection:
    now = as_utc(now or datetime.now(timezone.utc))
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    stats = {"already_analyzed": 0, "too_old": 0, "newsnow_no_gate_match": 0, "selected": 0}
    eligible: list[Candidate] = []
    with session_factory() as session:
        watchlist = session.scalars(select(Watchlist).order_by(
            Watchlist.type, Watchlist.created_at, Watchlist.id)).all()
        rows = session.execute(select(Item, Source, Analysis.id).join(Source, Source.id == Item.source_id)
                               .outerjoin(Analysis, Analysis.item_id == Item.id).order_by(Item.id)).all()
        for item, source, analysis_id in rows:
            if analysis_id is not None:
                stats["already_analyzed"] += 1
                continue
            effective = as_utc(item.published_at or item.captured_at)
            if effective < cutoff:
                stats["too_old"] += 1
                continue
            source_type = source.type.lower()
            if source_type == "hotboard":
                source_type = "newsnow"
            if source_type not in SOURCE_QUOTAS:
                continue
            match_text = normalize_match_text(" ".join((source.name, item.title,
                                                       item.content or "", item.url)))
            watchlist_matches = tuple(entry.value for entry in watchlist
                                      if normalize_match_text(entry.normalized_value) in match_text)
            matches = tuple(term for term in ANALYSIS_GATE_TERMS
                            if term.casefold() in (item.title + " " + (item.content or "")).casefold()) \
                if source_type == "newsnow" else ()
            if source_type == "newsnow" and not matches and not watchlist_matches:
                stats["newsnow_no_gate_match"] += 1
                continue
            tier = {"github": 1, "rss": 2, "newsnow": 3}[source_type]
            reasons = []
            if watchlist_matches:
                reasons.append("WATCHLIST_MATCH: " + ", ".join(watchlist_matches))
            if matches:
                reasons.append("NEWSNOW_GATE_MATCH: " + ", ".join(matches))
            elif source_type != "newsnow":
                reasons.append(source_type.upper() + "_RECENT")
            eligible.append(Candidate(item.id, source.name, source_type, item.title,
                                      effective, tier, matches, watchlist_matches,
                                      bool(watchlist_matches), " | ".join(reasons)))
    eligible.sort(key=candidate_order)
    selected = []
    selected_by_type = {source_type: 0 for source_type in SOURCE_QUOTAS}
    for candidate in eligible:
        if len(selected) >= MAX_TOTAL:
            break
        if selected_by_type[candidate.source_type] >= SOURCE_QUOTAS[candidate.source_type]:
            continue
        selected.append(candidate)
        selected_by_type[candidate.source_type] += 1
    stats["selected"] = len(selected)
    return Selection(tuple(selected), stats)
