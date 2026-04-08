# 本地验证：历史模拟优化

## 1. 前置条件

- MySQL 中已存在 `simulation_task`、`simulation_trade` 表，并已执行迁移增加温度列。
- 库中已有 `market_temperature_daily` 数据（至少覆盖测试区间内的买入日）。
- 后端依赖安装完毕，`DATABASE_URL` 正确。

## 2. 迁移

在仓库根目录执行（以项目实际脚本为准）：

```bash
# 示例：执行新增列的 SQL
mysql -u ... stock_assistant < backend/scripts/add_simulation_trade_temperature.sql
```

或使用 Alembic 升级（若项目已接入）。

## 3. 启动服务

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

## 4. 接口抽检（需登录态与 Token）

1. **发起模拟**  
   `POST /api/simulation/run`，body：`strategy_id`、`start_date`、`end_date`。  
   返回 `202`，记录 `task_id`。

2. **轮询任务**  
   `GET /api/simulation/tasks/{task_id}`，直至 `status` 为 `completed` 或 `incomplete`。

3. **交易明细（带温度与年份筛选）**  
   `GET /api/simulation/tasks/{task_id}/trades?market_temp_levels=冷,温&exchanges=SSE&year=2024&page=1&page_size=50`  
   检查返回项中含 `market_temp_level`（新任务非空为主）。

4. **筛选复算**  
   `GET /api/simulation/tasks/{task_id}/filtered-report?market_temp_levels=冷&markets=__EMPTY__`  
   核对 `metrics` 与明细逐笔手算一致。

5. **分年分析**  
   `GET /api/simulation/tasks/{task_id}/yearly-analysis`  
   跨年任务应出现多行 `items`，每年 `win_rate`、`total_return` 可核对。

## 5. 前端

- 进入「智能回测 → 历史模拟」，完成任务后打开详情。
- 确认：筛选器含温度、年份；存在筛选后汇总或分年表格；Tooltip 说明与回测差异。

## 6. 回归

- 执行一次**历史回测**同策略、同区间，确认模拟笔数 ≥ 回测「闭仓成交」笔数（无资金跳过），且温度/板块/交易所字段分布合理。
