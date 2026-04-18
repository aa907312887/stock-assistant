# 数据模型：60 日均线买入法（历史回测）

**日期**: 2026-04-16  
**说明**: 本功能**不新增**数据库表；仅只读/写入既有实体。下列为与实现相关的字段与关系说明。

---

## 1. 只读：`stock_daily_bar`（日线 K 线）

| 字段 | 类型（概念） | 用途 |
|------|----------------|------|
| `stock_code` | 字符串 | 分组键 |
| `trade_date` | 日期 | 排序与信号日 / 买入日定位 |
| `open` | 数值，可空 | **买入价**（信号日次日开盘价） |
| `close` | 数值 | 卖出监测价；信号日 K 线需有值以便与其它策略一致落库 |
| `ma5` / `ma10` / `ma20` | 数值，可空 | 信号日 **多头排列** 判定 |
| `ma60` | 数值，可空 | MA60 序列；与前一交易日差分为斜率 |

**校验规则**：

- `ma60`、`close` 任一为空时，该日不参与斜率或信号判定。  
- 信号日须 `ma5`、`ma10`、`ma20` 均非空且满足 `ma5>ma10>ma20`；买入日须 `open` 有效且 `>0`，否则不成交。  
- 斜率等于 0 不满足 spec 中严格「正/负」条件。

**索引**：沿用表上 `(stock_code, trade_date)` 唯一约束与索引（无需本功能新增）。

---

## 2. 只读：`stock_basic`（证券主数据）

| 字段 | 用途 |
|------|------|
| `code` | 与 `stock_daily_bar.stock_code` 关联 |
| `name` | 判断是否 ST / *ST（名称前缀） |
| `exchange` / `market` | 回测引擎在落库后 `enrich_trades_with_stock_dimension` 已会补充至 `BacktestTrade`，本策略无需特殊处理 |

---

## 3. 写入：`backtest_task`（回测任务）

与现网一致：一次 `POST /api/backtest/run` 创建一行；`strategy_id` 取固定字面量 **`ma60_slope_buy`**；`strategy_description` 由引擎从 `STRATEGY_DESCRIPTIONS['ma60_slope_buy']` 快照写入。

**状态流转**：与现有任务相同（运行中 → 完成/失败等），本功能不改变状态机。

---

## 4. 写入：`backtest_trade`（回测成交明细）

与现网一致字段映射，本策略约定：

| 逻辑含义 | 典型落库来源 |
|----------|----------------|
| `trigger_date` | 转折日 \(t\)（`s` 由负转正日） |
| `buy_date` | 确认日 \(t+1\) |
| `buy_price` | \(t+1\) 日收盘价 |
| `sell_date` / `sell_price` | 止盈/止损触发日收盘价；未触发则空 |
| `trade_type` | `closed` / `unclosed` |
| `extra_json`（若项目使用 JSON 扩展） | 三日斜率、`exit_reason` 等 |

**关系**：多行 `backtest_trade` 归属同一 `task_id`（外键语义以现有 ORM 为准）。

---

## 5. 策略执行快照（选股落库，若启用）

若使用既有 `strategy_execution` / 明细表（与 `POST /api/strategies/{id}/execute` 配套），本策略不产生新实体类型；仅多一种 `strategy_id` 取值。具体表名以 `strategy_execute_service` 实现为准，**本功能不要求改表结构**。
