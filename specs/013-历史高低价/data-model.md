# 数据模型：历史高低价（Phase 1）

**关联规格**：[spec.md](./spec.md)  
**调研**：[research.md](./research.md)

## 1. 存储与关系

| 表 | 角色 |
|----|------|
| `stock_basic` | 主数据行扩展三列，存放历史最高价、历史最低价、极值计算时间。 |
| `stock_daily_bar` | 只读来源：`high`、`low`、`stock_code`、`trade_date`。 |

关系：`stock_basic.code` 与 `stock_daily_bar.stock_code` 字符串一致（同一代码体系）。

## 2. `stock_basic` 新增字段（迁移）

**迁移脚本建议路径**：`backend/scripts/add_stock_basic_hist_extrema.sql`（与现有 `add_*.sql` 风格一致）。

| 字段 | SQL 类型 | 可空 | 说明 |
|------|----------|------|------|
| `hist_high` | `DECIMAL(12,4)` | YES | 该股在 `stock_daily_bar` 全历史 `high` 的最大值。 |
| `hist_low` | `DECIMAL(12,4)` | YES | 全历史 `low` 的最小值。 |
| `hist_extrema_computed_at` | `DATETIME` | YES | 最近一次极值任务（增量或全量）成功写入该行的时间。 |

**校验规则**：

- 若该股在 `stock_daily_bar` 中**无任何行**：`hist_high`、`hist_low` 均为 `NULL`，`hist_extrema_computed_at` 可为 `NULL`。
- 若存在日线但 `high`/`low` 部分为 `NULL`：聚合时使用 SQL `MAX(high)`/`MIN(low)` 时忽略 `NULL` 行为（MySQL 语义）；若该股所有行为 `NULL`，结果仍为 `NULL`。

**索引**：一般无需为 `hist_high`/`hist_low` 单独建索引（列表排序未在规格中要求）；若后续有「按历史最高价排序」需求再评估。

## 3. SQLAlchemy 模型

在 `app.models.stock_basic.StockBasic` 上增加与上表一致的三列，类型使用 `Numeric(12, 4)` 与 `DateTime`，与 ORM 现有风格一致。

## 4. 聚合口径（与实现对应）

| 操作 | 口径 |
|------|------|
| **全量 CLI** | `SELECT stock_code, MAX(high), MIN(low) FROM stock_daily_bar GROUP BY stock_code` → 按 `code` 更新 `stock_basic`；无日线数据的 `code` 将极值列置 `NULL`（可选是否清空仅无数据的行，建议在服务层显式处理）。 |
| **增量定时** | 选定交易日 `T` 后，取集合 `S = { stock_code \| 存在 trade_date = T 的日线 }`，**仅对 `S` 中每个 code** 执行该股全历史 `MAX/MIN` 更新（或对 `S` 与聚合子查询 JOIN 批量 UPDATE）。 |

## 5. 与 `synced_at` 的区分

| 字段 | 含义 |
|------|------|
| `synced_at` | 股票**基础信息**从 Tushare 同步的时间。 |
| `hist_extrema_computed_at` | **极值**计算任务写入时间，独立演进。 |
