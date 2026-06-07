# 快速上手：月 MACD 翻红

**日期**：2026-06-06  
**用途**：实现完成后本地联通性验证（以历史模拟为主，历史回测为辅）。

---

## 1. 前置条件

- MySQL 可连；`stock_daily_bar`、`stock_monthly_bar` 已同步且含 **`macd_hist`**（可执行 `python -m app.scripts.fill_stock_indicators` 或等待日终指标回填）。
- 后端虚拟环境已安装依赖。

---

## 2. 单元测试（推荐先跑）

```bash
cd backend
pytest tests/test_yue_macd_fan_hong.py -q
```

期望：覆盖「绿转红月末买」「±20% 止盈止损」「月线红转绿月末卖」「同日优先级」的用例通过。

---

## 3. 后端 API 自检

### 3.1 策略是否注册

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/strategies | jq '.items[] | select(.strategy_id=="yue_macd_fan_hong")'
```

期望：返回策略摘要，`short_description` 含「月线 MACD」「±20%」。

### 3.2 历史模拟跑通（主场景）

```bash
curl -s -X POST http://127.0.0.1:8000/api/simulation/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"yue_macd_fan_hong","start_date":"2020-01-01","end_date":"2024-12-31"}' | jq
```

期望：

- 任务创建成功并最终 `completed` 或含 `unclosed`；
- 若有 `closed` 交易：`trigger_date == buy_date`，`buy_price` 为买入日收盘价；
- `extra.exit_reason` 为三类之一；
- `assumptions` 中 `portfolio_simulation_applied == false`。

### 3.3 历史回测跑通

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtest/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"yue_macd_fan_hong","start_date":"2020-01-01","end_date":"2024-12-31","position_amount":100000,"reserve_amount":100000}' | jq
```

期望：任务成功；策略层闭仓样本的 `buy_date`/`sell_date` 与 3.2 同区间同数据下一致（不含 `not_traded` 差异）。

### 3.4 策略详情文案

```bash
curl -s -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8000/api/strategies/yue_macd_fan_hong | jq '.description'
```

期望：说明含「首个红柱月最后交易日收盘买」「±20%」「后续月 MACD 红转绿月末卖」。

---

## 4. 前端冒烟（可选）

1. 登录 → **智能回测 → 历史模拟**。
2. 策略下拉应出现「月 MACD 翻红」。
3. 选择区间提交，任务列表出现新任务，详情可查看交易明细与 `strategy_description`。

---

## 5. 首期不包含项（验证时应为否）

- **无** APScheduler 17:xx Job（除非 Phase 2 已实施）。
- **无** 独立策略选股前端路由。

---

## 6. 人工抽查清单

| 检查项 | 方法 |
|--------|------|
| 买入日 = 红柱月最后交易日 | 对照 `extra.buy_month_end` 与 `buy_date`，为该月最后有 K 线的日期 |
| 绿转红 | `extra.macd_hist_prev_month ≤ 0` 且 `macd_hist_buy_month > 0` |
| 止盈/止损 | 相对买入价 ±20%，卖出价为触发日收盘 |
| 月线卖出 | `exit_reason=sell_monthly_macd_red_to_green` 时 `sell_date` 为对应月最后交易日 |
| 优先级 | 同日 −20% 与红转绿 → 仅 `stop_loss_20pct` |
| 模拟=回测信号 | 同区间策略层闭仓笔买卖日一致 |
