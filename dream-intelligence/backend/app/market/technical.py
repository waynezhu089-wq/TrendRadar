"""Descriptive calculations over stored daily snapshots; no prediction or signal."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol, Sequence


class DailyValues(Protocol):
    date: object
    close: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: Decimal | None


@dataclass(frozen=True)
class TechnicalState:
    change_pct: Decimal | None
    ma5: Decimal | None
    ma10: Decimal | None
    ma20: Decimal | None
    close_vs_ma5_pct: Decimal | None
    close_vs_ma10_pct: Decimal | None
    close_vs_ma20_pct: Decimal | None
    high_20d: Decimal | None
    low_20d: Decimal | None
    range_position_20d: Decimal | None
    avg_volume_5d: Decimal | None
    volume_ratio_5d: Decimal | None
    sample_days: int


def _round(value: Decimal | None, places: str = "0.0001") -> Decimal | None:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP) if value is not None else None


def _mean(values: Sequence[Decimal | None], count: int) -> Decimal | None:
    if len(values) != count or any(value is None for value in values):
        return None
    return sum(values, Decimal(0)) / count


def _percent(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _round((numerator / denominator - 1) * 100)


def compute_technical_state(snapshots: Sequence[DailyValues]) -> TechnicalState:
    days = sorted(snapshots, key=lambda row: row.date)[-30:]
    latest = days[-1] if days else None
    close = latest.close if latest is not None else None
    previous_close = days[-2].close if len(days) >= 2 else None

    def ma(count: int) -> Decimal | None:
        return _mean([row.close for row in days[-count:]], count)

    ma5, ma10, ma20 = ma(5), ma(10), ma(20)
    last20 = days[-20:]
    full_range = len(last20) == 20 and all(row.high is not None and row.low is not None
                                             for row in last20)
    high_20d = max(row.high for row in last20) if full_range else None
    low_20d = min(row.low for row in last20) if full_range else None
    range_position = None
    if close is not None and high_20d is not None and low_20d is not None and high_20d != low_20d:
        range_position = _round((close - low_20d) / (high_20d - low_20d) * 100)

    previous_five = days[-6:-1] if len(days) >= 6 else []
    average_volume = _mean([row.volume for row in previous_five], 5)
    volume_ratio = None
    if latest is not None and latest.volume is not None and average_volume not in (None, 0):
        volume_ratio = _round(latest.volume / average_volume)

    return TechnicalState(
        change_pct=_percent(close, previous_close),
        ma5=_round(ma5), ma10=_round(ma10), ma20=_round(ma20),
        close_vs_ma5_pct=_percent(close, ma5),
        close_vs_ma10_pct=_percent(close, ma10),
        close_vs_ma20_pct=_percent(close, ma20),
        high_20d=high_20d, low_20d=low_20d,
        range_position_20d=range_position,
        avg_volume_5d=_round(average_volume, "0.01"),
        volume_ratio_5d=volume_ratio,
        sample_days=len(days),
    )
