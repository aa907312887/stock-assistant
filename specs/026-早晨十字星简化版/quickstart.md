# 快速上手：早晨十字星（简化版）

**日期**：2026-05-03  
**用途**：开发完成后本地联通性验证（后端 + 可选前端）。

---

## 1. 前置条件

- MySQL 可连；`stock_daily_bar` 含 **`cum_hist_high`**（与早晨十字星相同前置脚本）。  
- 后端虚拟环境已安装依赖；前端 `npm install` 已完成。

---

## 2. 后端 API 自检

### 2.1 策略是否注册

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/strategies | jq
```

期望：`items` 中含 `strategy_id == "zao_chen_shi_zi_xing_jian_hua"`。

### 2.2 回测跑通

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtest/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"zao_chen_shi_zi_xing_jian_hua","start_date":"2024-06-01","end_date":"2024-08-01"}' | jq
```

期望：任务创建成功；完成后交易明细中 `trigger_date` 为形态第三根阳线日，`buy_date` 在 T 之后，`extra.exit_reason` 含 `stop_loss_8pct` 或 `take_profit_10pct`（若有平仓）；`sell_price` 为触发日收盘价。

### 2.3 选股执行（可选）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/strategies/zao_chen_shi_zi_xing_jian_hua/execute" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"as_of_date":"2024-07-01"}' | jq
```

---

## 3. 定时任务（可选）

- 启动后端后，确认 **APScheduler** 已注册 `_job_strategy_zao_chen_shi_zi_xing_jian_hua_daily`（或最终实现函数名）；日志中在交易日 **17:23** 左右出现执行记录（与 `plan.md` 一致）。  
- **不在部署启动时要求立即执行一次**。

---

## 4. 前端（可选）

- 浏览器打开 **`/strategy/zao-chen-shi-zi-xing-jian-hua`**（以路由为准），侧栏可见「早晨十字星（简化版）」。  
- 页面标题旁有 **悬浮说明**（能力边界：形态同主策略、80% 线、T+1 开盘、收盘 ±10%/−8%）。

---

## 5. 与主策略对比 smoke

同一股票池、同一日期区间，分别提交：

- `strategy_id=zao_chen_shi_zi_xing`  
- `strategy_id=zao_chen_shi_zi_xing_jian_hua`  

期望：**触发日集合可以不同**（80% vs 50% 过滤、买入与卖出规则均不同）；不应出现「简化版触发而主策略完全同 buy/sell 路径」的强行一致。

---

## 6. 故障排查

| 现象 | 检查 |
|------|------|
| 策略列表无新 id | `registry.py` 是否注册；服务是否重启 |
| 回测报 cum_hist_high | 执行 `backend/scripts/add_stock_daily_bar_cum_hist.sql` 与历史极值重算脚本 |
| 定时任务不跑 | `scheduler.py` 是否注册；当日是否交易日；日志是否 `StrategyDataNotReadyError` |
