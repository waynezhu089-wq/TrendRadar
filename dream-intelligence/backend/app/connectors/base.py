from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class NormalizedItem:
    source: str
    external_id: str
    title: str
    url: str
    content: str
    author: str | None
    published_at: datetime | None
    captured_at: datetime
    raw_json: dict[str, Any] | None = None

@dataclass
class CollectionResult:
    source: str
    items: list[NormalizedItem]
    received: int = 0
    error: str | None = None

class BaseConnector(ABC):
    @abstractmethod
    def collect(self) -> list[CollectionResult]: ...

    @abstractmethod
    def normalize(self, source: str, raw: dict[str, Any]) -> NormalizedItem: ...

    @abstractmethod
    def health(self) -> bool: ...
