# 快速开始：恐慌回落法（历史回测）

**日期**：2026-03-28（同步实现）

## 你将得到什么

- 前端「历史回测」中选择策略 **恐慌回落法**（`strategy_id`：`panic_pullback`），指定回测起止日期后发起任务
- 全市场日线扫描（与现有回测引擎一致），完成后查看报告、交易明细
- 在结果页使用：**温度 / 交易所 / 板块（含空板块）/ 交易年份** 多选交叉筛选、**分年度分析**、**最佳胜率 / 最佳盈利** 快捷按钮

## 回测口径（务必一致）

以 `specs/011-恐慌回落法/spec.md` 为准：

- **买入价**：触发日收盘价  
- **卖出价**：次日收盘价（无论盈亏）  
- **放量**：B 方案（见 `spec.md` 澄清记录）

## 接口速览

| 用途 | 方法 | 路径 |
|------|------|------|
| 发起回测 | POST | `/api/backtest/run`（body 含 `strategy_id: "panic_pullback"`） |
| 任务详情 | GET | `/api/backtest/tasks/{task_id}` |
| 交易明细 | GET | `/api/backtest/tasks/{task_id}/trades` |
| 筛选复算 | GET | `/api/backtest/tasks/{task_id}/filtered-report` |
| 分年度 | GET | `/api/backtest/tasks/{task_id}/yearly-analysis` |
| 最佳组合 | GET | `/api/backtest/tasks/{task_id}/best-options` |

Query 多选使用**逗号分隔**；空板块传 **`__EMPTY__`**。详见 `specs/010-智能回测/contracts/backtest-api.md`。

## 常见问题

- **参数能否在界面改阈值**：本期不能；阈值以 `spec.md` 为准写在策略代码中。  
- **最佳胜率很「宽」**：若没有任何子组合满足「已平仓 ≥ 全任务已平仓的 1/10」，会回退为全量不限条件的结果。  
- **结果与手工不一致**：核对同一日线数据、同一筛选条件、买入日自然年与分组口径。
