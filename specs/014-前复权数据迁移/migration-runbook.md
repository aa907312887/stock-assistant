# 前复权迁移 Runbook（FR-006）

本文档与 [quickstart.md](./quickstart.md) 交叉引用，供运维在**维护窗口**执行清空与回灌。

## 1. 前置条件

- 已完成代码发布：日线 `pro_bar` qfq、周/月 `stk_week_month_adj`、探测接口已上线。
- `backend/.env`：`TUSHARE_TOKEN`、`ADMIN_SECRET` 有效。
- **MySQL 全库或逻辑备份**已完成，备份路径与责任人已记录。

## 2. 清空（仅行数据）

```bash
mysql -u ... -p stock_assistant < backend/scripts/truncate_for_qfq_migration.sql
```

**禁止**对业务库执行无备份的 `TRUNCATE`。若需保留 `sync_job_run` 审计，可先导出再 `TRUNCATE`。

## 3. 回灌主路径

1. **股票主档 + 日/周/月**（示例区间请按环境调整）：

```bash
curl -sS -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode":"backfill","modules":["basic","daily","weekly","monthly"],"start_date":"2010-01-01","end_date":"2026-12-31"}' \
  "http://127.0.0.1:8000/api/admin/stock-sync"
```

2. **均线/MACD**（若编排未跑满）：

```bash
curl -sS -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode":"full","timeframes":["daily","weekly","monthly"]}' \
  "http://127.0.0.1:8000/api/admin/stock-indicators"
```

3. **大盘温度**：依赖指数日线，可调用应用内 `run_incremental_temperature_job` 或等待定时 17:10；详见 `backend/app/services/market_temperature/`。

4. **历史极值**：全量迁移后建议执行一次全历史重算（依赖已前复权的 `stock_daily_bar`）：

```bash
cd backend && python -m app.scripts.recompute_hist_extrema_full
```

日常仍可由定时任务 `run_incremental_for_trade_date` 增量更新。

5. **策略选股**：数据就绪后由定时 17:20 或手动 `execute_strategy` 重算。

## 4. 回滚

- 从备份恢复整库；或再次执行清空并重新回灌（耗时长）。
- 不建议仅删除部分表导致口径不一致。

## 5. 生产执行记录（T014）

| 字段 | 填写 |
|------|------|
| 执行时间 | |
| batch_id（stock-sync） | |
| 耗时（估算） | |
| 执行人 | |

## 6. 验收（T015～T017）

- **温度**：大盘温度页与 `market_temperature_daily` 抽样一致。
- **策略**：策略结果表有新数据且无长期 `StrategyDataNotReadyError`。
- **极值**：抽样 `stock_basic` 极值与日线前复权全序列一致。

## 7. 已知问题 / 耗时

- 全市场日线按标的请求 `pro_bar`，全历史回灌可能需**数小时至数日**，取决于 Tushare 限流与机器性能；可分批缩短 `end_date` 或分多窗口执行。
- `stk_week_month_adj` 需足够积分；单次 6000 行上限时按周/月末分批已在线下逻辑处理。
