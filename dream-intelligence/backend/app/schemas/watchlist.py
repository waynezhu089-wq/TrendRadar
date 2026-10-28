from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

WatchlistType = Literal["keyword", "project", "company", "model", "topic"]


class WatchlistInput(BaseModel):
    type: WatchlistType
    value: str

    @field_validator("value")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class WatchlistOutput(BaseModel):
    id: int
    type: WatchlistType
    value: str
    created_at: datetime
