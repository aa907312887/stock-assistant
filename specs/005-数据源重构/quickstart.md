# 快速开始：数据源重构

**功能**: 005-数据源重构 | **日期**: 2026-03-21

## 1. 前置准备

- 已在 `backend/.env` 中配置：
  - `DATABASE_URL`
  - `TUSHARE_TOKEN`
  - `ADMIN_SECRET`
- 已安装后端依赖和前端依赖
- 已确认本次允许**删除旧数据并重建**

## 2. 重建数据库

执行新的初始化脚本（文件名按最终实现为准，当前计划建议为 `reset_and_init_v3.sql`）：

```bash
mysql -u root -p < backend/scripts/reset_and_init_v3.sql
```

完成后应具备以下核心表：

- `stock_basic`
- `stock_daily_bar`
- `stock_weekly_bar`
- `stock_monthly_bar`
- `stock_financial_report`
- `sync_job_run`

## 3. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --reload
```

验证接口：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

## 4. 触发一次增量同步

```bash
curl -X POST "http://127.0.0.1:8000/api/admin/stock-sync" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Secret: your-secret" \
  -d '{
    "mode": "incremental",
    "modules": ["basic", "daily", "weekly", "monthly", "financial"]
  }'
```

预期返回：

```json
{
  "status": "started",
  "batch_id": "stock-20260321-170001",
  "mode": "incremental",
  "message": "同步任务已触发"
}
```

## 5. 执行一次历史回灌

```bash
cd backend
python -m app.scripts.sync_stock --mode backfill --start-date 2025-01-01 --end-date 2025-12-31
```

说明：
- 历史回灌建议分阶段执行
- 推荐先 `basic + daily`，再执行 `weekly + monthly`，最后执行 `financial`

## 6. 验证数据库结果

### 6.1 历史日线

```sql
SELECT stock_code, trade_date, close, pe, pe_ttm, pb, dv_ratio
FROM stock_daily_bar
ORDER BY trade_date DESC, stock_code
LIMIT 20;
```

### 6.2 周线 / 月线

```sql
SELECT stock_code, trade_week_end, close
FROM stock_weekly_bar
ORDER BY trade_week_end DESC
LIMIT 20;

SELECT stock_code, trade_month_end, close
FROM stock_monthly_bar
ORDER BY trade_month_end DESC
LIMIT 20;
```

### 6.3 同步任务日志

```sql
SELECT batch_id, job_name, job_mode, status, daily_rows, weekly_rows, monthly_rows, report_rows
FROM sync_job_run
ORDER BY started_at DESC
LIMIT 20;
```

## 7. 验证选股接口

先登录获取 token 或沿用当前项目登录方式，然后调用：

```bash
curl "http://127.0.0.1:8000/api/stock/screening?page=1&page_size=20&pe_min=1&pb_max=3"
```

重点检查：
- `data_date` 是否为最近历史日线日期
- 返回字段中是否包含 `pe`、`pe_ttm`、`pb`、`dv_ratio`
- `price` 是否等于 `close`

## 8. 验证监控接口

```bash
curl "http://127.0.0.1:8000/api/admin/sync-jobs?page=1&page_size=20" \
  -H "X-Admin-Secret: your-secret"
```

重点检查：
- 是否能看到最新 `batch_id`
- 失败任务是否有 `error_message`
- `daily_rows` / `weekly_rows` / `monthly_rows` / `report_rows` 是否有值

## 9. 验证定时任务

- 启动应用后，确认 [backend/app/core/scheduler.py](../../backend/app/core/scheduler.py) 已注册 17:00 任务
- 到达 17:00 后检查：
  - `sync_job_run` 中是否新增一条任务记录
  - `backend/logs/app.log` 中是否有开始/结束日志
  - 非交易日是否被记录为 `skipped`

## 10. 验收重点

- 旧表已删除，系统不再依赖 `stock_daily_quote`
- 日线数据为**历史日线**，最新值不超过当日收盘后结果
- 选股接口能直接读取日线主表中的估值字段
- 任务监控页面所需数据已能通过 `sync_job_run` 查询
