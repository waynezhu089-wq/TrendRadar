"""One replaceable public daily-line provider. Amount is CNY; volume is shares; turnover is percent."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx


@dataclass(frozen=True)
class DailySnapshot:
    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: Decimal | None
    amount: Decimal | None
    turnover: Decimal | None
    source: str


class MarketProvider(Protocol):
    def fetch_daily(self, symbol: str, market: str) -> DailySnapshot: ...
    def fetch_recent_daily(self, symbol: str, market: str, limit: int = 30) -> list[DailySnapshot]: ...


def _number(value: object) -> Decimal | None:
    if value is None or value == "" or value == "--":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid numeric market value") from exc
    if not number.is_finite():
        raise ValueError("Non-finite numeric market value")
    return number


def normalize_tencent_day(row: list[object]) -> DailySnapshot:
    if not isinstance(row, list) or len(row) < 9:
        raise ValueError("Incomplete Tencent daily row")
    trading_date = date.fromisoformat(str(row[0]))
    volume_lots = _number(row[5])
    amount_ten_thousands = _number(row[8])
    return DailySnapshot(
        date=trading_date,
        open=_number(row[1]), close=_number(row[2]),
        high=_number(row[3]), low=_number(row[4]),
        volume=volume_lots * 100 if volume_lots is not None else None,
        amount=amount_ten_thousands * 10000 if amount_ten_thousands is not None else None,
        turnover=_number(row[7]), source="Tencent Finance",
    )


class TencentDailyProvider:
    API_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"

    def fetch_daily(self, symbol: str, market: str) -> DailySnapshot:
        return self.fetch_recent_daily(symbol, market, limit=30)[-1]

    def fetch_recent_daily(self, symbol: str, market: str, limit: int = 30) -> list[DailySnapshot]:
        if not 1 <= limit <= 30:
            raise ValueError("Daily history limit must be between 1 and 30")
        key = f"{market.lower()}{symbol}"
        year = datetime.now(ZoneInfo("Asia/Shanghai")).year
        response = httpx.get(self.API_URL, params={
            "_var": f"kline_day{year}",
            "param": f"{key},day,,,{limit},",
            "r": "0.8205512681390605",
        }, timeout=15)
        response.raise_for_status()
        prefix, separator, payload = response.text.partition("=")
        if separator != "=" or prefix != f"kline_day{year}":
            raise ValueError("Unexpected Tencent daily response")
        data = json.loads(payload)
        if data.get("code") != 0:
            raise ValueError("Tencent daily provider returned an error")
        rows = data.get("data", {}).get(key, {}).get("day", [])
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        available = [normalize_tencent_day(row) for row in rows
                     if isinstance(row, list) and row and date.fromisoformat(str(row[0])) <= today]
        if not available:
            raise ValueError("No available daily snapshot")
        # Keep dates sorted and distinct even if the upstream response changes order.
        by_date = {snapshot.date: snapshot for snapshot in available}
        return [by_date[day] for day in sorted(by_date)[-limit:]]
