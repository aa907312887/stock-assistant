# 数据模型：策略选股（为未来回测预留）

## 1. 设计目标

- 本期仅交付“策略选股”的执行与结果展示，但必须沉淀可复用数据，保证未来接入“历史回测”时不返工。
- 策略本身以代码实现，不要求把策略规则存成可编辑 DSL；但必须记录“执行时使用的策略版本与口径”。

## 2. 复用现有数据表

冲高回落战法基于日线数据计算，复用：

- `stock_daily_bar`：股票日线（包含 `trade_date/open/high/close/prev_close/pct_change` 等）
- `stock_basic`：股票基础信息（名称等）

## 3. 新增表（本期交付）

### 3.1 策略执行快照表：`strategy_execution_snapshot`

**用途**：记录一次策略执行的元信息、参数与数据口径，作为未来回测与复现的最小输入。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK，自增 | 主键 |
| execution_id | VARCHAR(64) | UK | 对外展示/接口引用的执行编号（可用 UUID） |
| strategy_id | VARCHAR(64) | IDX | 策略稳定标识（如 `chong_gao_hui_luo`） |
| strategy_version | VARCHAR(32) |  | 策略版本（如 `v1.0.0`） |
| market | VARCHAR(16) |  | 固定 `A股` |
| as_of_date | DATE | IDX | 截止时间点（本次执行基于哪一交易日的数据） |
| timeframe | VARCHAR(16) |  | 本期固定 `daily`（为未来周/月策略预留） |
| params_json | JSON |  | 执行参数（例如阈值、窗口长度；本期可为空/默认） |
| assumptions_json | JSON |  | 口径与假设（例如“开盘口径=日线开盘价”“回落比例=(high-close)/high”） |
| data_source | VARCHAR(32) |  | 如 `tushare`（与行情表保持一致口径） |
| created_at | DATETIME |  | 创建时间 |

**索引建议**：

- `UK(execution_id)`
- `IDX(strategy_id, as_of_date)`
- `IDX(as_of_date)`

### 3.2 候选结果明细表：`strategy_selection_item`

**用途**：存储本次执行产出的候选股票列表，便于前端分页、复用与审计。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK，自增 | 主键 |
| execution_id | VARCHAR(64) | IDX | 关联 `strategy_execution_snapshot.execution_id` |
| stock_code | VARCHAR(20) | IDX | 股票代码 |
| trigger_date | DATE |  | 触发日（第 0 天） |
| summary_json | JSON |  | 结果摘要（例如回落比例、涨幅、是否满足第 1 天低开等） |
| created_at | DATETIME |  | 创建时间 |

**索引建议**：

- `IDX(execution_id)`
- `IDX(stock_code, trigger_date)`
- `UK(execution_id, stock_code)`（避免重复写入）

### 3.3 信号事件表：`strategy_signal_event`

**用途**：记录策略在某股票某时间点产生的信号，用于未来回测复用（入场/离场/过滤等）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK，自增 | 主键 |
| execution_id | VARCHAR(64) | IDX | 关联执行快照 |
| stock_code | VARCHAR(20) | IDX | 股票代码 |
| event_date | DATE | IDX | 事件发生的交易日 |
| event_type | VARCHAR(32) | IDX | `trigger`/`entry`/`exit`/`filter`/`note` |
| event_payload_json | JSON |  | 事件详情（阈值、判定、归因信息） |
| created_at | DATETIME |  | 创建时间 |

**索引建议**：

- `IDX(execution_id, stock_code)`
- `IDX(stock_code, event_date)`

## 4. 与未来回测的关系（不在本期交付）

未来回测可复用：

- 执行快照：确定策略版本、截止时间点、阈值口径
- 信号事件：确定入场/离场时点与事件序列
- 候选明细：作为触发集合或事件对照

回测新增表（未来）可通过 `execution_id` 或 `strategy_id + strategy_version + 区间` 建立关联，不破坏本期结构。

