# 接口契约补充：恐慌回落法（历史回测）

**日期**：2026-03-28（同步实现）  
**说明**：通用回测路由前缀为 `/api/backtest`，详见 `specs/010-智能回测/contracts/backtest-api.md`。本文仅补充恐慌回落法策略标识及与本文口径一致的约定。

## 策略标识

- **`strategy_id`**：`panic_pullback`（请求体字段名与现有回测 API 一致，**不是** `strategy_key`）
- **展示名称**：恐慌回落法

## 发起回测

与通用接口相同：

- **方法**：`POST /api/backtest/run`
- **请求体**（本期仅三字段）：

```json
{
  "strategy_id": "panic_pullback",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

策略阈值（均线周期、低开、跌幅、放量系数等）以 `specs/011-恐慌回落法/spec.md` 默认值为代码实现口径；**本期请求体不包含** `universe`、`strategy_params`（若未来扩展，须以 spec 为准）。

## 任务结果与分析接口（共用）

完成回测后，与其它策略共用同一套任务与明细接口，包括：

- `GET /api/backtest/tasks/{task_id}` — 任务详情与报告
- `GET /api/backtest/tasks/{task_id}/trades` — 明细分页与筛选（多选温度/交易所/板块、年份等）
- `GET /api/backtest/tasks/{task_id}/filtered-report` — 筛选后复算指标
- `GET /api/backtest/tasks/{task_id}/yearly-analysis` — 分年度分析
- `GET /api/backtest/tasks/{task_id}/best-options` — 最佳胜率/最佳盈利组合

细则以 `specs/010-智能回测/contracts/backtest-api.md` 更新章节为准。

## 错误约定

与通用回测一致：`STRATEGY_NOT_FOUND`、`INVALID_PARAMS`、`DATE_OUT_OF_RANGE`、`TASK_NOT_FOUND` 等。
