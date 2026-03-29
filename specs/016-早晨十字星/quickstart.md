# 快速开始：早晨十字星（开发与验证）

**日期**：2026-03-29

## 1. 前置条件

- 后端依赖与 `specs/010-智能回测/quickstart.md` 相同（Python 虚拟环境、MySQL、`stock_daily_bar` 含 `cum_hist_high` 等）。
- 若库表尚无 `backtest_trade.trigger_date`，执行仓库内迁移脚本（见 `015-曙光初现` / 根目录 `backend/scripts/add_backtest_trade_trigger_date.sql`）。

## 2. 实现后自检清单

1. **注册**：`list_strategies()` 含 `zao_chen_shi_zi_xing`；`get_strategy("zao_chen_shi_zi_xing")` 非空。
2. **列表接口**：`curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/strategies | jq` 中出现「早晨十字星」。
3. **单日执行**：对已知有数据的 `as_of_date` 调用 `POST /api/strategies/zao_chen_shi_zi_xing/execute`，响应结构与其他策略相同。
4. **回测**：`POST /api/backtest/run`，`strategy_id` 填 `zao_chen_shi_zi_xing`，短区间（如 1 个月）；任务完成后拉取 `.../trades`，确认 `trigger_date` 为第三根阳线日、且买入日 ≥ 触发日。
5. **单元测试**：为锤头判定与「T−9…T−3 弱势窗口」各写至少 1 组表驱动测试（可选但推荐）。

## 3. 前端

- 登录后打开「智能回测 → 历史回测」，策略下拉应自动出现新策略（来自 `/api/strategies`）。
- 若未新增侧栏菜单，属预期；回测不受影响。

## 4. 常见问题

- **回测结果为空**：检查区间内是否满足最小历史深度（索引需至少到 T−9）；或 ST 剔除、字段缺失导致跳过。
- **与曙光初现结果混淆**：核对 `strategy_id` 与任务记录中的策略名称。

## 5. 实现后自检（与 tasks T017 对应）

- 代码已注册 `zao_chen_shi_zi_xing`；本地启动后端后按第 2 节执行。
- **SC-003**（不少于 10 组人工标注样本）：属验收阶段工作，可在发布前单独安排，不阻塞开发合并。
