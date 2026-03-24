"""个人持仓：加权成本、操作校验、清仓结算。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.portfolio_operation import PortfolioOperation
from app.models.portfolio_trade import PortfolioTrade
from app.models.stock_basic import StockBasic

ZERO = Decimal("0")


def _dec(x) -> Decimal:
    if x is None:
        return ZERO
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def stock_exists(db: Session, stock_code: str) -> bool:
    return (
        db.query(StockBasic.id).filter(StockBasic.code == stock_code.strip()).first()
        is not None
    )


def get_stock_name(db: Session, stock_code: str) -> str | None:
    row = db.query(StockBasic.name).filter(StockBasic.code == stock_code.strip()).first()
    return row[0] if row else None


def find_open_trade(db: Session, user_id: int, stock_code: str) -> PortfolioTrade | None:
    return (
        db.query(PortfolioTrade)
        .filter(
            PortfolioTrade.user_id == user_id,
            PortfolioTrade.stock_code == stock_code.strip(),
            PortfolioTrade.status == "open",
        )
        .first()
    )


def get_trade_for_user(db: Session, trade_id: int, user_id: int) -> PortfolioTrade | None:
    return (
        db.query(PortfolioTrade)
        .filter(PortfolioTrade.id == trade_id, PortfolioTrade.user_id == user_id)
        .first()
    )


def get_operation_for_user(db: Session, op_id: int, user_id: int) -> PortfolioOperation | None:
    return (
        db.query(PortfolioOperation)
        .filter(PortfolioOperation.id == op_id, PortfolioOperation.user_id == user_id)
        .first()
    )


def _apply_buy(
    trade: PortfolioTrade,
    qty: Decimal,
    price: Decimal,
    fee: Decimal,
) -> None:
    """买入类：增加持仓与成本基数。"""
    qty = _dec(qty)
    price = _dec(price)
    fee = _dec(fee)
    add_cost = qty * price + fee
    tcb = _dec(trade.total_cost_basis)
    tq = _dec(trade.total_qty)
    new_tcb = tcb + add_cost
    new_tq = tq + qty
    trade.total_cost_basis = new_tcb
    trade.total_qty = new_tq
    trade.avg_cost = (new_tcb / new_tq) if new_tq > ZERO else ZERO


def _apply_sell(
    trade: PortfolioTrade,
    qty: Decimal,
    price: Decimal,
    fee: Decimal,
) -> Decimal:
    """卖出：减少持仓，累计已实现盈亏；返回本笔卖出实现的盈亏。"""
    qty = _dec(qty)
    price = _dec(price)
    fee = _dec(fee)
    avg = _dec(trade.avg_cost)
    tq = _dec(trade.total_qty)
    if qty > tq:
        raise ValueError("卖出数量超过当前持仓")
    if tq <= ZERO:
        raise ValueError("当前无持仓可卖")
    # 本笔实现盈亏：卖价收入 - 成本 - 费
    realized = qty * price - fee - qty * avg
    acc = _dec(trade.accumulated_realized_pnl)
    trade.accumulated_realized_pnl = acc + realized
    tcb = _dec(trade.total_cost_basis)
    tcb -= qty * avg
    tq -= qty
    trade.total_cost_basis = tcb
    trade.total_qty = tq
    if tq > ZERO:
        trade.avg_cost = tcb / tq
    else:
        trade.avg_cost = ZERO
    return realized


def create_open_trade(
    db: Session,
    user_id: int,
    stock_code: str,
    op_date: date,
    qty: Decimal,
    price: Decimal,
    fee: Decimal | None,
) -> tuple[PortfolioTrade, PortfolioOperation]:
    code = stock_code.strip()
    if not stock_exists(db, code):
        raise ValueError("股票代码不存在于基础库，本期仅支持股票")
    if find_open_trade(db, user_id, code):
        raise ValueError("同一股票已存在未完结持仓，请先清仓或删除该持仓")
    fee = _dec(fee)
    qty = _dec(qty)
    price = _dec(price)
    now = datetime.combine(op_date, datetime.min.time())
    trade = PortfolioTrade(
        user_id=user_id,
        stock_code=code,
        status="open",
        opened_at=now,
        total_cost_basis=ZERO,
        total_qty=ZERO,
        avg_cost=ZERO,
        accumulated_realized_pnl=ZERO,
    )
    _apply_buy(trade, qty, price, fee)
    db.add(trade)
    db.flush()
    op = PortfolioOperation(
        trade_id=trade.id,
        user_id=user_id,
        op_type="open",
        op_date=op_date,
        qty=qty,
        price=price,
        amount=qty * price,
        fee=fee,
    )
    db.add(op)
    db.flush()
    return trade, op


def add_or_reduce(
    db: Session,
    user_id: int,
    trade_id: int,
    op_type: str,
    op_date: date,
    qty: Decimal,
    price: Decimal,
    fee: Decimal | None,
    operation_rating: str | None,
    note: str | None,
) -> PortfolioOperation:
    trade = get_trade_for_user(db, trade_id, user_id)
    if not trade or trade.status != "open":
        raise ValueError("交易不存在或已结束")
    fee = _dec(fee)
    qty = _dec(qty)
    price = _dec(price)
    if op_type == "add":
        _apply_buy(trade, qty, price, fee)
        op_t = "add"
    elif op_type == "reduce":
        _apply_sell(trade, qty, price, fee)
        op_t = "reduce"
    else:
        raise ValueError("无效的操作类型")
    op = PortfolioOperation(
        trade_id=trade.id,
        user_id=user_id,
        op_type=op_t,
        op_date=op_date,
        qty=qty,
        price=price,
        amount=qty * price,
        fee=fee,
        operation_rating=operation_rating,
        note=note,
    )
    db.add(op)
    db.flush()
    return op


def close_trade(
    db: Session,
    user_id: int,
    trade_id: int,
    op_date: date,
    qty: Decimal,
    price: Decimal,
    fee: Decimal | None,
    operation_rating: str | None,
    note: str | None,
) -> tuple[PortfolioTrade, Decimal]:
    trade = get_trade_for_user(db, trade_id, user_id)
    if not trade or trade.status != "open":
        raise ValueError("交易不存在或已结束")
    fee = _dec(fee)
    qty = _dec(qty)
    price = _dec(price)
    tq = _dec(trade.total_qty)
    if qty != tq:
        raise ValueError("清仓数量必须与当前持仓数量一致")
    _apply_sell(trade, qty, price, fee)
    op = PortfolioOperation(
        trade_id=trade.id,
        user_id=user_id,
        op_type="close",
        op_date=op_date,
        qty=qty,
        price=price,
        amount=qty * price,
        fee=fee,
        operation_rating=operation_rating,
        note=note,
    )
    db.add(op)
    trade.status = "closed"
    trade.closed_at = datetime.combine(op_date, datetime.min.time())
    trade.realized_pnl = trade.accumulated_realized_pnl
    trade.total_qty = ZERO
    trade.avg_cost = ZERO
    trade.total_cost_basis = ZERO
    db.flush()
    return trade, _dec(trade.realized_pnl)


def delete_open_trade(db: Session, user_id: int, trade_id: int) -> bool:
    trade = get_trade_for_user(db, trade_id, user_id)
    if not trade:
        return False
    if trade.status != "open":
        raise ValueError("仅可删除进行中的交易")
    db.query(PortfolioOperation).filter(PortfolioOperation.trade_id == trade_id).delete()
    db.delete(trade)
    db.flush()
    return True


def aggregate_stats(
    db: Session,
    user_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    """股票胜率与操作胜率聚合。"""
    q_closed = db.query(PortfolioTrade).filter(
        PortfolioTrade.user_id == user_id,
        PortfolioTrade.status == "closed",
        PortfolioTrade.realized_pnl.isnot(None),
    )
    if from_date:
        q_closed = q_closed.filter(PortfolioTrade.closed_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        q_closed = q_closed.filter(
            PortfolioTrade.closed_at <= datetime.combine(to_date, datetime.max.time())
        )
    closed = q_closed.all()
    won = lost = breakeven = 0
    total_profit = ZERO
    total_loss = ZERO
    for t in closed:
        pnl = _dec(t.realized_pnl)
        if pnl > ZERO:
            won += 1
            total_profit += pnl
        elif pnl < ZERO:
            lost += 1
            total_loss += pnl
        else:
            breakeven += 1
    total = len(closed)
    rate = float(won / total) if total else None
    net_pnl = total_profit + total_loss
    base_cost = total_profit + abs(total_loss)
    net_pnl_rate = float(net_pnl / base_cost) if base_cost > ZERO else None

    q_ops = db.query(PortfolioOperation).filter(PortfolioOperation.user_id == user_id)
    if from_date:
        q_ops = q_ops.filter(PortfolioOperation.op_date >= from_date)
    if to_date:
        q_ops = q_ops.filter(PortfolioOperation.op_date <= to_date)
    ops = q_ops.all()
    good = bad = unrated = 0
    for o in ops:
        if o.operation_rating == "good":
            good += 1
        elif o.operation_rating == "bad":
            bad += 1
        else:
            unrated += 1
    rated_total = good + bad
    op_rate = float(good / rated_total) if rated_total else None

    return {
        "stock_win_rate": {
            "won": won,
            "lost": lost,
            "breakeven": breakeven,
            "total": total,
            "rate": rate,
        },
        "operation_win_rate": {
            "good": good,
            "bad": bad,
            "unrated": unrated,
            "rated_total": rated_total,
            "rate": op_rate,
        },
        "overall_pnl": {
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_pnl": net_pnl,
            "net_pnl_rate": net_pnl_rate,
        },
    }
