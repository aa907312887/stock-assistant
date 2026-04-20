"""指数 PE 百分位推理：成分权重 × 个股 pe_percentile，缺失项剔除后重新归一。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.index_daily_bar import IndexDailyBar
from app.models.index_weight import IndexWeight
from app.models.stock_daily_bar import StockDailyBar


def normalize_ts_code(code: str) -> str:
    """统一 ts_code 后缀大小写，便于与持仓/日线对齐。"""
    s = (code or "").strip()
    if not s:
        return s
    if "." in s:
        left, right = s.rsplit(".", 1)
        return f"{left.strip().upper()}.{right.strip().upper()}"
    return s.upper()


def resolve_weight_table_date(
    db: Session,
    index_ts_code: str,
    *,
    anchor_date: date,
    explicit_weight_as_of: date | None,
) -> date | None:
    """选取用于展示的权重表日期：显式传入优先，否则取 anchor 日之前（含）最近一期。"""
    ic = normalize_ts_code(index_ts_code)
    if explicit_weight_as_of is not None:
        exists = (
            db.query(IndexWeight.trade_date)
            .filter(IndexWeight.index_code == ic, IndexWeight.trade_date == explicit_weight_as_of)
            .limit(1)
            .scalar()
        )
        return explicit_weight_as_of if exists else None

    row = (
        db.query(IndexWeight.trade_date)
        .filter(IndexWeight.index_code == ic, IndexWeight.trade_date <= anchor_date)
        .order_by(IndexWeight.trade_date.desc())
        .limit(1)
        .scalar()
    )
    return row


def load_weights_for_date(db: Session, index_ts_code: str, weight_date: date) -> list[tuple[str, Decimal]]:
    """返回 (规范化 con_code, 原始权重) 列表。"""
    ic = normalize_ts_code(index_ts_code)
    rows = (
        db.query(IndexWeight.con_code, IndexWeight.weight)
        .filter(IndexWeight.index_code == ic, IndexWeight.trade_date == weight_date)
        .all()
    )
    out: list[tuple[str, Decimal]] = []
    for con_code, w in rows:
        cc = normalize_ts_code(con_code or "")
        if cc and w is not None:
            out.append((cc, Decimal(str(w))))
    return out


def weighted_pe_percentile_core(
    norm_pairs: list[tuple[str, Decimal]],
    pe_map: dict[str, Decimal | None],
) -> tuple[list[dict[str, Any]], float | None, float | None, int]:
    """
    纯函数：已知归一权重与成分 PE 百分位映射时，计算指数推理值（剔除 None 后重归一加权）。
    用于单测与 composition 共用同一口径。
    """
    items: list[dict[str, Any]] = []
    weighted_sum = Decimal("0")
    participating_sum = Decimal("0")
    with_pe = 0

    for c, wi in norm_pairs:
        pep = pe_map.get(c)
        pv = Decimal(str(pep)) if pep is not None else None
        items.append(
            {
                "con_code": c,
                "weight": float(wi),
                "pe_percentile": float(pv) if pv is not None else None,
            }
        )
        if pv is not None:
            weighted_sum += wi * pv
            participating_sum += wi
            with_pe += 1

    idx_pe: float | None = None
    ratio: float | None = None
    if participating_sum > 0:
        idx_pe = float((weighted_sum / participating_sum).quantize(Decimal("0.01")))
        ratio = float(participating_sum.quantize(Decimal("0.0001")))
    return items, idx_pe, ratio, with_pe


def infer_index_pe_percentile_bundle(
    db: Session,
    index_ts_code: str,
    *,
    snapshot_trade_date: date,
    weight_as_of: date | None = None,
) -> dict[str, Any]:
    """
    按 plan：先对全体成分权重归一（和=1），再在 pe 非空集合 S 上按 w_i 重归一后加权求和。
    """
    ic = normalize_ts_code(index_ts_code)
    anchor = snapshot_trade_date
    wd = resolve_weight_table_date(db, ic, anchor_date=anchor, explicit_weight_as_of=weight_as_of)
    if wd is None:
        return {
            "ts_code": ic,
            "weight_table_date": None,
            "snapshot_trade_date": anchor,
            "index_pe_percentile": None,
            "pe_percentile_meta": {
                "formula": "weighted_mean_renormalize",
                "participating_weight_ratio": None,
                "constituents_total": 0,
                "constituents_with_pe": 0,
            },
            "items": [],
            "message": "暂无成分权重数据",
        }

    pairs = load_weights_for_date(db, ic, wd)
    if not pairs:
        return {
            "ts_code": ic,
            "weight_table_date": wd,
            "snapshot_trade_date": anchor,
            "index_pe_percentile": None,
            "pe_percentile_meta": {
                "formula": "weighted_mean_renormalize",
                "participating_weight_ratio": None,
                "constituents_total": 0,
                "constituents_with_pe": 0,
            },
            "items": [],
            "message": "权重表为空",
        }

    sum_w = sum(w for _, w in pairs)
    if sum_w <= 0:
        return {
            "ts_code": ic,
            "weight_table_date": wd,
            "snapshot_trade_date": anchor,
            "index_pe_percentile": None,
            "pe_percentile_meta": {
                "formula": "weighted_mean_renormalize",
                "participating_weight_ratio": None,
                "constituents_total": len(pairs),
                "constituents_with_pe": 0,
            },
            "items": [{"con_code": c, "weight": None, "pe_percentile": None} for c, w in pairs],
            "message": "权重合计异常",
        }

    norm_pairs = [(c, w / sum_w) for c, w in pairs]

    codes = [c for c, _ in norm_pairs]
    pe_rows = (
        db.query(StockDailyBar.stock_code, StockDailyBar.pe_percentile)
        .filter(StockDailyBar.trade_date == anchor, StockDailyBar.stock_code.in_(codes))
        .all()
    )
    pe_map: dict[str, Decimal | None] = {normalize_ts_code(r.stock_code): r.pe_percentile for r in pe_rows}

    items, idx_pe, ratio, with_pe = weighted_pe_percentile_core(norm_pairs, pe_map)

    return {
        "ts_code": ic,
        "weight_table_date": wd,
        "snapshot_trade_date": anchor,
        "index_pe_percentile": idx_pe,
        "pe_percentile_meta": {
            "formula": "weighted_mean_renormalize",
            "participating_weight_ratio": ratio,
            "constituents_total": len(norm_pairs),
            "constituents_with_pe": with_pe,
        },
        "items": items,
        "message": None,
    }


def suggest_snapshot_trade_date(db: Session, explicit: date | None) -> date | None:
    """composition 默认快照日：参数优先，否则取指数日线最大 trade_date。"""
    if explicit is not None:
        return explicit
    return db.query(func.max(IndexDailyBar.trade_date)).scalar()
