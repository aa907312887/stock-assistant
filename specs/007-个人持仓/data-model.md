# 数据模型：个人持仓（007）

**功能**: 007-个人持仓 | **日期**: 2026-03-22 | **规格**: [spec.md](./spec.md)

## 概述

- **品种**：本期仅 **股票**，`stock_code` 与 `stock_basic` / `stock_daily_bar` 一致。
- **核心业务对象**：
  - **交易（一笔）**：`portfolio_trade`，生命周期 `open` → `closed`。
  - **操作记录**：`portfolio_operation`，隶属于一笔交易。
  - **复盘图片**：`portfolio_trade_image`（仅 `status=closed` 后上传；也可允许闭市后编辑，见接口）。

## 实体关系

```text
user (已有)
  └── portfolio_trade (1:N)
         └── portfolio_operation (1:N)
         └── portfolio_trade_image (0:N，建议仅 closed 后使用)
```

- **同一用户 + 同一股票**：**最多一笔 `open` 状态**的交易（应用层校验 + 查询保证；如需 DB 约束可后续加可编辑触发器，本期以应用层为准）。

## 表：portfolio_trade

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT PK AI | 必填 | 主键 |
| user_id | BIGINT | 必填，索引 | 关联 `user.id` |
| stock_code | VARCHAR(20) | 必填，索引 | 股票代码 |
| status | ENUM('open','closed') | 必填，默认 open | 是否已清仓完结 |
| opened_at | DATETIME | 必填 | 首笔建仓时间（首条 open 操作时间，可与首操作同步） |
| closed_at | DATETIME | 可空 | 清仓完成时间 |
| avg_cost | DECIMAL(18,6) | 可空 | **当前未清倉时**加权平均成本（冗余，便于展示；每次操作后更新） |
| total_qty | DECIMAL(20,6) | 可空 | **当前**持仓数量；closed 时应为 0 |
| total_cost_basis | DECIMAL(24,6) | 可空 | 持仓成本基数（买入类累计 − 卖出按价冲减），用于加权平均成本 |
| accumulated_realized_pnl | DECIMAL(20,6) | 默认 0 | 未平仓前卖出已实现的盈亏累计（减仓时更新） |
| realized_pnl | DECIMAL(20,6) | 可空 | **closed 时**整笔已实现盈亏（关闭时写入） |
| review_text | TEXT | 可空 | 复盘文字 |
| manual_realized_pnl | DECIMAL(20,6) | 可空 | 可选：用户手工覆盖整笔盈亏（与自动计算冲突时以业务规则为准，本期可**不实现**，预留列） |
| created_at | DATETIME | 必填 | |
| updated_at | DATETIME | 必填 | |

**索引建议**：

- `INDEX idx_pt_user_stock_open (user_id, stock_code, status)` — 查当前是否有未完结同股交易。
- `INDEX idx_pt_user_closed (user_id, closed_at)` — 已完结列表。

**校验规则**：

- `status=closed` 时：`closed_at` 必填，`total_qty=0`，`realized_pnl` 应有值（除非允许 0 盈亏）。
- `stock_code` 须在 `stock_basic` 存在（插入/更新时校验）。

## 表：portfolio_operation

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT PK AI | 必填 | 主键 |
| trade_id | BIGINT | 必填，索引 | `portfolio_trade.id` |
| user_id | BIGINT | 必填，索引 | 冗余，便于按用户直接查操作 |
| op_type | ENUM('open','add','reduce','close') | 必填 | 操作类型 |
| op_date | DATE | 必填 | 成交日 |
| qty | DECIMAL(20,6) | 必填 | 数量，**正数**；语义为「股数」 |
| price | DECIMAL(18,6) | 必填 | 单价 |
| amount | DECIMAL(20,6) | 可空 | 成交金额，可推导 `qty*price` 或含费 |
| fee | DECIMAL(20,6) | 可空 | 手续费，默认 0 |
| operation_rating | ENUM('good','bad') | 可空 | 操作自评；空=未评价 |
| note | VARCHAR(512) | 可空 | 操作备注 |
| created_at | DATETIME | 必填 | |
| updated_at | DATETIME | 必填 | |

**业务规则**：

- 首条操作必须为 `open`（建仓），且该 `trade` 仅允许一条 `open`。
- `add` / `reduce` / `close` 须在 `open` 之后按时间或录入顺序合法（持仓不能减为负）。
- `close`：应使 `total_qty` 变为 0，随后将 `trade.status` 置为 `closed` 并写 `realized_pnl`。

**加权成本**：与 `research.md` 一致，服务端在每次操作提交后重算 `avg_cost`、`total_qty`；清仓时汇总 `realized_pnl`。

## 表：portfolio_trade_image

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT PK AI | 必填 | |
| trade_id | BIGINT | 必填，索引 | 仅关联已 `closed` 的 trade（应用层校验） |
| user_id | BIGINT | 必填 | 冗余 |
| file_path | VARCHAR(512) | 必填 | 相对 `uploads/portfolio` 或存储根的路径 |
| mime_type | VARCHAR(64) | 必填 | |
| size_bytes | INT | 必填 | |
| sort_order | INT | 默认 0 | 展示顺序 |
| created_at | DATETIME | 必填 | |

删除图片时**同步删除磁盘文件**（或异步清理任务，本期同步删除即可）。

## 引用表（只读）

- **`stock_basic`**：校验代码、展示名称。
- **`stock_daily_bar`**：取 `max(trade_date)` 的 `close` 作为参考市值。

## 胜率统计（查询时计算）

- **股票胜率**：`status=closed` 且 `realized_pnl` 非空的记录中，`realized_pnl > 0` 的比例；分母不含 `realized_pnl` 为 NULL 的 closed（应禁止出现，除非异常数据）。
- **操作胜率**：`operation_rating IN ('good','bad')` 的记录中，`good` 占比；分母仅含已评价；界面同时返回 `rated_count` / `total_operations`。

## 状态流转

```text
portfolio_trade: open ──(清仓成功)──> closed
```

- 删除「当前持仓」：等价删除 `open` 的 `trade` 及其 `operations`（需用户确认），规格验收场景 4；若业务希望保留审计，可改为软删除 `is_deleted`（本期硬删除即可，自用）。
