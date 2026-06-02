# 快速上手：多周期 MACD 共振主升浪

**日期**：2026-06-02  
**用途**：实现完成后本地联通性验证（以历史回测为主）。

---

## 1. 前置条件

- MySQL 可连；`stock_daily_bar`、`stock_weekly_bar`、`stock_monthly_bar` 已同步且含 **`macd_hist`**（可执行 `python -m app.scripts.fill_stock_indicators` 或等待日终指标回填）。
- 后端虚拟环境已安装依赖。

---

## 2. 单元测试（推荐先跑）

```bash
cd backend
pytest tests/test_duo_zhou_qi_macd_gong_zhen.py -q
```

期望：覆盖「六日递增红柱」「三周期共振」「四类平仓优先级」的用例通过。

---

## 3. 后端 API 自检

### 3.1 策略是否注册

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/strategies | jq
```

期望：`items` 中含 `strategy_id == "duo_zhou_qi_macd_gong_zhen"`。

### 3.2 回测跑通

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtest/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"duo_zhou_qi_macd_gong_zhen","start_date":"2024-06-01","end_date":"2024-08-01"}' | jq
```

期望：

- 任务创建成功并最终 `completed` 或 `incomplete`（存在未平仓时）；
- 若有 `closed` 交易：`trigger_date == buy_date`，`buy_price` 为买入日收盘价；
- `extra.exit_reason` 为四类之一；
- 移动止盈样本：`trailing_armed == true` 且卖出价为触发日收盘。

### 3.3 策略详情文案

```bash
curl -s -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8000/api/strategies/duo_zhou_qi_macd_gong_zhen | jq '.description'
```

期望：说明含「日周月红柱」「第 6 日收盘买」「+10% 后 3% 移动止盈」。

---

## 4. 首期不包含项（验证时应为否）

- **无** APScheduler 17:xx Job（除非 Phase 2 已实施）。
- **无** 独立策略选股前端路由（`route_path` 可为空）。

---

## 5. 人工抽查清单

| 检查项 | 方法 |
|--------|------|
| 买入日 = D6 | 对照 `extra.d1_date` 与 `trigger_date`，相差 5 个交易日 |
| 涨幅过滤 | `close(D6) / open(D1) - 1 ≥ 0.10` |
| 止损优先 | 构造同日 −7% 与红转绿，应仅 `stop_loss_7pct` |
| 未武装移动止盈 | 未达 +10% 前大跌，不应 `trailing_take_profit_3pct` |
