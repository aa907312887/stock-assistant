"""单仓位资金约束下的回测成交筛选与权益核算。

**所有策略**的已平仓信号均经本模块筛选后落库；完整逻辑包括：持仓名义、补仓池划入/盈利回流、同日仅一笔、资金不足跳过、遍历全量信号。

**日历规则（与 ``allow_rebuy_same_day_as_prior_sell`` 区分）**：
- ``True``（仅 ``panic_pullback`` 使用）：上一笔卖出日为 S 时，下一笔买入日须 **≥ S**，即 **卖出当日可再按收盘价买入另一只**（下午卖、下午买的日线近似）。
- ``False``（其它策略）：须 **买入日 > S**，卖出当日不得再开仓，仅早于 S 的与同日换股均跳过。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
from typing import Any

from app.services.strategy.strategy_base import BacktestTrade


@dataclass(frozen=True)
class PortfolioCapitalSummary:
    """仓位模型下的资金结果摘要（可序列化写入 assumptions_json）。"""

    position_size: float
    initial_principal: float
    initial_reserve: float
    final_principal: float
    final_reserve: float
    total_wealth_end: float
    total_profit: float
    total_return_on_initial_total: float
    strategy_raw_closed_count: int
    executed_closed_count: int
    skipped_closed_count: int
    same_day_not_traded_count: int
    before_previous_sell_not_traded_count: int
    insufficient_funds_not_traded_count: int
    allow_rebuy_same_day_as_prior_sell: bool
    description: str

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def simulate_single_slot_portfolio(
    closed_trades: list[BacktestTrade],
    *,
    position_size: float = 100_000.0,
    initial_principal: float = 100_000.0,
    initial_reserve: float = 100_000.0,
    allow_rebuy_same_day_as_prior_sell: bool = True,
) -> tuple[list[BacktestTrade], list[BacktestTrade], PortfolioCapitalSummary]:
    """
    在已平仓交易集合上按时间顺序做资金与仓位约束筛选。

    :param closed_trades: 仅含 trade_type==closed 且 sell_date、return_rate 有效的交易
    :param allow_rebuy_same_day_as_prior_sell: 恐慌回落法为 True（卖出当日可再买）；其它策略为 False
    :return: (实际成交的闭仓列表, 选中未交易列表, 资金摘要)
    """
    valid: list[BacktestTrade] = []
    for t in closed_trades:
        if t.trade_type != "closed":
            continue
        if t.sell_date is None or t.return_rate is None:
            continue
        valid.append(t)

    valid.sort(key=lambda x: (x.buy_date, x.sell_date, x.stock_code))

    cash = float(initial_principal)
    reserve = float(initial_reserve)
    last_sell_date: date | None = None
    used_buy_dates: set[date] = set()

    executed: list[BacktestTrade] = []
    not_traded_same_day: list[BacktestTrade] = []
    not_traded_before_sell: list[BacktestTrade] = []
    not_traded_insufficient_funds: list[BacktestTrade] = []
    skipped = 0
    seq = 0

    for t in valid:
        if t.buy_date in used_buy_dates:
            skipped += 1
            nt_extra = {
                **(t.extra or {}),
                "portfolio_status": "selected_not_traded",
                "skip_reason": "same_buy_day",
            }
            not_traded_same_day.append(
                replace(t, trade_type="not_traded", extra=nt_extra),
            )
            continue
        if last_sell_date is not None:
            if allow_rebuy_same_day_as_prior_sell:
                calendar_blocks = t.buy_date < last_sell_date
            else:
                calendar_blocks = t.buy_date <= last_sell_date
            if calendar_blocks:
                skipped += 1
                nt_extra = {
                    **(t.extra or {}),
                    "portfolio_status": "selected_not_traded",
                    "skip_reason": "before_previous_sell",
                }
                not_traded_before_sell.append(
                    replace(t, trade_type="not_traded", extra=nt_extra),
                )
                continue

        reserve_used_before_open = 0.0
        if cash < position_size:
            need = position_size - cash
            take = min(need, reserve)
            if take < need:
                skipped += 1
                nt_extra = {
                    **(t.extra or {}),
                    "portfolio_status": "selected_not_traded",
                    "skip_reason": "insufficient_funds",
                }
                not_traded_insufficient_funds.append(
                    replace(t, trade_type="not_traded", extra=nt_extra),
                )
                continue
            reserve -= take
            cash += take
            reserve_used_before_open = float(take)

        cash -= position_size
        r = float(t.return_rate)
        proceeds = position_size * (1.0 + r)
        pnl_yuan = proceeds - position_size

        if pnl_yuan > 0:
            reserve += pnl_yuan
            cash += position_size
        else:
            cash += proceeds

        reserve_balance_after_sell = reserve

        last_sell_date = t.sell_date
        used_buy_dates.add(t.buy_date)
        seq += 1
        new_extra = {
            **(t.extra or {}),
            "portfolio_seq": seq,
            "position_notional_yuan": round(position_size, 2),
            "trade_pnl_yuan": round(pnl_yuan, 2),
            "profit_amount_yuan": round(pnl_yuan, 2) if pnl_yuan > 0 else 0.0,
            "loss_amount_yuan": round(-pnl_yuan, 2) if pnl_yuan < 0 else 0.0,
            "reserve_used_before_open_yuan": round(reserve_used_before_open, 2),
            "reserve_balance_after_sell_yuan": round(reserve_balance_after_sell, 2),
        }
        executed.append(replace(t, extra=new_extra))

    initial_total = initial_principal + initial_reserve
    end_wealth = cash + reserve
    profit = end_wealth - initial_total
    ret_on_total = profit / initial_total if initial_total > 0 else 0.0

    if allow_rebuy_same_day_as_prior_sell:
        desc = (
            "固定持仓名义/笔；同日仅一笔；恐慌口径：卖出当日收盘可再买他股，早于上一笔卖出日不可买；"
            "开仓前由补仓池补足现金；盈利计入补仓池，亏损进现金；用尽则跳过"
        )
    else:
        desc = (
            "固定持仓名义/笔；同日仅一笔；须上一笔卖出日次日及以后方可再买（卖出当日不得换股）；"
            "早于上一笔卖出日不可买；开仓前由补仓池补足现金；盈利计入补仓池，亏损进现金；用尽则跳过"
        )

    summary = PortfolioCapitalSummary(
        position_size=position_size,
        initial_principal=initial_principal,
        initial_reserve=initial_reserve,
        final_principal=round(cash, 2),
        final_reserve=round(reserve, 2),
        total_wealth_end=round(end_wealth, 2),
        total_profit=round(profit, 2),
        total_return_on_initial_total=round(ret_on_total, 6),
        strategy_raw_closed_count=len(valid),
        executed_closed_count=len(executed),
        skipped_closed_count=skipped,
        same_day_not_traded_count=len(not_traded_same_day),
        before_previous_sell_not_traded_count=len(not_traded_before_sell),
        insufficient_funds_not_traded_count=len(not_traded_insufficient_funds),
        allow_rebuy_same_day_as_prior_sell=allow_rebuy_same_day_as_prior_sell,
        description=desc,
    )
    not_traded_all = not_traded_same_day + not_traded_before_sell + not_traded_insufficient_funds
    return executed, not_traded_all, summary
