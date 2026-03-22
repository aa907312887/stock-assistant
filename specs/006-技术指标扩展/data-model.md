# 数据模型：技术指标扩展（均线与 MACD）

**规格**: [spec.md](./spec.md) | **计划**: [plan.md](./plan.md)

## 1. 概述

在 **不改变** 现有主键与唯一约束的前提下，为以下三张表增加**可空**数值列，用于存储与该行 K 线收盘后一致的指标（按「该行日期及之前历史」计算）。

| 表 | 日期列 | 唯一约束 |
|----|--------|----------|
| `stock_daily_bar` | `trade_date` | `(stock_code, trade_date)` |
| `stock_weekly_bar` | `trade_week_end` | `(stock_code, trade_week_end)` |
| `stock_monthly_bar` | `trade_month_end` | `(stock_code, trade_month_end)` |

## 2. 字段定义（三张表列名一致）

**类型建议**：`DECIMAL(16, 8)`（与 ORM `Numeric(16, 8)` 对齐），与 OHLC `Numeric(12,4)` 区分精度；若 DBA 要求统一，可降为 `DECIMAL(14,6)`，但须在验收中放宽误差。

| 列名 | 含义 | 说明 |
|------|------|------|
| `ma5` | 5 周期 SMA(close) | 不足 5 根有效收盘为 NULL |
| `ma10` | 10 周期 SMA(close) | 不足 10 根为 NULL |
| `ma20` | 20 周期 SMA(close) | 不足 20 根为 NULL |
| `ma60` | 60 周期 SMA(close) | 不足 60 根为 NULL |
| `macd_dif` | DIF | EMA12(close) − EMA26(close) |
| `macd_dea` | DEA | EMA9(DIF) |
| `macd_hist` | 柱 | 2 × (DIF − DEA) |

- **SMA**：\( \text{SMA}_n = \frac{1}{n}\sum_{i=0}^{n-1} \text{close}_{t-i} \)（含当日）。
- **EMA**：标准指数移动平均，平滑因子 \(\alpha = 2/(n+1)\)，**首值**采用业界常见做法：以第一根可用值为种子或以前若干根 SMA 预热（实现须在 `research.md` 与单元测试固定一种，全表一致）。
- **MACD 参数**：12、26、9（与规格一致）。

## 3. 空值与异常

- `close` 为 NULL：该行所有指标列保持 NULL，不参与向前滚动计算（或整段该标的跳过，实现二选一，**全库统一**）。
- 上市初期、历史长度不足：对应 `ma*` / `macd_*` 为 **NULL**。
- **禁止**用 0 填充表示「未计算」，避免与真实零值混淆（MACD 可接近 0）。

## 4. 索引

本期**不新增索引**（筛选下期才做）；若后续按指标列查询，再评估 `(stock_code, trade_date)` 与部分列组合索引。

## 5. 与同步元数据

可选：沿用 `sync_batch_id` / `synced_at` 表示行情同步批次；指标更新可：

- **方案 A**：指标更新**不修改** `synced_at`（仅改指标列 + `updated_at`），避免与 Tushare 同步语义混淆；
- **方案 B**：新增 `indicator_batch_id`（本期可不建，减少迁移面）。

**建议**：本期采用 **方案 A**，在日志中记录指标任务 `batch_id`。

## 6. ORM

在 `StockDailyBar` / `StockWeeklyBar` / `StockMonthlyBar` 上增加与上表一致的 `Mapped` 字段；`nullable=True`。
