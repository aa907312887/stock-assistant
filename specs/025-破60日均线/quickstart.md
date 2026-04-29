# 快速验证：破 60 日均线买入法

**适用对象**：在本地已能跑起 **backend**（含 DB、已同步日线、含 `ma60` 字段）的开发者。

## 1. 后端依赖

- **策略注册**：`registry.list_strategies()` 含 `ma60_five_day_break`。
- **无新表**；`stock_daily_bar` 在目标区间有数据即可。

## 2. 验证策略是否可见

```bash
# 需已登录后携带 Token，或按项目既有方式
curl -sS -H "Authorization: Bearer <TOKEN>" "http://127.0.0.1:8000/api/strategies" | jq .
```

在返回 `items` 中查找 `strategy_id == "ma60_five_day_break"`。

## 3. 发起一次回测

将 `start_date` / `end_date` 设在 DB 有数据的区间内：

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/backtest/run" \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "ma60_five_day_break",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "position_amount": 100000,
    "reserve_amount": 100000
  }'
```

预期：**HTTP 202** 且 `task_id` 非空；随后用既有「任务列表/详情/交易明细」接口核对 `trigger_date`、`buy_date` 为**信号日/次日**、`buy_price` 为**次日开盘**、卖出在 **±8% 收盘价**首次触达日（**先损后盈**）。

## 4. 单元测试（实现阶段）

```bash
cd backend
pytest tests/test_ma60_five_day_break.py -q
```

（`tasks.md` 中落地具体文件名；此处为占位。）

## 5. 前端

在「历史回测」或「智能回测」页的策略下拉里出现「破60日均线买入法」即视为接入完成；**无需**新路由即可验收 P1。
