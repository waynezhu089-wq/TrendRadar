from dataclasses import dataclass
import json
import re
from json import JSONDecodeError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.database import SessionLocal
from app.db.models import Item, Source, Analysis
from app.llm.base import LLMClient, LLMError
from app.schemas.analysis import AnalysisOutput
from .priority import calculate_priority
from .prompts import PROFILE_PATH, messages_for, repair_messages_for

ANALYZER_VERSION = "dsih-analyzer-v0.1.1"
EXCLUDED_SOURCE_TYPES = ("mock", "custom_web", "mediacrawler")

@dataclass(frozen=True)
class ItemResult:
    item_id: int
    status: str
    priority: int | None = None
    category: str | None = None
    reason: str = ""
    error_type: str | None = None
    initial_error_type: str | None = None
    repair_invoked: bool = False


def validate_response(raw: str) -> tuple[AnalysisOutput | None, str | None, str]:
    try:
        value = json.loads(raw)
    except (JSONDecodeError, TypeError) as error:
        if isinstance(error, JSONDecodeError):
            return None, "JSON_PARSE_ERROR", f"JSONDecodeError at line {error.lineno}, column {error.colno}, position {error.pos}"
        return None, "JSON_PARSE_ERROR", "Response is not JSON text"
    try:
        return AnalysisOutput.model_validate(value), None, ""
    except ValidationError as error:
        # Never include model input or context in diagnostics; both may contain secrets.
        details = error.errors(include_input=False, include_context=False, include_url=False)
        summary = "; ".join(f"{'.'.join(map(str, detail['loc'])) or 'root'}: {detail['type']} ({detail['msg']})"
                            for detail in details[:3])
        if len(details) > 3:
            summary += f"; {len(details) - 3} more validation errors"
        return None, "SCHEMA_VALIDATION_ERROR", summary


def provider_error_summary(error: Exception) -> str:
    # The production client emits a safe status string; other exception text is untrusted.
    detail = str(error)
    return detail if isinstance(error, LLMError) and re.fullmatch(r"Provider HTTP [45][0-9]{2}", detail) else "Provider request failed"

class Analyzer:
    def __init__(self, client: LLMClient, session_factory=SessionLocal, profile: str | None = None):
        self.client = client
        self.sessions = session_factory
        self.profile = profile if profile is not None else PROFILE_PATH.read_text(encoding="utf-8")

    def pending_ids(self, limit: int = 5) -> list[int]:
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be 1..20")
        with self.sessions() as session:
            return list(session.scalars(select(Item.id).join(Source, Source.id == Item.source_id)
                .where(Source.type.not_in(EXCLUDED_SOURCE_TYPES),
                       ~select(Analysis.id).where(Analysis.item_id == Item.id).exists())
                .order_by(Item.id).limit(limit)))

    def analyze_one(self, item_id: int) -> ItemResult:
        with self.sessions() as session:
            item = session.get(Item, item_id)
            if item is None:
                return ItemResult(item_id, "FAIL", reason="item missing")
            if session.scalar(select(Analysis.id).where(Analysis.item_id == item_id)) is not None:
                return ItemResult(item_id, "SKIP", reason="already analyzed")
            if session.get(Source, item.source_id).type in EXCLUDED_SOURCE_TYPES:
                return ItemResult(item_id, "SKIP", reason="source is outside global analysis")
            messages = messages_for(item, self.profile)
        # No DB write transaction is held during the external request.
        try:
            raw = self.client.analyze(messages)
        except Exception as error:
            return ItemResult(item_id, "FAIL", reason=provider_error_summary(error), error_type="LLM_REQUEST_ERROR")
        output, error_type, reason = validate_response(raw)
        initial_error_type = error_type
        repaired = False
        if error_type is not None:
            repaired = True
            try:
                repaired_raw = self.client.analyze(repair_messages_for(messages, raw, reason))
            except Exception as error:
                return ItemResult(item_id, "FAIL", reason=provider_error_summary(error),
                                  error_type="LLM_REQUEST_ERROR", initial_error_type=initial_error_type,
                                  repair_invoked=True)
            output, error_type, reason = validate_response(repaired_raw)
            if error_type is not None:
                return ItemResult(item_id, "FAIL", reason=reason, error_type=error_type,
                                  initial_error_type=initial_error_type, repair_invoked=True)
        assert output is not None
        priority = calculate_priority(output)
        try:
            with self.sessions() as session, session.begin():
                if session.scalar(select(Analysis.id).where(Analysis.item_id == item_id)) is not None:
                    return ItemResult(item_id, "SKIP", reason="already analyzed")
                session.add(Analysis(item_id=item_id, **output.model_dump(), priority=priority,
                    analyzer_version=ANALYZER_VERSION))
        except IntegrityError:
            with self.sessions() as session:
                if session.scalar(select(Analysis.id).where(Analysis.item_id == item_id)) is not None:
                    return ItemResult(item_id, "SKIP", reason="already analyzed")
            return ItemResult(item_id, "FAIL", reason="database constraint failed")
        except Exception:
            return ItemResult(item_id, "FAIL", reason="database write failed")
        return ItemResult(item_id, "OK", priority=priority, category=output.category,
                          initial_error_type=initial_error_type, repair_invoked=repaired)

    def analyze_pending(self, limit: int = 5) -> list[ItemResult]:
        return [self.analyze_one(item_id) for item_id in self.pending_ids(limit)]
