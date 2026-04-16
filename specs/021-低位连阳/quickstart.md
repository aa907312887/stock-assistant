# 快速上手：红三兵（`strategy_id`: `di_wei_lian_yang`）

## 前置

- `stock_daily_bar` 含 `cum_hist_high`；建议已写入 `ma60`、成交量字段完整。

## 验证策略已注册

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/strategies | jq '.[] | select(.strategy_id=="di_wei_lian_yang")'
```

展示名称应为「红三兵」。

## 回测

在「历史回测」中选择 **红三兵**，或 `POST /api/backtest/run` 中 `strategy_id` 填 `di_wei_lian_yang`。

核对：`trigger_date` 为三连阳最后一日；`buy_date` 多为次日；`extra.pattern_path` 为 `red_three_soldiers`；形态为实体每日 **1%～5%**、影线占振幅默认 **25%**；开盘相对前收高开上限默认 **1%**（见 `extra.max_open_gap_up_pct`）。

## 策略选股

侧栏 **策略选股 → 红三兵**（路径仍为 `/strategy/di-wei-lian-yang`）。

## 单元测试

```bash
cd backend && pytest tests/test_di_wei_lian_yang.py -q
```

## 定时任务

交易日 **17:21（Asia/Shanghai）** 执行当日筛选；日志关键字：`红三兵定时筛选`。
