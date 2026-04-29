"""单仓位资金约束下的回测成交筛选与权益核算。

**所有策略**的已平仓信号均经本模块筛选后落库；完整逻辑包括：持仓名义、补仓池划入/盈利回流、同日仅一笔、资金不足跳过、遍历全量信号。

**同日多标的择一**：
- 若同一 buy_date 有多笔可成交闭仓样本，默认在这些样本中**随机择一**视为成交，其余记为 ``not_traded(same_buy_day)``。
- 随机性用于避免“固定字典序”导致的偶然性；为保证可追溯性，应将随机种子写入回测任务的 assumptions_json。

**日历规则（与 ``allow_rebuy_same_day_as_prior_sell`` 区分）**：
- ``True``（仅 ``panic_pullback`` 使用）：上一笔卖出日为 S 时，下一笔买入日须 **≥ S**，即 **卖出当日可再按收盘价买入另一只**（下午卖、下午买的日线近似）。
- ``False``（其它策略）：须 **买入日 > S**，卖出当日不得再开仓，仅早于 S 的与同日换股均跳过。
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, replace
from datetime import date
from typing import Any

from app.services.strategy.strategy_base import BacktestTrade


def _as_not_traded(t: BacktestTrade, *, skip_reason: str) -> BacktestTrade:
    """
    选中未成交：顶层不设收益率/卖出价日，避免与已平仓绩效混淆；假设口径写入 extra。
    """
    extra: dict[str, Any] = {
        **(t.extra or {}),
        "portfolio_status": "selected_not_traded",
        "skip_reason": skip_reason,
    }
    if t.return_rate is not None:
        extra["hypothetical_return_rate"] = t.return_rate
    if t.sell_date is not None:
        extra["hypothetical_sell_date"] = t.sell_date.isoformat()
    if t.sell_price is not None:
        extra["hypothetical_sell_price"] = float(t.sell_price)
    return replace(
        t,
        trade_type="not_traded",
        return_rate=None,
        sell_date=None,
        sell_price=None,
        extra=extra,
    )


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
    same_day_pick_seed: int | None = None,
) -> tuple[list[BacktestTrade], list[BacktestTrade], PortfolioCapitalSummary]:
    """
    在已平仓交易集合上按时间顺序做资金与仓位约束筛选。

    :param closed_trades: 仅含 trade_type==closed 且 sell_date、return_rate 有效的交易
    :param allow_rebuy_same_day_as_prior_sell: 恐慌回落法为 True（卖出当日可再买）；其它策略为 False
    :param same_day_pick_seed: 同一买入日多标的可成交时的随机种子；传入以便复现“同日择一”的随机结果
    :return: (实际成交的闭仓列表, 选中未交易列表, 资金摘要)
    """
    valid: list[BacktestTrade] = []
    for t in closed_trades:
        if t.trade_type != "closed":
            continue
        if t.sell_date is None or t.return_rate is None:
            continue
        valid.append(t)

    # 先按 buy_date 分组；组内顺序不应再决定“同日择一”的结果（改为随机抽样）。
    # 这里仍排序是为了稳定分组与非同日逻辑（如 last_sell_date 推进）。
    valid.sort(key=lambda x: (x.buy_date, x.sell_date, x.stock_code))

    cash = float(initial_principal)
    reserve = float(initial_reserve)
    last_sell_date: date | None = None
    used_buy_dates: set[date] = set()
    rng = random.Random(same_day_pick_seed)

    executed: list[BacktestTrade] = []
    not_traded_same_day: list[BacktestTrade] = []
    not_traded_before_sell: list[BacktestTrade] = []
    not_traded_insufficient_funds: list[BacktestTrade] = []
    skipped = 0
    seq = 0

    idx = 0
    while idx < len(valid):
        buy_d = valid[idx].buy_date
        group: list[BacktestTrade] = []
        while idx < len(valid) and valid[idx].buy_date == buy_d:
            group.append(valid[idx])
            idx += 1

        # 保险：若上游重复调用导致同一 buy_date 已被占用，则整组均记为 same_buy_day
        if buy_d in used_buy_dates:
            for t in group:
                skipped += 1
                not_traded_same_day.append(_as_not_traded(t, skip_reason="same_buy_day"))
            continue

        # 日历约束：先按上一笔卖出日过滤
        blocked: list[BacktestTrade] = []
        eligible: list[BacktestTrade] = []
        for t in group:
            if last_sell_date is not None:
                if allow_rebuy_same_day_as_prior_sell:
                    calendar_blocks = t.buy_date < last_sell_date
                else:
                    calendar_blocks = t.buy_date <= last_sell_date
                if calendar_blocks:
                    blocked.append(t)
                    continue
            eligible.append(t)

        for t in blocked:
            skipped += 1
            not_traded_before_sell.append(_as_not_traded(t, skip_reason="before_previous_sell"))

        if not eligible:
            continue

        # 资金约束：同一 buy_date 下 position_size 固定，因此资金不足时整组都无法开仓
        reserve_used_before_open = 0.0
        if cash < position_size:
            need = position_size - cash
            take = min(need, reserve)
            if take < need:
                for t in eligible:
                    skipped += 1
                    not_traded_insufficient_funds.append(_as_not_traded(t, skip_reason="insufficient_funds"))
                continue
            reserve -= take
            cash += take
            reserve_used_before_open = float(take)

        chosen = rng.choice(eligible) if len(eligible) > 1 else eligible[0]
        for t in eligible:
            if t is chosen:
                continue
            skipped += 1
            not_traded_same_day.append(_as_not_traded(t, skip_reason="same_buy_day"))

        # 成交 chosen
        cash -= position_size
        r = float(chosen.return_rate)
        proceeds = position_size * (1.0 + r)
        pnl_yuan = proceeds - position_size

        if pnl_yuan > 0:
            reserve += pnl_yuan
            cash += position_size
        else:
            cash += proceeds

        reserve_balance_after_sell = reserve

        last_sell_date = chosen.sell_date
        used_buy_dates.add(chosen.buy_date)
        seq += 1
        new_extra = {
            **(chosen.extra or {}),
            "portfolio_seq": seq,
            "position_notional_yuan": round(position_size, 2),
            "trade_pnl_yuan": round(pnl_yuan, 2),
            "profit_amount_yuan": round(pnl_yuan, 2) if pnl_yuan > 0 else 0.0,
            "loss_amount_yuan": round(-pnl_yuan, 2) if pnl_yuan < 0 else 0.0,
            "reserve_used_before_open_yuan": round(reserve_used_before_open, 2),
            "reserve_balance_after_sell_yuan": round(reserve_balance_after_sell, 2),
            "same_day_pick_policy": "random_one",
            "same_day_pick_seed": same_day_pick_seed,
        }
        executed.append(replace(chosen, extra=new_extra))

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
