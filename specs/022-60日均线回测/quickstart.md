# 快速上手：60 日均线买入法（`strategy_id`: `ma60_slope_buy`）

## 前置

- `stock_daily_bar` 已写入 **`ma60`**、`close`；日线同步覆盖待测区间。  
- 本地 MySQL 与后端 `SessionLocal` 配置可用。

## 环境（Specify 脚本）

在仓库根目录若需运行 `.specify/scripts/bash/*.sh` 且当前 git 分支为 `main`，可设置：

```bash
export SPECIFY_FEATURE='022-60日均线回测'
```

再执行 `update-agent-context.sh` 等，以便解析到本规格目录。

## 验证策略已注册

```bash
curl -s http://127.0.0.1:8000/api/strategies | jq '.items[] | select(.strategy_id=="ma60_slope_buy")'
```

（若接口需鉴权，加上与项目一致的 `Authorization` 头。）

预期：`strategy_id` 为 **`ma60_slope_buy`**，展示名含 **60** 与 **均线** 语义。

## 回测

1. 浏览器打开「**智能回测 → 历史回测**」，策略下拉里选择 **60 日均线买入法**。  
2. 或调用 `POST /api/backtest/run`，body 中 `strategy_id` 填 **`ma60_slope_buy`**。

**核对要点**：

- 某笔 `buy_price` 等于该笔 **`buy_date` 当日开盘价**（信号日次日）。  
- `trigger_date` 为 **信号日**（`buy_date` 的前一交易日），且 `extra` 中四日 MA60 斜率满足前三负、信号日正，信号日 `ma5>ma10>ma20`。  
- 止盈后收益率约 **+15%**（收盘价口径）、止损约 **-8%**。

## 策略选股页

侧栏 **策略选股 → 60 日均线买入法**，路径 **`/strategy/ma60-slope-buy`**（实现阶段添加菜单与路由后生效）。

## 单元测试

```bash
cd backend && pytest tests/test_ma60_slope_buy.py -q
```

## 定时任务

本功能**不**新增定时任务。
