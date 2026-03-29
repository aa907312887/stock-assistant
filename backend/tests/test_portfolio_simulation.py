"""单仓位资金约束仿真单元测试。"""

from datetime import date

from app.services.backtest.portfolio_simulation import simulate_single_slot_portfolio
from app.services.strategy.strategy_base import BacktestTrade


def _closed(code: str, buy: date, sell: date, rr: float) -> BacktestTrade:
    return BacktestTrade(
        stock_code=code,
        stock_name=None,
        buy_date=buy,
        buy_price=10.0,
        sell_date=sell,
        sell_price=10.0 * (1 + rr),
        return_rate=rr,
        trade_type="closed",
    )


def test_same_buy_date_only_one_executed():
    d = date(2024, 6, 1)
    s = date(2024, 6, 3)
    a = _closed("000001.SZ", d, s, 0.02)
    b = _closed("000002.SZ", d, s, 0.05)
    ex, nt, summary = simulate_single_slot_portfolio([a, b])
    assert len(ex) == 1
    assert len(nt) == 1
    assert ex[0].stock_code == "000001.SZ"
    assert nt[0].stock_code == "000002.SZ"
    assert nt[0].trade_type == "not_traded"
    assert nt[0].extra.get("skip_reason") == "same_buy_day"
    assert summary.skipped_closed_count == 1
    assert summary.same_day_not_traded_count == 1


def test_buy_on_same_day_as_previous_sell_allowed():
    """上一笔卖出当日可按收盘价再买入下一笔（与恐慌回落「收盘卖、收盘买」口径一致）。"""
    t1 = _closed("A", date(2024, 1, 2), date(2024, 1, 5), 0.01)
    t2 = _closed("B", date(2024, 1, 5), date(2024, 1, 8), 0.02)
    ex, nt, summary = simulate_single_slot_portfolio(
        [t1, t2], allow_rebuy_same_day_as_prior_sell=True,
    )
    assert len(ex) == 2
    assert len(nt) == 0
    assert summary.before_previous_sell_not_traded_count == 0
    assert summary.allow_rebuy_same_day_as_prior_sell is True


def test_buy_on_same_day_as_previous_sell_blocked_when_strict_calendar():
    """非恐慌口径：卖出当日不得再开仓，须次日及以后。"""
    t1 = _closed("A", date(2024, 1, 2), date(2024, 1, 5), 0.01)
    t2 = _closed("B", date(2024, 1, 5), date(2024, 1, 8), 0.02)
    ex, nt, summary = simulate_single_slot_portfolio(
        [t1, t2], allow_rebuy_same_day_as_prior_sell=False,
    )
    assert len(ex) == 1
    assert len(nt) == 1
    assert nt[0].extra.get("skip_reason") == "before_previous_sell"
    assert summary.before_previous_sell_not_traded_count == 1
    assert summary.allow_rebuy_same_day_as_prior_sell is False


def test_must_buy_after_previous_sell():
    t1 = _closed("A", date(2024, 1, 2), date(2024, 1, 4), 0.01)
    t2 = _closed("B", date(2024, 1, 3), date(2024, 1, 5), 0.02)
    ex, nt, summary = simulate_single_slot_portfolio([t1, t2])
    assert len(ex) == 1
    assert len(nt) == 1
    assert nt[0].extra.get("skip_reason") == "before_previous_sell"
    assert ex[0].stock_code == "A"
    assert summary.skipped_closed_count == 1
    assert summary.same_day_not_traded_count == 0
    assert summary.before_previous_sell_not_traded_count == 1


def test_profit_goes_to_reserve():
    """盈利进补仓池，本金名义回现金（总权益与旧模型一致，现金/池子拆分不同）。"""
    t = _closed("A", date(2024, 1, 2), date(2024, 1, 4), 0.05)
    ex, nt, summary = simulate_single_slot_portfolio([t])
    assert len(ex) == 1
    assert summary.final_principal == 100_000.0
    assert summary.final_reserve == 105_000.0
    assert summary.total_wealth_end == 205_000.0
    assert ex[0].extra.get("trade_pnl_yuan") == 5_000.0
    assert ex[0].extra.get("profit_amount_yuan") == 5_000.0
    assert ex[0].extra.get("loss_amount_yuan") == 0.0
    assert ex[0].extra.get("reserve_used_before_open_yuan") == 0.0
    assert ex[0].extra.get("reserve_balance_after_sell_yuan") == 105_000.0


def test_loss_reduces_principal_reserve_unchanged():
    """单笔亏损 5%：回款进本金，预备池未动用。"""
    t = _closed("A", date(2024, 1, 2), date(2024, 1, 4), -0.05)
    ex, nt, summary = simulate_single_slot_portfolio([t])
    assert len(ex) == 1
    assert len(nt) == 0
    assert summary.final_principal == 95_000.0
    assert summary.final_reserve == 100_000.0
    assert summary.total_wealth_end == 195_000.0
    assert summary.total_profit == -5_000.0


def test_reserve_zero_no_top_up_second_trade_skipped():
    """补仓池为 0：首笔亏损后无法凑齐持仓额，第二笔跳过。"""
    t1 = _closed("A", date(2024, 1, 2), date(2024, 1, 4), -0.05)
    t2 = _closed("B", date(2024, 1, 5), date(2024, 1, 8), 0.0)
    ex, nt, summary = simulate_single_slot_portfolio(
        [t1, t2],
        initial_reserve=0.0,
    )
    assert len(ex) == 1
    assert len(nt) == 1
    assert nt[0].extra.get("skip_reason") == "insufficient_funds"
    assert summary.insufficient_funds_not_traded_count == 1
    assert summary.skipped_closed_count >= 1


def test_reserve_top_up_before_second_trade():
    """首笔亏 5% 后第二笔开仓前从预备池补 5 万；第二笔平盘则期末本金 10 万、预备池 9.5 万。"""
    t1 = _closed("A", date(2024, 1, 2), date(2024, 1, 4), -0.05)
    t2 = _closed("B", date(2024, 1, 5), date(2024, 1, 8), 0.0)
    ex, nt, summary = simulate_single_slot_portfolio([t1, t2])
    assert len(ex) == 2
    assert len(nt) == 0
    assert summary.final_principal == 100_000.0
    assert summary.final_reserve == 95_000.0
    assert summary.total_wealth_end == 195_000.0
    assert summary.total_profit == -5_000.0
