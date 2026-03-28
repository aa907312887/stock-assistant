# 数据模型：恐慌回落法（历史回测）

**日期**：2026-03-28（同步实现）  
**说明**：本功能复用「智能回测」表结构；策略阈值本期**不落库**，以 `spec.md` 默认值为代码实现口径。以下字段与 `backend/app/models/backtest_*.py` 对齐。

## 关键实体

### 1) 策略参数（StrategyParams）

本期**仅代码内常量**；回测任务表记录 `strategy_id` + `strategy_version`，不在任务行存 JSON 参数。

- **strategy_id**：`panic_pullback`
- **ma_short / ma_mid / ma_long**：均线周期（默认 5/10/20）
- **gap_down_threshold**：低开阈值（默认 0.03）
- **day_drop_threshold**：触发日整体跌幅阈值（默认 0.07）
- **volume_k**：成交量放大系数（默认 1.5）
- **lookback_days**：窗口天数（固定 5）

### 2) 触发信号（Signal）

用于调试与复盘，建议作为可选输出或在回测明细中展开。

- **symbol**：股票代码
- **trade_date (t)**：触发日
- **passed_ma_bearish**：是否均线空头排列
- **passed_down_days**：是否“前 5 天跌 4 天”
- **passed_gap_down**：是否低开 ≥ 3%
- **passed_day_drop**：是否整体跌 ≥ 7%
- **passed_volume_spike**：是否成交量显著放大（B 方案）
- **eligible**：是否最终触发

> 若系统已有“信号表/信号日志”则直接复用；否则可不落库，仅在回测运行日志中输出。

### 3) 交易记录（`backtest_trade`）

与恐慌回落法语义对应关系：

- **buy_date**：触发日 \(t\)（买入日）
- **buy_price**：触发日收盘价
- **sell_date**：次日 \(t+1\)
- **sell_price**：次日收盘价
- **return_rate**：单笔收益率 \((sell - buy) / buy\)
- **trade_type**：`closed` / `unclosed`
- **exchange**、**market**、**market_temp_level**、**market_temp_score**：用于筛选与分组统计
- **extra_json**：策略扩展字段（如触发相关数值）

## 索引与查询（建议）

- 按 `task_id + buy_date` / `task_id + stock_code` 查询交易明细
- 按 `task_id` 汇总指标；筛选分析均为**读已落库行**，不重复跑策略

