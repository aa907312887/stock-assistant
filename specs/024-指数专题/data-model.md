# 数据模型：指数专题

**关联规格**: [`spec.md`](./spec.md) | **计划**: [`plan.md`](./plan.md)

本文描述本期推荐的关系型模型（MySQL）。实际 DDL 以 `backend/scripts/` 迁移脚本为准。

## 实体关系（概念）

```text
index_basic (1) ──< (N) index_daily_bar
                 ├──< (N) index_weekly_bar
                 ├──< (N) index_monthly_bar
                 └──< (N) index_weight
```

## `index_basic`

指数基本信息，对齐 Tushare `index_basic` 常用字段。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK AI | |
| ts_code | VARCHAR(32) | UNIQUE，索引 | Tushare 指数代码，如 `399300.SZ` |
| name | VARCHAR(128) | 可空 | 简称 |
| fullname | VARCHAR(255) | 可空 | 全称 |
| market | VARCHAR(16) | 索引 | SSE/SZSE/SW/CSI… |
| publisher | VARCHAR(64) | 可空 | 发布方 |
| index_type | VARCHAR(64) | 可空 | 指数风格 |
| category | VARCHAR(64) | 可空 | 类别 |
| base_date | DATE | 可空 | 基期 |
| base_point | DECIMAL(16,4) | 可空 | 基点 |
| list_date | DATE | 可空 | 发布日期 |
| weight_rule | VARCHAR(255) | 可空 | 加权方式 |
| description | TEXT | 可空 | 描述 |
| exp_date | DATE | 可空 | 终止日期 |
| data_source | VARCHAR(32) | 默认 tushare | |
| synced_at | DATETIME | 非空 | |

## `index_daily_bar`

指数日线 K 线，**列级对齐** `stock_daily_bar` 中与行情/指标相关的部分；价格为**指数点位**。

建议至少包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | |
| index_code | VARCHAR(32) 索引 | 与 `index_basic.ts_code` 一致 |
| trade_date | DATE 索引 | |
| open, high, low, close | DECIMAL(12,4) | 点位 |
| prev_close | DECIMAL(12,4) | 昨收点位，供涨跌幅与仿真展示；来源 Tushare `pre_close` |
| change_amount | DECIMAL(12,4) | 对应 `change` |
| pct_change | DECIMAL(10,4) | 对应 `pct_chg` |
| volume | DECIMAL(20,2) | 对应 `vol`（手，与个股口径展示一致） |
| amount | DECIMAL(20,2) | 对应 `amount`（千元→与个股统一量纲时按项目约定换算或原样存元） |
| amplitude | DECIMAL(10,4) | 可计算或与 Tushare 对齐 |
| ma5, ma10, ma20, ma60 | DECIMAL(16,8) | 同步管线填充 |
| macd_dif, macd_dea, macd_hist | DECIMAL(16,8) | 同上 |
| data_source, sync_batch_id, synced_at, created_at, updated_at | | 与个股 bar 一致 |

唯一约束：`UNIQUE(index_code, trade_date)`。

**说明**：现有 `market_index_daily_quote` 字段较少；长期以本表为主，`market_index_daily_quote` 可废弃或双写过渡期使用（见 `plan.md`）。

## `index_weekly_bar` / `index_monthly_bar`

对齐 `stock_weekly_bar` / `stock_monthly_bar` 的周期边界语义：

| 字段 | 说明 |
|------|------|
| index_code | 指数代码 |
| trade_week_end / trade_month_end | 周期结束日（与个股周月线命名一致） |
| open, high, low, close, volume, amount, … | 与日线同类指标列 |

唯一约束：`(index_code, trade_week_end)` / `(index_code, trade_month_end)`。

## `index_pe_percentile_snapshot`（可选，性能优化）

首期可在 API 层即时计算「指数 PE 百分位」（见 `plan.md`）。若composition 压力过大，可增加快照表：

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR(32) | 指数代码 |
| snapshot_trade_date | DATE | 个股 PE 百分位快照日 \(T\) |
| weight_as_of_date | DATE | 所用法权重记录的日期 |
| weighted_pe_percentile | DECIMAL(6,2) | 推理结果 0～100 |
| participating_weight_ratio | DECIMAL(6,4) | 参与加权的权重占原始总权重比例 |
| meta_json | TEXT | 可选调试信息 |

唯一约束建议：`(ts_code, snapshot_trade_date)`。

## `index_weight`

Tushare `index_weight`，月度更新。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | |
| index_code | VARCHAR(32) 索引 | 指数 ts_code |
| con_code | VARCHAR(32) | 成分 ts_code |
| trade_date | DATE | 权重生效日（按 Tushare 返回） |
| weight | DECIMAL(12,4) | 权重 |
| synced_at | DATETIME | |

唯一约束建议：`(index_code, con_code, trade_date)` 或通过业务确定。

## 与模拟交易表的关系

`paper_trading_position.stock_code`、`paper_trading_order.stock_code` **继续存字符串**，允许值为指数 `ts_code`（如 `399300.SZ`）。不在此处增加 FK，以保持与现有订单数据兼容。

## 索引建议

- `index_daily_bar`: `(index_code, trade_date)`、`trade_date`
- `index_basic`: `ts_code`（唯一）、`market`
