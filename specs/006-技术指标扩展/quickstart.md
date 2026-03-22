# 快速开始：技术指标扩展（验证）

**规格**: [spec.md](./spec.md) | **计划**: [plan.md](./plan.md)

## 前置

- MySQL 已存在 `stock_daily_bar` / `stock_weekly_bar` / `stock_monthly_bar` 且有样本数据。
- 已执行本期数据库迁移（指标列已存在）。

## 本地验证步骤

1. **单元测试**（工作目录为 `backend`）：`pytest tests/test_technical_indicator.py -q`，确认 SMA/MACD 与黄金样本一致。
2. **小样本回填**：

   ```bash
   cd backend && python -m app.scripts.fill_stock_indicators --mode backfill --timeframe daily --start-date 2024-01-01 --end-date 2024-12-31 --limit 5
   # 全表每标的全部 K 线（日/周/月需分别跑或一次指定多周期）：
   # python -m app.scripts.fill_stock_indicators --mode full
   ```

3. **SQL 抽检**：任选一只股票、最近一日：

   ```sql
   SELECT trade_date, close, ma5, ma10, ma20, ma60, macd_dif, macd_dea, macd_hist
   FROM stock_daily_bar
   WHERE stock_code = '000001.SZ'
   ORDER BY trade_date DESC
   LIMIT 5;
   ```

4. **任务链**：执行 `execute_pending_auto_sync`（含 `daily`→`weekly`→`monthly`），确认日志中出现指标填充或 `stock_indicator_fill_service` 无异常；**不再**使用单独的 `indicators` 子任务类型。

## 完成标准（与规格 SC 对齐）

- 抽检误差在验收约定阈值内；
- 增量后最新 bar 指标已更新；
- 失败任务可在 `sync_task` / 日志中定位。
