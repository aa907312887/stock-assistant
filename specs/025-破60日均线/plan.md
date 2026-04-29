# 实现计划：破 60 日均线买入法（历史回测内置策略）

**分支**：`main`（规格目录 `025-破60日均线`）| **日期**：2026-04-18 | **规格**：[spec.md](./spec.md) | **调研**：[research.md](./research.md)

**产品决策（来自规划输入）**：**不考虑停牌**——不单独建停牌状态字段、不向交易日历借补；**有 K 则计一日**，**无行则该自然片段不存在于序列**，前 5 日 + 信号日 + 买入日**均须为库中**连续**日线行。详见 [research.md](./research.md) 第 1 节。

**说明**：全文中文，粒度达到**可直接按本方案实现**。

## 概要

在现有**策略注册表 + 回测引擎**上新增内置策略，**`strategy_id`=`ma60_five_day_break`**，展示名**「破60日均线买入法」**（与 `ma60_slope_buy`「60日均线买入法（斜率）」区分）。信号逻辑：设 `bars_list` 为某标的按日升序 K 线，**信号日**为下标 **`i`（对应规格中的 D）**，满足：

- **`i >= 5`** 且存在 **`i+1`**（买入用）；
- 对 **`k=1..5`**：`close[i-k] < ma60[i-k]` 且 `ma60[i-k]`、`close[i-k]` 非空；
- **信号日**：`close[i] > ma60[i]` 且非空；
- **买入日**：`bars[i+1]` 的 `trade_date`，`buy_price = open[i+1]`（`open` 无效则**不成交**）；
- **卖出**：自 **`i+2`** 起（买入日**之后**的下一根 K）至序列末，**按收盘价**；相对 `buy_price` **先**检 **≤ 1−8%** 止损，再检 **≥ 1+8%** 止盈（同 [ma60_slope_buy 的 `simulate_exit_close_only`](../../backend/app/services/strategy/strategies/ma60_slope_buy.py) 顺序，**止盈比例参数改为 0.08**）；见 [research.md](./research.md) 第 2 节。

交付物：新策略模块、注册、**`strategy_descriptions.py` 键**、**中文 docstring**（符合项目策略类注释要求）、**pytest 表驱动单测**（含五日在下+突破+次日开买+8%/8% 退出边界）。**无新数据库表**、**无新 API 路由**；[contracts/strategy-backtest.md](./contracts/strategy-backtest.md) 为契约说明。

**本功能不涉及定时任务**（不新增 APScheduler 任务不新增 cron）；若与「早晨十字星」一样后续把 `execute` 接入选股定时，在**单独任务**中增加 `strategy_id` 配置即可。

## 技术背景

- **语言/版本**：Python 3.12、TypeScript / Vue 3（与仓库一致）  
- **主要依赖**：FastAPI、SQLAlchemy、MySQL；策略 `app/services/strategy/`、回测 `app/services/backtest/`  
- **存储**：复用 `stock_daily_bar`（`open`/`close`/`ma60` 等）及 `backtest_task` / `backtest_trade`  
- **测试**：`pytest`，`backend/tests/test_ma60_five_day_break.py`（构造 `bars` 或 Mock 行对象）  
- **目标平台**：与现网回测相同  
- **性能目标**：与 `ma60_slope_buy` 全市场日线扫描**同量级**；判定较斜率法更简单，无额外风险  
- **约束**：**仅日线**；参数**写死**在 `_Params`：`take_profit_pct=0.08`、`stop_loss_pct=0.08`（与 `ma60_slope` 的 0.15/0.08 不同）  
- **规模/范围**：A 股**剔 ST/*ST**（与 `ma60_slope_buy` 同）

## 章程检查

`/.specify/memory/constitution.md` 为模板占位，**无额外**强制门禁。本计划遵循：简体中文 `spec`/`plan` 同步、策略类**完整**中文 docstring、能力说明在回测/策略选页**悬浮轻量**补充（不铺满首屏）。

**复检（Phase 1 后）**：契约与 [data-model.md](./data-model.md) 与本文件一致，无未解决「待澄清」。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
新建 Ma60FiveDayBreakStrategy + run_ma60_five_day_break_backtest(db, ...)
    → registry.list_strategies() 追加
         → GET /api/strategies 出现新 strategy_id
    → POST /api/backtest/run body.strategy_id=ma60_five_day_break
         → backtest_engine 调用 strategy.backtest(...)
    → 可选：POST /api/strategies/ma60_five_day_break/execute（与现网策略同入口，P1 **不强依赖**；若本迭代只做回测，可**仅**实现 `describe`+`backtest`）
```

#### 后端文件（建议）

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy/strategies/ma60_five_day_break.py` | **新建**：`_Params`、`five_day_below_then_break` 判定、可复用或**复制** `simulate_exit_close_only` 为 `_simulate_exit_8_8`（`take_profit_pct=stop_loss_pct=0.08`）、`run_ma60_five_day_break_backtest`、`Ma60FiveDayBreakStrategy` |
| `backend/app/services/strategy/registry.py` | `from ...ma60_five_day_break import Ma60FiveDayBreakStrategy`，`list_strategies()` 在 `Ma60SlopeBuyStrategy()` **相邻**或**之后**注册 |
| `backend/app/services/strategy/strategy_descriptions.py` | 增加键 `ma60_five_day_break`，**修改参数须同步**（同文件头注释） |
| `app/api/backtest.py`、`strategies` 路由 | **不新增**路径；仅新 `strategy_id` 生效 |

#### 数据查询（与 `ma60_slope_buy` 对齐）

- `select` 字段：至少 `stock_code, trade_date, open, close, ma60`；**必须** `close`/`ma60` 非空入列（`where` 可过滤，与斜率法类似）。
- **扩展窗口**：`extended_start = start_date - timedelta(days=~120)`（保证信号日前有足够根数参与预计算，若引擎仅信任库内 `ma60` 可不必手算 60 根，与斜率法一致取 **120** 天缓冲）；`extended_end = end_date + timedelta(days=400)` 以覆盖持仓后止盈止损扫描。
- **分组**：`defaultdict` 按 `stock_code` 组内升序，**剔 ST**（从 `stock_basic` 建集合，**同** `ma60_slope_buy`）。

#### 主循环与下标

- 最外层：`for i in range(5, len(bars_list) - 1):`（保证 `i-5` 有、`i+1` 有）。  
- **子条件** `all_below = True`：  
  `for k in 1..5: bar = bars[i-k];` 若 `ma60/close` 为 `None` → `continue` 外层 `i`（不触发）；`float(close) < float(ma60)` 否则。  
- **突破**：`float(bars[i].close) > float(bars[i].ma60)`。  
- `trigger_date = bars[i].trade_date`；`buy` 用 `bars[i+1]`；`buy_date` 须在 `[start_date, end_date]` 内才产出（**与**斜率法相同区间过滤，避免只统计区间外买）。

#### 与 `ma60_slope_buy` 相同工程语义

- `last_block` / `unclosed` 交易、区间外**未平**写 `trade_type=unclosed` 等，**整段复制**自 `ma60_slope_buy.py` 的 `for code, bars_list` 与 `trades.append` 结构，仅**替换**信号检测块与 `extra` 内容。

#### `extra_json` 建议键

- `pattern_path`: e.g. `ma60_five_below_break_next_open`  
- `exit_reason`: 沿用 `stop_loss_8pct` / `take_profit_8pct`（字符串在实现中统一，**勿**与 15% 策略复用同名字符串若会造成报表混淆，可带 `_8pct` 后缀）

### 定时任务与部署设计

**本功能不涉及定时任务。**

不新增 `scheduler` 中 job；不新增部署一次性脚本。若产品要求「与低位连阳」一致每日跑选股，后续在 `specs/025-破60日均线/tasks` 中增加「对接 `execute_strategy` 与 `scheduler`」的**可选**任务项。

### 前后端职责

| 层 | 职责 |
|----|------|
| 后端 | 策略类、`backtest` 全市场扫描、注册、描述、（可选 `execute`） |
| 前端 | **仅**在策略下拉里出现新项（由 `/api/strategies` 自动带出）；在 `BacktestConfigPanel` 等使用统一列表的页面**无**新组件；**建议**在策略说明/Tooltip 中写清「5 日在线下 / 突破 / 次日开 / 8% 8%」，与 `010` 能力说明规则一致（悬浮、不占满屏） |

### 其它关键设计

- **前复权**：不新增逻辑；**信任**现网日线同口径。  
- **涨跌停卖出**：不新增**策略级**卖价可成交性校验，**以**回测引擎与 `ma60_slope_buy` **相同**的「收盘价即成交」理想化；若全引擎统一加涨跌停，随引擎变更而变更。  
- **可复现性**：不引入非确定性；同库同参两次 `backtest` 结果**一致**。

## 项目结构

### 本功能文档

```text
specs/025-破60日均线/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── strategy-backtest.md
└── checklists/
    └── requirements.md
```

### 源码结构（本功能增量）

```text
backend/app/services/strategy/
├── strategies/
│   └── ma60_five_day_break.py   # 新建
├── registry.py                 # 注册
└── strategy_descriptions.py   # 文案
backend/tests/
└── test_ma60_five_day_break.py # 新建
```

## 测试计划（实现阶段必做）

1. **单元测试**：3～5 组**构造** `bars_list`（**无 DB**）：  
   - 满足五日在下+突破+次日开买+随后某日收盘 +8% → 卖在 **+8%** 日。  
   - 满足买后**先**触及 −8% → 卖在**止损**日。  
   - 不满足「五日都在下」→ 无买。  
   - `open` 缺失/无效 → 不成交。  
2. **集成**（可选）：在测试库跑短区间 `backtest` 与任务查询（非 P1 阻塞项）。

## 风险与回滚

- 与 `ma60_slope_buy` 名称接近 → **必须**在 UI 上「短描述」区分子标题（斜率 vs 五日线突破）。  
- 回滚：移除 `registry` 与文件即可；**无**迁移。

## 验收追踪（对 spec 的 FR）

| FR | 落地位置 |
|----|----------|
| FR-001～005 | `ma60_five_day_break.py` 下标与价格计算 |
| FR-006 | `_simulate_exit_8_8` 收盘价+顺序 |
| FR-007 | `backtest` 产出的 `BacktestTrade` 与引擎写库 |
| FR-008 | 无随机、确定分支 |

## 与现有规格/契约同步

- 若实现中 `strategy_id` 或展示名有变，**同步** [spec.md](./spec.md) 中名称表述与 [contracts/strategy-backtest.md](./contracts/strategy-backtest.md) 的 `strategy_id` 行。  
- 更新 `checklists/requirements.md` 中规划阶段结论（**可选**手勾）。

---

**IMPL_PLAN 完成**：Phase 0（research）与 Phase 1（data-model、contracts、quickstart）成稿，可进入 `/speckit.tasks` 或手工拆解任务。
