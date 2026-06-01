# 数据模型：早晨十字星（简化版）

**日期**：2026-05-03  
**说明**：**不新增**数据库表或列；复用「智能回测」「策略选股结果」与 `stock_daily_bar`。

---

## 1. 持久化实体（复用）

### 1.1 `backtest_task`

与 `specs/010-智能回测/data-model.md` 一致。`strategy_id` 新增取值：`zao_chen_shi_zi_xing_jian_hua`。

### 1.2 `backtest_trade`

与现有结构一致。本策略写入时：

| 字段 | 取值说明 |
|------|-----------|
| `trigger_date` | 第三根阳线日 **T**（形态完成日） |
| `buy_date` | **T 之后首个实际成交的开盘日**（通常为 T+1；停牌顺延则为更晚的交易日） |
| `buy_price` | 该日 **开盘价**（顺延则为顺延日开盘价） |
| `sell_date` / `sell_price` / `return_rate` | 触发止损/止盈时 **卖出价=触发日收盘价**；监测阈值 **−8%** / **+10%**（见 `spec.md`） |
| `trade_type` | `closed` / `unclosed` 语义同现有策略 |
| `extra` | JSON；建议含 `exit_reason`（`stop_loss_8pct` / `take_profit_10pct`）、三日形态日期、`cum_hist_high`、`max_close_to_cum_hist_high_ratio: 0.8`、`buy_rule`、`sell_rule` |

### 1.3 策略选股结果（若项目已有候选表）

与「早晨十字星」相同实体；通过 **`strategy_id`** 区分存储；字段语义：**信号对应触发日 T**，展示文案说明「买入拟在下一交易日开盘」。

---

## 2. 行情实体（只读）— `stock_daily_bar`

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_date` | 主键维度 |
| `open`, `high`, `low`, `close` | 形态、锤头、买入.open |
| `ma5`, `ma10`, `ma20` | 本策略**不用于触发**；可选落库展示 |
| `cum_hist_high` | **T** 日收盘 ≤ **0.8 × cum_hist_high** |

缺失任一方针所需字段时，该样本**不触发**。

---

## 3. 策略运行时对象（非持久化）

| 名称 | 说明 |
|------|------|
| `BacktestTrade` | `trigger_date` = **T**；`buy_date` 可与 `trigger_date` 不同（始终 ≥ T 的下一日历尝试）。 |
| `BacktestResult` | `trades` 列表 |
| `StrategyDescriptor` | `describe()` 供 `/api/strategies` 与前端展示 |

---

## 4. 校验规则摘要

- `trigger_date` 必须为第三根阳线日 **T**，不得与「首次站上 MA5」买入混淆（本策略**不用**该买入规则）。  
- `buy_date` 必须晚于或等于「T 的下一交易日」意图；若停牌顺延，`extra` 宜记 `buy_delay_trading_days` 便于核对。  
- 止损与止盈的**成交价均为触发日的收盘价**；监测阈值分别为相对买入价 **−8%** 与 **+10%**（见 `spec.md` FR-005）。
