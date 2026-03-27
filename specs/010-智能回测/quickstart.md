# 本地运行与验证：智能回测

**日期**: 2026-03-26

## 前置条件

- 后端环境已搭建（Python + pip + MySQL），可运行 `uvicorn app.main:app`
- 前端环境已搭建（Node.js + npm），可运行 `npm run dev`
- 数据库中已有日线数据（`stock_daily_bar`）和股票基本信息（`stock_basic`）
- 已有至少一个策略在系统中注册（冲高回落战法）

## 步骤 1：建表

在 MySQL 中执行建表脚本：

```bash
mysql -u <用户名> -p <数据库名> < backend/scripts/add_backtest_tables.sql
```

验证：

```sql
SHOW TABLES LIKE 'backtest%';
-- 应看到 backtest_task、backtest_trade
```

## 步骤 2：启动后端

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 步骤 3：验证 API

### 3.1 获取可用数据范围

```bash
curl http://localhost:8000/api/backtest/data-range
```

预期返回：

```json
{
  "min_date": "2023-01-03",
  "max_date": "2026-03-25"
}
```

### 3.2 发起回测

```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": "chong_gao_hui_luo", "start_date": "2024-01-01", "end_date": "2024-12-31"}'
```

预期返回（202）：

```json
{
  "task_id": "bt-chong_gao_hui_luo-20240101-20241231-xxxxxxxx",
  "status": "running",
  "message": "回测任务已创建，后台执行中"
}
```

### 3.3 查询任务状态

等待数秒后：

```bash
curl http://localhost:8000/api/backtest/tasks
```

验证：返回的列表中包含刚创建的任务，状态从 `running` 变为 `completed` 或 `incomplete`。

### 3.4 查看绩效报告

```bash
curl http://localhost:8000/api/backtest/tasks/<task_id>
```

验证：返回包含 `report` 字段，含 `total_trades`、`win_rate`、`total_return` 等指标。

### 3.5 查看交易明细

```bash
curl "http://localhost:8000/api/backtest/tasks/<task_id>/trades?page=1&page_size=10"
```

验证：返回交易列表，每笔包含 `stock_code`、`buy_date`、`buy_price`、`sell_date`、`sell_price`、`return_rate`。

## 步骤 4：启动前端并验证

```bash
cd frontend
npm run dev
```

1. 打开浏览器访问 `http://localhost:5173`
2. 登录后在侧边栏找到「智能回测 → 历史回测」
3. 在页面中选择策略（冲高回落战法）、设定时间范围、点击"开始回测"
4. 验证：任务出现在列表中，状态从"运行中"变为"回测完成"
5. 点击"查看"，验证绩效报告与交易明细展示正确

## 验证清单

- [ ] 建表成功（`backtest_task`、`backtest_trade`）
- [ ] `GET /api/backtest/data-range` 返回正确的日期范围
- [ ] `POST /api/backtest/run` 返回 202 并创建任务
- [ ] 后台线程执行完成后 `backtest_task.status` 更新为 `completed` 或 `incomplete`
- [ ] `backtest_trade` 表中有交易记录
- [ ] 绩效指标（胜率、收益率等）可通过交易明细逐笔验算
- [ ] 同一配置重复回测，结果完全一致（确定性）
- [ ] 前端页面可正常发起回测、查看列表、查看详情
- [ ] 侧边栏菜单「智能回测 → 历史回测」可正常导航
