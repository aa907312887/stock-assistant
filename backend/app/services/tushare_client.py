"""Tushare Pro API 封装：股票列表、全市场日线、利润表。"""
import json
import logging
import time
from datetime import date
from decimal import Decimal
from threading import Lock
from typing import Any

import pandas as pd
import tushare as ts

from app.config import settings

logger = logging.getLogger(__name__)

# 与定时任务/同步链路检索一致，标明 Tushare 封装层
TUSHARE_CLIENT_ALERT = "[Tushare客户端告警]"

MAX_RETRIES = 3
RETRY_INTERVAL_SEC = 5
RATE_PAUSE_SEC = 0.06

_pro_lock = Lock()
_pro_api: Any = None
_cached_token: str | None = None


class TushareClientError(Exception):
    """Tushare 请求失败或解析异常"""

    pass


def _get_pro() -> Any:
    """
    使用显式 token 初始化 pro_api（仅来自 app.config.settings，即 backend/.env）。
    不调用 ts.set_token()，避免写入 ~/tk.csv 或与系统环境变量 TUSHARE_TOKEN 混用。
    """
    global _pro_api, _cached_token
    token = (settings.tushare_token or "").strip()
    if not token:
        logger.error(
            "%s 调用方法=tushare_client._get_pro | 接口=未初始化 pro_api | 原因=TUSHARE_TOKEN 未配置（请在 backend/.env 中设置）",
            TUSHARE_CLIENT_ALERT,
        )
        raise TushareClientError("TUSHARE_TOKEN 未配置（请在 backend/.env 中设置）")
    with _pro_lock:
        if _pro_api is None or _cached_token != token:
            _pro_api = ts.pro_api(token=token)
            _cached_token = token
        return _pro_api


def _df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _exchange_from_ts_code(ts_code: str) -> str:
    suf = ts_code.split(".")[-1].upper() if "." in ts_code else ""
    if suf == "SZ":
        return "SZ"
    if suf == "SH":
        return "SH"
    if suf == "BJ":
        return "BJ"
    return suf


def get_stock_list() -> list[dict[str, Any]]:
    """
    上市股票列表，对应 Tushare Pro 接口 **stock_basic**（见官方文档）。
    返回每行含：dm/mc/jys（与下游同步逻辑兼容键）及 area/industry/list_date 等原始字段映射。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,list_date,market,exchange",
            )
            rows = _df_to_records(df)
            out: list[dict[str, Any]] = []
            for r in rows:
                tc = (r.get("ts_code") or "").strip()
                if not tc:
                    continue
                area = (r.get("area") or "").strip()
                industry = (r.get("industry") or "").strip()
                ld_raw = r.get("list_date")
                if ld_raw is None:
                    ld_val = None
                else:
                    try:
                        ld_val = None if isinstance(ld_raw, float) and pd.isna(ld_raw) else str(ld_raw).strip() or None
                    except Exception:
                        ld_val = str(ld_raw).strip() or None
                out.append(
                    {
                        "dm": tc,
                        "mc": r.get("name") or "",
                        "jys": _exchange_from_ts_code(tc),
                        "region": area or None,
                        "industry_name": industry or None,
                        "list_date": ld_val,
                    }
                )
            return out
        except Exception as e:
            last_err = e
            logger.warning("Tushare stock_basic 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare stock_basic 失败: {last_err}") from last_err


def get_daily_by_trade_date(trade_date: date) -> dict[str, dict[str, Any]]:
    """
    指定交易日的全市场日线，键为 ts_code（如 000001.SZ）。
    amount 单位为千元，vol 单位为手（与 Tushare 文档一致）。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = pro.daily(trade_date=trade_date.strftime("%Y%m%d"))
            rows = _df_to_records(df)
            return {str(r["ts_code"]): r for r in rows if r.get("ts_code")}
        except Exception as e:
            last_err = e
            logger.warning("Tushare daily 失败 attempt=%s error=%s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare daily 失败: {last_err}") from last_err


def normalize_daily_bar(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    将 Tushare daily 行转为与旧同步逻辑兼容的字段：o/h/l/c/pc/a/v，
    其中成交额转为元、成交量转为股；pct_chg、change 为涨跌幅与涨跌额。
    """
    if not row:
        return None

    def _dec(v: Any) -> Decimal | None:
        if v is None or v == "":
            return None
        try:
            if isinstance(v, float) and pd.isna(v):
                return None
        except Exception:
            pass
        try:
            return Decimal(str(v))
        except Exception:
            return None

    o = _dec(row.get("open"))
    h = _dec(row.get("high"))
    l = _dec(row.get("low"))
    c = _dec(row.get("close"))
    pc = _dec(row.get("pre_close"))
    vol_hand = _dec(row.get("vol"))
    amt_k = _dec(row.get("amount"))
    # 千元 -> 元；手 -> 股（1 手 100 股）
    amount_yuan = (amt_k * Decimal("1000")) if amt_k is not None else None
    volume_shares = (vol_hand * Decimal("100")) if vol_hand is not None else None
    pct_chg = _dec(row.get("pct_chg"))
    change_amt = _dec(row.get("change"))
    return {
        "o": o,
        "h": h,
        "l": l,
        "c": c,
        "pc": pc,
        "a": amount_yuan,
        "v": volume_shares,
        "pct_chg": pct_chg,
        "change": change_amt,
    }


def get_fin_income(
    ts_code: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """
    利润表（按公告日期区间筛选）。返回行中含 end_date、total_revenue、oper_cost 等。
    start/end 为 YYYYMMDD，对应 Tushare income 的公告日期区间。
    """
    pro = _get_pro()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if RATE_PAUSE_SEC > 0:
                time.sleep(RATE_PAUSE_SEC)
            df = pro.income(
                ts_code=ts_code,
                start_date=start or "20000101",
                end_date=end or "20991231",
            )
            return _df_to_records(df)
        except Exception as e:
            last_err = e
            logger.warning("Tushare income 失败 attempt=%s code=%s error=%s", attempt + 1, ts_code, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL_SEC)
    raise TushareClientError(f"Tushare income 失败: {last_err}") from last_err
