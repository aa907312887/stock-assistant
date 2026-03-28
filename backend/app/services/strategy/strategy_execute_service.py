"""策略执行与落库服务。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import StrategyExecutionSnapshot, StrategySelectionItem, StrategySignalEvent, StockBasic
from app.services.screening_service import get_latest_bar_date
from app.services.strategy.registry import get_strategy
from app.services.strategy.strategy_base import StrategyCandidate, StrategyExecutionResult, StrategySignal


class StrategyNotFoundError(Exception):
    pass


class StrategyDataNotReadyError(Exception):
    pass


class StrategyResultNotFoundError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def execute_strategy(
    db: Session,
    *,
    strategy_id: str,
    as_of_date: date | None,
) -> tuple[StrategyExecutionSnapshot, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    执行策略并落库“操作现场”。

    返回：
    - execution_snapshot ORM
    - items（给 API 的简化 dict 列表）
    - signals（给 API 的简化 dict 列表）
    """

    strategy = get_strategy(strategy_id)
    if not strategy:
        raise StrategyNotFoundError(f"策略不存在: {strategy_id}")

    dd = as_of_date or get_latest_bar_date(db, "daily")
    if dd is None:
        raise StrategyDataNotReadyError("日线数据为空，无法执行策略")

    result: StrategyExecutionResult = strategy.execute(as_of_date=dd)

    # 幂等：同一 strategy_id + as_of_date + strategy_version 的执行，复用同一个 execution_id。
    # 重复执行时先清理旧“操作现场”（候选/事件/快照），再写入最新结果。
    execution_id = f"{strategy.strategy_id}-{dd.isoformat()}-{strategy.version}"

    db.query(StrategySelectionItem).filter(StrategySelectionItem.execution_id == execution_id).delete()
    db.query(StrategySignalEvent).filter(StrategySignalEvent.execution_id == execution_id).delete()
    db.query(StrategyExecutionSnapshot).filter(StrategyExecutionSnapshot.execution_id == execution_id).delete()

    snapshot = StrategyExecutionSnapshot(
        execution_id=execution_id,
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.version,
        market="A股",
        as_of_date=result.as_of_date,
        timeframe="daily",
        params_json=result.params,
        assumptions_json={
            **(result.assumptions or {}),
            "generated_at": _now_iso(),
        },
        data_source="tushare",
    )
    db.add(snapshot)

    # 写入候选明细
    selection_rows: list[StrategySelectionItem] = []
    for it in result.items:
        selection_rows.append(
            StrategySelectionItem(
                execution_id=execution_id,
                stock_code=it.stock_code,
                trigger_date=it.trigger_date,
                summary_json={
                    **(it.summary or {}),
                    "exchange_type": it.exchange_type,
                },
            )
        )
    if selection_rows:
        db.add_all(selection_rows)

    # 写入信号事件（操作现场）
    signal_rows: list[StrategySignalEvent] = []
    for s in result.signals:
        signal_rows.append(
            StrategySignalEvent(
                execution_id=execution_id,
                stock_code=s.stock_code,
                event_date=s.event_date,
                event_type=s.event_type,
                event_payload_json=s.payload,
            )
        )
    if signal_rows:
        db.add_all(signal_rows)

    db.commit()
    db.refresh(snapshot)

    # 补齐候选的股票名（若策略实现没填）
    items = _candidates_to_api_items(db, result.items)
    signals = _signals_to_api_items(result.signals)
    return snapshot, items, signals


def _legacy_exchange_type(
    exchange: str | None,
    market: str | None,
    fallback: str | None,
) -> str | None:
    """兼容冲高回落等旧页单列展示：优先策略自带，否则拼接交易所/板块。"""
    if fallback:
        return fallback
    parts = [p for p in (exchange, market) if p]
    return "/".join(parts) if parts else None


def get_latest_strategy_result(
    db: Session,
    *,
    strategy_id: str,
    as_of_date: date | None = None,
) -> tuple[StrategyExecutionSnapshot, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    只读查询：返回某策略最新一次已落库的执行结果（不触发执行）。
    """
    q = db.query(StrategyExecutionSnapshot).filter(StrategyExecutionSnapshot.strategy_id == strategy_id)
    if as_of_date is not None:
        q = q.filter(StrategyExecutionSnapshot.as_of_date == as_of_date)
    snapshot = q.order_by(StrategyExecutionSnapshot.as_of_date.desc(), StrategyExecutionSnapshot.created_at.desc()).first()
    if not snapshot:
        raise StrategyResultNotFoundError("暂无已生成的策略结果，请先等待定时任务或手动执行一次")

    # 候选明细：用 selection_item + stock_basic 补全名称/交易所
    rows = (
        db.query(StrategySelectionItem, StockBasic)
        .join(StockBasic, StockBasic.code == StrategySelectionItem.stock_code)
        .filter(StrategySelectionItem.execution_id == snapshot.execution_id)
        .order_by(StrategySelectionItem.stock_code)
        .all()
    )
    items: list[dict[str, Any]] = []
    for sel, basic in rows:
        summary = dict(sel.summary_json or {})
        ex = basic.exchange
        mk = basic.market
        items.append(
            {
                "stock_code": sel.stock_code,
                "stock_name": basic.name,
                "exchange": ex,
                "market": mk,
                "exchange_type": _legacy_exchange_type(ex, mk, summary.get("exchange_type")),
                "trigger_date": sel.trigger_date,
                "summary": summary,
            }
        )

    signal_rows = (
        db.query(StrategySignalEvent)
        .filter(StrategySignalEvent.execution_id == snapshot.execution_id)
        .order_by(StrategySignalEvent.id.asc())
        .all()
    )
    signals = [
        {
            "stock_code": r.stock_code,
            "event_date": r.event_date,
            "event_type": r.event_type,
            "payload": r.event_payload_json or {},
        }
        for r in signal_rows
    ]
    return snapshot, items, signals


def _candidates_to_api_items(db: Session, items: list[StrategyCandidate]) -> list[dict[str, Any]]:
    if not items:
        return []
    codes = list({i.stock_code for i in items})
    rows = db.query(StockBasic.code, StockBasic.name, StockBasic.exchange, StockBasic.market).filter(
        StockBasic.code.in_(codes)
    ).all()
    code_to_basic: dict[str, tuple[str | None, str | None, str | None]] = {
        r.code: (r.name, r.exchange, r.market) for r in rows
    }
    out: list[dict[str, Any]] = []
    for i in items:
        name_b, ex_b, mk_b = code_to_basic.get(i.stock_code, (None, None, None))
        stock_name = i.stock_name or name_b
        exchange = ex_b
        market = mk_b
        out.append(
            {
                "stock_code": i.stock_code,
                "stock_name": stock_name,
                "exchange": exchange,
                "market": market,
                "exchange_type": _legacy_exchange_type(exchange, market, i.exchange_type),
                "trigger_date": i.trigger_date,
                "summary": i.summary,
            }
        )
    return out


def _signals_to_api_items(signals: list[StrategySignal]) -> list[dict[str, Any]]:
    return [
        {
            "stock_code": s.stock_code,
            "event_date": s.event_date,
            "event_type": s.event_type,
            "payload": s.payload,
        }
        for s in signals
    ]

