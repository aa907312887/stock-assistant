# Phase 0 调研结论：月 MACD 翻红

**日期**：2026-06-06  
**目的**：固定实现口径，消除规格歧义，指导 Phase 1 契约与编码。

---

## 1. 「20 点」是否为百分数？

**决策**：是。**20 点** 表示相对买入价的 **20%**（止盈 `×1.20`、止损 `×0.80`），与 `ma60_slope_buy`、`duo_zhou_qi_macd_gong_zhen` 等策略一致。

**理由**：规格假设已写明；本仓库回测/模拟域统一为百分比。

**备选**：绝对价位差 —— 与规格及仓库惯例冲突，**不采用**。

---

## 2. MACD 红/绿判定字段

**决策**：

- **红柱**：`macd_hist > 0`（`None` 或无法解析视为不可比，不参与信号）。
- **绿柱**：`macd_hist ≤ 0`。
- **绿转红（买入）**：前一月 `hist ≤ 0` 且当月 `hist > 0`。
- **红转绿（卖出）**：前一月 `hist > 0` 且当月 `hist ≤ 0`。

**理由**：与 `screening_service`、`duo_zhou_qi_macd_gong_zhen`、综合选股 MACD 筛选一致。

**备选**：DIF/DEA 金叉定义颜色 —— 与全项目柱状图语义不一致，**不采用**。

---

## 3. 「第一个红色月份」与买入日 T_buy

**决策**：

1. 在 `stock_monthly_bar` 按 `trade_month_end` 升序扫描相邻月 `(M−1, M)`；
2. 当 **M−1 绿、M 红** 时，**M 即为首个红柱月**（每次独立绿转红周期各产生一次候选）；
3. **T_buy** = 该月 **最后一个有日线 K 线的交易日** 的 `trade_date`（非自然月最后一天）；
4. **买入价** = **T_buy 收盘价**；`trigger_date = buy_date = T_buy`。

**月末最后交易日算法**：

```text
对每个 daily bar 日期 D，令 aligned_end = max(trade_month_end | trade_month_end <= D)
month_last_trade[aligned_end] = max(D)
T_buy = month_last_trade[M.trade_month_end]
```

**理由**：规格 FR-004/FR-005 与假设「月末最后一个交易日 = 该月 A 股仍有日线的最后 trade_date」；`trade_month_end` 在库中已为当月最后开市日，与日线对齐后取 max(D) 即可。

**备选**：固定使用 `trade_month_end` 当日作为 T_buy —— 若该日非交易日或无 K 线会误买，**不采用**。

---

## 4. 「下一个月 MACD 变绿」的卖出范围

**决策**：采用规格 FR-009 已写明的 **任意后续月首次红转绿** 即卖（于 **Mk 月最后一个交易日** 收盘），**不**限制为买入月的紧邻下一月 **M+1**。

**理由**：

- 规格假设已记录：若仅限 M+1，当 M+1 仍红柱且价格长期未触 ±20% 时缺少 MACD 侧离场；
- 与买入「对称月末判定」一致，实现与测试更简单；
- 用户原文「下一个月」作为典型路径，已在 `strategy_description` 中说明。

**备选**：仅 M+1 转绿才卖 —— 需产品澄清；若后续收紧，只改 `simulate_exit` 中 `curr_month_end == next_month_after_buy` 条件。

---

## 5. 卖出监测：逐日 ±20% 与月末 MACD

**决策**：

| 类型 | 监测频率 | 条件 |
|------|----------|------|
| 止损 −20% | **每个交易日**（自 T_buy 次日） | `close ≤ buy × 0.80` |
| 止盈 +20% | **每个交易日** | `close ≥ buy × 1.20` |
| 月线红转绿 | **仅各月最后一个交易日** | `curr_month_end > buy_month_end` 且前月红、当月绿 |

**同日优先级**（FR-010）：**① 止损 → ② 止盈 → ③ 月线红转绿**。

**理由**：±20% 为日内价格阈值，须逐日扫描；月线信号仅在月末 bar 可最终确认，与买入对称。

**备选**：月线红转绿改为月初第一个交易日卖 —— 与 spec FR-009 冲突，**不采用**。

---

## 6. 首期交付范围（模拟 vs 回测 vs 选股）

**决策**：**Phase 1 交付历史模拟 + 历史回测**：

- 实现 `YueMacdFanHongStrategy.backtest()`（模拟与回测共用）+ 注册表 + `strategy_descriptions`；
- **`execute()`** 返回空候选并说明「本期仅模拟/回测」；
- **不**新增策略选股页、**不**注册 APScheduler Job。

**理由**：规格 FR-001 明确要求双模块；主场景为历史模拟；选股/定时任务在假设中 defer 到 plan Phase 2。

**备选**：首期仅回测 —— 与 spec P1 用户场景不符，**不采用**。

---

## 7. 数据预热与区间扩展

**决策**：

- `extended_start = start_date − 120 日历日`（至少 2 根月线 + 对齐余量）；
- `extended_end = end_date + 1500 日历日`（约 4 年，覆盖长期持仓卖出）。

**理由**：本策略持仓周期以**月**计，±20% 或 MACD 转绿可能发生在回测 `end_date` 之后很久；过短扩展会导致大量 `unclosed` 或错误截断。

**备选**：+400 日（沿用短线策略）—— 对月线长期策略偏短，**不采用**。

---

## 8. 依赖数据未就绪时行为

**决策**：任一月线 `macd_hist` 缺失、或无法构建 `month_last_trade`、或 T_buy 无有效收盘价时，**该买入候选跳过**（`skipped_count++`），不抛 500。

**理由**：规格 P3 与 FR 边界；全市场扫描需容错。

---

## 9. 历史模拟与历史回测一致性

**决策**：两模块均调用同一 `run_yue_macd_fan_hong_backtest()`；差异仅在引擎层（模拟不过 `portfolio_simulation`、回测可能有 `not_traded`）。

**理由**：规格 SC-005 要求策略信号层一致；现有 `simulation_engine` / `backtest_engine` 已按此模式接入其它策略。

---

## 10. 前端改动

**决策**：**首期零前端改动**（除可选 Tooltip）。`BacktestConfigPanel`、`SimulationConfigPanel` 已通过 `listStrategies()` 动态填充下拉。

**理由**：减少交付面；策略说明由 `strategy_description` 在任务详情展示。
