"""股票同步相关的通用工具函数。"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.tushare_client import get_open_trade_dates

logger = logging.getLogger(__name__)


def safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def safe_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def safe_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    try:
        return (numerator / denominator) * Decimal("100")
    except Exception:
        return None


def ymd(value: date) -> str:
    return value.strftime("%Y%m%d")


def subtract_years(d: date, years: int) -> date:
    """粗略减去若干年，处理 2 月 29 日等情况。"""
    try:
        return date(d.year - years, d.month, d.day)
    except ValueError:
        return date(d.year - years, d.month, 28)


def is_last_trading_day_of_month(d: date) -> bool:
    """判断 d 是否为当月最后一个开市日（用于月线仅在月末更新）。"""
    last_cal = date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
    opens = get_open_trade_dates(
        start=date(d.year, d.month, 1).strftime("%Y%m%d"),
        end=last_cal.strftime("%Y%m%d"),
    )
    return bool(opens) and d == opens[-1]


def enumerate_week_batch_trade_dates(start: date, end: date) -> list[date]:
    """区间内按「自然周」去重，每周取该周最后一个开市日，用于 stk_weekly_monthly 按日批量拉取。"""
    opens = get_open_trade_dates(start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    by_week: dict[tuple[int, int], list[date]] = {}
    for d in opens:
        y, w, _ = d.isocalendar()
        key = (y, w)
        by_week.setdefault(key, []).append(d)
    return sorted(max(ds) for ds in by_week.values())


def enumerate_month_batch_trade_dates(start: date, end: date) -> list[date]:
    """区间内每个自然月的最后一个开市日。"""
    out: list[date] = []
    y, m = start.year, start.month
    months_done = 0
    while date(y, m, 1) <= end:
        last_cal = date(y, m, calendar.monthrange(y, m)[1])
        mo = get_open_trade_dates(
            start=date(y, m, 1).strftime("%Y%m%d"),
            end=last_cal.strftime("%Y%m%d"),
        )
        if mo:
            last_open = mo[-1]
            if start <= last_open <= end:
                out.append(last_open)
        months_done += 1
        if months_done == 1 or months_done % 6 == 0:
            msg = f"[月线枚举] 已处理 {months_done} 个月份日历请求，当前 {y}-{m:02d}"
            logger.info(msg)
            print(msg, flush=True)
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def get_week_last_open_date(anchor_date: date) -> date | None:
    """返回 anchor 所在自然周（周一至周日）的最后一个开市日。"""
    week_start = anchor_date.fromordinal(anchor_date.toordinal() - anchor_date.weekday())
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    opens = get_open_trade_dates(start=week_start.strftime("%Y%m%d"), end=week_end.strftime("%Y%m%d"))
    return opens[-1] if opens else None


def get_month_last_open_date(anchor_date: date) -> date | None:
    """返回 anchor 所在自然月最后一个开市日。"""
    last_cal = date(anchor_date.year, anchor_date.month, calendar.monthrange(anchor_date.year, anchor_date.month)[1])
    opens = get_open_trade_dates(
        start=date(anchor_date.year, anchor_date.month, 1).strftime("%Y%m%d"),
        end=last_cal.strftime("%Y%m%d"),
    )
    return opens[-1] if opens else None
