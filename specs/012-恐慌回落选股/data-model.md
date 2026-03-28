# 数据模型：恐慌回落选股

**说明**：第一版**不新增业务表**；延续现有策略选股落库结构。本节描述**已有表**在本功能中的用法及**API 层字段**约定。

## 1. 已有表（复用）

### 1.1 `strategy_execution_snapshot`

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | VARCHAR(64) PK 逻辑唯一 | 格式沿用现有：`{strategy_id}-{as_of_date ISO}-{version}` |
| `strategy_id` | VARCHAR(64) | 恐慌回落固定为 `panic_pullback` |
| `strategy_version` | VARCHAR(32) | 与策略类 `version` 一致（如 `v1.0.0`） |
| `market` | VARCHAR(16) | 固定语义「A股」 |
| `as_of_date` | DATE | 数据截止交易日 |
| `timeframe` | VARCHAR(16) | `daily` |
| `params_json` | JSON | 策略参数快照 |
| `assumptions_json` | JSON | 口径假设 + `generated_at` 等 |

**关系**：一对多 `strategy_selection_item`、`strategy_signal_event`。

### 1.2 `strategy_selection_item`

| 字段 | 类型 | 说明 |
|------|------|------|
| `execution_id` | VARCHAR(64) | 外键语义关联快照 |
| `stock_code` | VARCHAR(20) | 证券代码 |
| `trigger_date` | DATE | 触发日（信号日） |
| `summary_json` | JSON | 策略附加指标（跌幅、放量、可选收益率等）；**不存** `exchange`/`market`（来源 `stock_basic`） |

**约束**：`(execution_id, stock_code)` 唯一。

### 1.3 `stock_basic`（只读关联）

| 字段 | 用途（本功能） |
|------|----------------|
| `code` | 与 `stock_code` 关联 |
| `name` | 展示名称 |
| `exchange` | SSE / SZSE / BSE，**交易所筛选** |
| `market` | 主板 / 创业板 / 科创板 / 北交所等，**板块筛选**；空值参与「空板块」 |

## 2. API 视图对象（非新表）

响应中每条候选在现有 `StrategySelectionItem` 上**扩展**（见 `contracts/`）：

- `exchange`：`string | null`，对应 `stock_basic.exchange`
- `market`：`string | null`，对应 `stock_basic.market`
- `exchange_type`：保留，可选，用于兼容旧页；建议新页不依赖其语义

**校验规则**：

- `trigger_date` 必有，且与快照 `as_of_date` 在同一次执行中一致（恐慌回落单日扫描下相等）。
- 组装 `items` 时若某 `stock_code` 在 `stock_basic` 中不存在，视为**数据异常**；与规格「整体失败」对齐的实现策略为：执行路径中应保证扫描范围与基础表一致，若仍缺失则该条可跳过或整次失败——**实现阶段优先与现有 `execute_strategy` 行为一致**（当前策略基于日线表，一般均有基础信息）。

## 3. 状态与流转

- **无独立状态机**：快照创建即为一次完整执行；重复执行同一 `(strategy_id, as_of_date, version)` 时，现有逻辑**先删后插**同 `execution_id` 的明细与事件，再写入新结果。

## 4. 与 `011` 的一致性

- 触发判定与回测共用 `PanicPullbackStrategy._run_backtest` / `_select_trigger_day` 路径，不在本功能中复制公式。
