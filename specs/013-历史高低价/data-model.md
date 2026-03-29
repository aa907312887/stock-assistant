# 数据模型：历史高低价（Phase 1，修订）

**关联规格**：[spec.md](./spec.md)  
**调研**：[research.md](./research.md)

## 1. 存储与关系

| 表 | 角色 |
|----|------|
| `stock_daily_bar` | **读写**：每行 `trade_date` 存 `cum_hist_high` / `cum_hist_low`（截至该日含扩展极值）；**读** `high`、`low` 作递推来源。 |
| `stock_basic` | **不存**全表终态极值列（避免回测泄露未来）；列表展示用极值由接口连**最新日线**派生。 |

关系：`stock_basic.code` 与 `stock_daily_bar.stock_code` 字符串一致。

## 2. `stock_daily_bar` 新增字段（迁移）

**迁移脚本**：`backend/scripts/add_stock_daily_bar_cum_hist.sql`

| 字段 | SQL 类型 | 可空 | 说明 |
|------|----------|------|------|
| `cum_hist_high` | `DECIMAL(12,4)` | YES | 截至该 `trade_date`（含）所有已遍历日中 `high` 的扩展最大值。 |
| `cum_hist_low` | `DECIMAL(12,4)` | YES | 截至该日（含）`low` 的扩展最小值。 |

**校验规则**：

- 按 `stock_code` + `trade_date` 升序递推；当日 `high`/`low` 为 `NULL` 时不更新对应扩展极值（列取当前已形成的扩展值，可为 `NULL` 直至首笔有效价）。

**索引**：一般无需单独为两列建索引；若回测按 `(stock_code, trade_date)` 查已有主键/唯一键覆盖。

## 3. 移除 `stock_basic` 旧列（已有库升级）

**脚本**：`backend/scripts/remove_stock_basic_hist_extrema.sql`（删除 `hist_high`、`hist_low`、`hist_extrema_computed_at`）。

新建库可使用已更新的 `reset_and_init_v3.sql`，其中 `stock_basic` 不再含上述三列。

## 4. SQLAlchemy 模型

- `StockDailyBar`：`cum_hist_high`、`cum_hist_low` → `Numeric(12, 4)`。  
- `StockBasic`：不包含极值列。

## 5. 聚合口径（与实现对应）

| 操作 | 口径 |
|------|------|
| **全量 CLI** | 对每个 `stock_code`，按 `trade_date` 升序遍历行，维护扩展 max/min，逐行 UPDATE `cum_hist_*`。 |
| **增量定时** | 交易日 `T` 上有日线的每个 `code`，对该 code **全部日线行**重算并写回（保证历史修订后仍一致）。 |

## 6. 列表接口与 `synced_at`

| 字段 | 含义 |
|------|------|
| `GET /api/stock/basic` 的 `hist_high` / `hist_low` | 等于该 code **最新 `trade_date`** 行上的 `cum_hist_high` / `cum_hist_low`（仅展示语义）。 |
| `hist_extrema_computed_at` | 取上述最新日线行的 `updated_at`（极值列变更会触发行更新）。 |
| `stock_basic.synced_at` | 仍为股票基础信息同步时间，与极值独立。 |
