from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, field_validator


class MarketWatchlistInput(BaseModel):
    symbol: str
    market: str
    name: str

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

    @field_validator("market")
    @classmethod
    def valid_market(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"SH", "SZ", "BJ"}:
            raise ValueError("Market must be SH, SZ, or BJ")
        return value


class MarketWatchlistOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    market: str
    name: str
    enabled: bool
    created_at: datetime


class MarketItemOutput(BaseModel):
    symbol: str
    market: str
    name: str
    date: date | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None
    turnover: float | None
    source: str | None
    technical: "TechnicalOutput"
    unread_announcement_count: int
    announcements: list["MarketAnnouncementOutput"]


class TechnicalOutput(BaseModel):
    change_pct: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    close_vs_ma5_pct: float | None
    close_vs_ma10_pct: float | None
    close_vs_ma20_pct: float | None
    high_20d: float | None
    low_20d: float | None
    range_position_20d: float | None
    avg_volume_5d: float | None
    volume_ratio_5d: float | None
    sample_days: int


class MarketAnnouncementOutput(BaseModel):
    id: int
    title: str
    url: str
    published_at: datetime | None
    source: str
    read_status: str | None
    text_available: bool
    is_read: bool


class MarketAnnouncementTextOutput(BaseModel):
    id: int
    title: str
    text: str


class MarketAnnouncementReadOutput(BaseModel):
    announcement_id: int
    is_read: bool
    read_at: datetime


class MarketOutput(BaseModel):
    items: list[MarketItemOutput]
