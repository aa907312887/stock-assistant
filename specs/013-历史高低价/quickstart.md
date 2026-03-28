# 快速上手：历史高低价（本地验证）

## 1. 前置条件

- MySQL 已按项目迁移脚本建库；`stock_basic`、`stock_daily_bar` 已有数据（至少部分股票有日线）。
- 后端依赖已安装（`backend` 目录 `uvicorn` 可启动）。

## 2. 数据库迁移

在数据库中执行：

```bash
# 示例：按项目惯例用 mysql 客户端执行
mysql -u... -p... your_db < backend/scripts/add_stock_basic_hist_extrema.sql
```

（脚本名以实现为准；执行前请备份。）

## 3. 首次全量极值（本机 CLI）

在仓库中进入 `backend` 目录（虚拟环境已激活、`PYTHONPATH` 含当前目录），执行：

```bash
cd backend
python -m app.scripts.recompute_hist_extrema_full
```

成功时控制台打印 `updated_rows`、`codes_with_daily` 与耗时。

## 4. 验证列表接口

```bash
curl -s "http://127.0.0.1:8000/api/stock/basic?page=1&page_size=5" | jq '.items[0] | {code, hist_high, hist_low, hist_extrema_computed_at}'
```

应能看到 `hist_*` 字段（有数据时为数字，无则为 `null`）。

## 5. 验证增量任务

- 启动后端，确认日志中出现 Scheduler 启动信息。
- 在**交易日**可观察 **18:00** 前后是否出现极值任务相关日志（`job_id` 以实现为准）；非交易日任务应快速跳过（与现有交易日判断一致）。
- 若不便等待定时器，可在开发环境临时调用服务层 `run_incremental_hist_extrema(...)`（以实现暴露方式为准）单次试跑。

## 6. 前端

打开「股票基本信息」页面，表格中应增加「历史最高价」「历史最低价」列；`null` 显示为「—」（与实现一致）。
