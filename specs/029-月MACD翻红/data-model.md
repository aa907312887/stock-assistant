# 数据模型：月 MACD 翻红

**日期**：2026-06-06  
**说明**：**不新增**数据库表或列；复用日/月线 bar 表与智能回测/历史模拟实体。

---

## 1. 持久化实体（复用）

### 1.1 `simulation_task` / `simulation_trade`（主场景）

与 `specs/018-历史模拟优化/data-model.md` 一致。`strategy_id` 新增取值：`yue_macd_fan_hong`。

| 字段 | 取值说明 |
|------|-----------|
| `strategy_id` | `yue_macd_fan_hong` |
| `strategy_description` | 自 `STRATEGY_DESCRIPTIONS` 快照 |
| `assumptions_json` | 含 `portfolio_simulation_applied: false` 等现网字段 |

### 1.2 `simulation_trade`

| 字段 | 取值说明 |
|------|-----------|
| `trigger_date` | **T_buy**（首个红柱月最后交易日，与 `buy_date` 相同） |
| `buy_date` | **T_buy** |
| `buy_price` | **T_buy 当日收盘价** |
| `sell_date` / `sell_price` | 触发平仓日的 **收盘价** |
| `return_rate` | 由买卖收盘价计算 |
| `trade_type` | `closed` / `unclosed` |
| `extra_json` | JSON；建议字段见下表 |

### 1.3 `backtest_task` / `backtest_trade`

与 `specs/010-智能回测/data-model.md` 一致；字段语义与 `simulation_trade` 相同。回测额外可能有 `trade_type=not_traded`（引擎层，非策略产出）。

#### `extra` / `extra_json` 建议字段

| 键 | 类型 | 说明 |
|----|------|------|
| `exit_reason` | string | `take_profit_20pct` / `stop_loss_20pct` / `sell_monthly_macd_red_to_green` |
| `buy_month_end` | string (ISO date) | 买入月 `trade_month_end` |
| `prev_month_end` | string | 绿转红前一月 `trade_month_end` |
| `macd_hist_buy_month` | number | 买入月 hist |
| `macd_hist_prev_month` | number | 前一月 hist |
| `sell_month_end` | string | 月线红转绿卖出时的 `trade_month_end`（若适用） |
| `buy_rule` | string | 固定 `month_first_red_last_day_close` |
| `sell_rule` | string | 固定 `close_triggered_multi_exit` |

---

## 2. 行情实体（只读）

### 2.1 `stock_daily_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_date` | 主键维度 |
| `close` | 买入价、±20% 止盈止损、成交价 |
| （间接） | 推导各月 `last_trade_date` |

### 2.2 `stock_monthly_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_month_end` | 主键；按升序扫描绿转红/红转绿 |
| `macd_hist` | 月 MACD 颜色判定 |

### 2.3 `stock_basic`

| 字段 | 用途 |
|------|------|
| `code`, `name`, `market` | 展示；**仅 `market == "主板"`**；剔除 ST/*ST |

**前置条件**：月线 bar 须已通过 `stock_indicator_fill_service` 写入 MACD；否则该标的买入候选跳过。

---

## 3. 策略运行时对象（非持久化）

| 名称 | 说明 |
|------|------|
| `_Params` | `take_profit_pct=0.20`, `stop_loss_pct=0.20` |
| `monthly_series` | `list[tuple[date, float]]` — `(trade_month_end, macd_hist)` 升序 |
| `month_last_trade` | `dict[date, date]` — `trade_month_end → 该月最后交易日` |
| `BacktestTrade` | `trigger_date == buy_date == T_buy` |
| `BacktestResult` | `trades`, `skipped_count` |

---

## 4. 校验规则摘要

- `buy_price` 必须等于 `trigger_date` 当日 `close`，**不得**用次日开盘或 `trade_month_end` 强行代替无 K 线日。
- 买入须满足：前一月绿、当月红；`T_buy` 为当月最后交易日。
- 平仓**监测与成交**均用**收盘价**；月线红转绿仅在 **买入月之后** 的月末判定。
- 同标的**未平仓**不重复开仓；平仓后继续扫描后续绿转红对。
- 历史模拟与回测共用同一 `BacktestTrade` 列表生成逻辑。
