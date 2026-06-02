# 数据模型：多周期 MACD 共振主升浪

**日期**：2026-06-02  
**说明**：**不新增**数据库表或列；复用日/周/月 bar 表与智能回测实体。

---

## 1. 持久化实体（复用）

### 1.1 `backtest_task`

与 `specs/010-智能回测/data-model.md` 一致。`strategy_id` 新增取值：`duo_zhou_qi_macd_gong_zhen`。

### 1.2 `backtest_trade`

| 字段 | 取值说明 |
|------|-----------|
| `trigger_date` | **D6 = T_buy**（买入日，与信号完成日相同） |
| `buy_date` | **T_buy**（与 `trigger_date` 相同） |
| `buy_price` | **T_buy 当日收盘价** |
| `sell_date` / `sell_price` | 触发平仓日的 **收盘价** |
| `return_rate` | 由买卖收盘价计算 |
| `trade_type` | `closed` / `unclosed`（区间结束前未触发任一平仓规则） |
| `extra` | JSON；建议字段见下表 |

#### `extra` 建议字段

| 键 | 类型 | 说明 |
|----|------|------|
| `exit_reason` | string | `stop_loss_7pct`（仅亏损止损）/ `sell_macd_red_to_green` / `sell_three_down_days`（不论盈亏的无条件卖出）/ `trailing_take_profit_3pct` |
| `d1_date` | string (ISO date) | 第一次上涨日 D1 |
| `d1_open` | number | D1 开盘价（涨幅过滤基准） |
| `gain_filter_pct` | number | 买入日收盘相对 D1 开盘涨幅（如 0.12 表示 12%） |
| `macd_hist_d6` | number | 买入日日线 hist |
| `weekly_bar_end` | string | 对齐周线 `trade_week_end` |
| `monthly_bar_end` | string | 对齐月线 `trade_month_end` |
| `trailing_armed` | bool | 是否曾启用移动止盈 |
| `peak_close_at_exit` | number | 平仓时记录的峰值收盘（若有） |
| `buy_rule` | string | 固定 `d6_close` |
| `sell_rule` | string | 固定 `close_triggered_multi_exit` |

---

## 2. 行情实体（只读）

### 2.1 `stock_daily_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_date` | 主键维度 |
| `open`, `close` | D1 开盘、买入日收盘、涨幅过滤、三连跌 |
| `macd_hist` | 红柱/绿柱、递增序列、红转绿止损 |

### 2.2 `stock_weekly_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_week_end` | 对齐键；取 `trade_week_end ≤ T_buy` 的最近一根 |
| `macd_hist` | 买入日周线共振（>0） |

### 2.3 `stock_monthly_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_month_end` | 对齐键；取 `trade_month_end ≤ T_buy` 的最近一根 |
| `macd_hist` | 买入日月线共振（>0） |

### 2.4 `stock_basic`

| 字段 | 用途 |
|------|------|
| `code`, `name` | 展示；剔除 ST/*ST（名称前缀） |

**前置条件**：周/月 bar 须已通过 `stock_indicator_fill_service` 写入 MACD；否则该标的买入候选跳过。

---

## 3. 策略运行时对象（非持久化）

| 名称 | 说明 |
|------|------|
| `_Params` | `gain_filter_pct=0.10`, `arm_profit_pct=0.10`, `trailing_drawdown_pct=0.03`, `stop_loss_pct=0.07` |
| `BacktestTrade` | `trigger_date == buy_date == D6` |
| `BacktestResult` | `trades`, `skipped_count`, 日志统计 |
| 周/月索引 | `dict[str, list[tuple[date, float]]]` 按 `stock_code` 预加载，二分取 `≤ T_buy` 最近 hist |

---

## 4. 校验规则摘要

- `buy_price` 必须等于 `trigger_date` 当日 `close`，**不得**用次日开盘。
- `trigger_date` 必须满足：D0 绿、D1…D6 红柱递增、三周期 MACD 红、`close(D6) ≥ open(D1)×1.10`。
- 平仓**监测与成交**均用**收盘价**；移动止盈未达 +10% 前不得因回撤 3% 平仓。
- 同标的**未平仓**不重复开仓；平仓后从 `sell_idx+1` 继续扫描。
