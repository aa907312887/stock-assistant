# 数据模型：早晨十字星

**日期**：2026-03-29  
**说明**：本功能**不新增**数据库表或列；复用现有「智能回测」与 `stock_daily_bar` 模型。

## 1. 持久化实体（复用）

### 1.1 `backtest_task`

与 `specs/010-智能回测/data-model.md` 一致。`strategy_id` 字段可取值新增：`zao_chen_shi_zi_xing`。

### 1.2 `backtest_trade`

与现有结构一致。本策略写入时：

| 字段 | 取值说明 |
|------|-----------|
| `strategy_id`（若表或关联中有） | 由任务带入，与任务一致 |
| `trigger_date` | 第三根阳线日 **T**（形态完成日） |
| `buy_date` / `buy_price` | 自 **T** 日起首次 `close > MA5` 的交易日收盘价 |
| `sell_date` / `sell_price` / `return_rate` | 与「曙光初现」相同仿真规则 |
| `trade_type` | `closed` / `unclosed` 语义同现有策略 |
| `extra` | JSON，建议含 `exit_reason`、`pattern_*` 等便于核对 |

若项目当前 `backtest_trade` 无 `strategy_id` 列，则以既有任务表关联为准（与 010 规格一致）。

## 2. 行情实体（只读）

### 2.1 `stock_daily_bar`（相关字段）

| 字段 | 用途 |
|------|------|
| `stock_code`, `trade_date` | 主键维度 |
| `open`, `close`, `high`, `low` | 三根 K 线形态与锤头影线 |
| `volume` | T 日放量判定 |
| `ma5`, `ma10`, `ma20` | 跌势结构、买入站上 MA5（卖出不再依赖破 MA5） |
| `cum_hist_high` | 收盘 ≤ 历史高 50% |

缺失任一方针所需字段时，该样本**不触发**（与曙光初现一致）。

## 3. 策略运行时对象（非持久化）

| 名称 | 说明 |
|------|------|
| `BacktestTrade` | `app/services/strategy/strategy_base.py` 中 dataclass，`trigger_date` 填 **T** |
| `BacktestResult` | `trades` 列表 + 可选 `skipped_count` |
| `StrategyDescriptor` | `describe()` 供 `/api/strategies` 与前端展示 |

## 4. 校验规则摘要

- `trigger_date` 必须为第三根阳线交易日；不得与 `buy_date` 混用（除非二者同日）。
- `extra` 中宜保留形态关键中间量（如三日日期、锤头判定布尔、前期 7 日阴线数）以便 SC-003 人工核对。
