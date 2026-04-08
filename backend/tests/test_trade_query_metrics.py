"""trade_query_metrics：筛选与指标纯逻辑测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.trade_query_metrics import (
    calculate_metrics_from_trade_rows,
    yearly_aggregate_from_rows,
)


@dataclass
class _FakeRow:
    trade_type: str
    return_rate: float | None
    buy_date: date


def test_calculate_metrics_empty_closed():
    rows: list[_FakeRow] = []
    m = calculate_metrics_from_trade_rows(rows)
    assert m.total_trades == 0
    assert m.matched_count == 0


def test_calculate_metrics_only_unclosed():
    rows = [
        _FakeRow("unclosed", None, date(2024, 1, 2)),
    ]
    m = calculate_metrics_from_trade_rows(rows)
    assert m.total_trades == 0
    assert m.matched_count == 1
    assert m.unclosed_count == 1


def test_yearly_aggregate_two_years():
    rows = [
        _FakeRow("closed", 0.01, date(2023, 6, 1)),
        _FakeRow("closed", -0.02, date(2024, 3, 1)),
    ]
    items = yearly_aggregate_from_rows(rows)
    assert len(items) == 2
    assert items[0].year == 2023
    assert items[1].year == 2024
    assert items[0].total_trades == 1

