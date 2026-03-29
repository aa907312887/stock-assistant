# 快速上手：历史高低价（本地验证）

## 1. 前置条件

- MySQL 已按项目迁移脚本建库；`stock_basic`、`stock_daily_bar` 已有数据（至少部分股票有日线）。
- 后端依赖已安装（`backend` 目录 `uvicorn` 可启动）。

## 2. 数据库迁移

在数据库中执行（**执行前请备份**）：

```bash
mysql -u... -p... your_db < backend/scripts/add_stock_daily_bar_cum_hist.sql
```

若库中仍有旧方案在 `stock_basic` 上的三列，在全量重算完成后再执行：

```bash
mysql -u... -p... your_db < backend/scripts/remove_stock_basic_hist_extrema.sql
```

## 3. 首次全量极值（本机 CLI）

在仓库中进入 `backend` 目录（虚拟环境已激活、`PYTHONPATH` 含当前目录），执行：

```bash
cd backend
python -m app.scripts.recompute_hist_extrema_full
```

成功时控制台打印 `updated_codes`、`updated_daily_rows` 与耗时。

## 4. 验证列表接口

```bash
curl -s "http://127.0.0.1:8000/api/stock/basic?page=1&page_size=5" | jq '.items[0] | {code, hist_high, hist_low, hist_extrema_computed_at}'
```

应能看到 `hist_*` 字段（有数据时为数字，无则为 `null`）。

## 5. 验证随日线写入的累计极值

- 执行一次带 `daily` 的同步（如 `python -m app.scripts.sync_stock` 或管理端 `POST /api/admin/stock-sync`），写入后查询该股**最新**与**当日**日线行的 `cum_hist_high` / `cum_hist_low`，应与按日递推口径一致。
- **无**独立 18:00 极值 Job；Scheduler 启动日志中不应再出现 `hist_extrema_incremental_daily`。

## 6. 前端

打开「股票基本信息」页面，表格中应增加「历史最高价」「历史最低价」列；`null` 显示为「—」（与实现一致）。
