# 实现计划：60 日均线买入法（历史回测）

**分支**: `main`（规格目录 `022-60日均线回测`） | **日期**: 2026-04-16 | **规格**: [`spec.md`](./spec.md)  
**输入**: 功能规格来自 `specs/022-60日均线回测/spec.md`

**说明**: 仓库在 `main` 上开发；`setup-plan.sh` 依赖「特性分支名」校验，本计划在 **`SPECIFY_FEATURE=022-60日均线回测`**（或与目录名一致且带 `022-` 前缀的环境）下可与 Specify 脚本对齐。路径固定为 `specs/022-60日均线回测/`。

## 概要

在现有「策略注册表 + `StockStrategy.backtest()` + 回测引擎落库 + 历史回测页动态拉策略列表」架构上，新增内置策略 **`ma60_slope_buy`**（展示名 **60 日均线买入法**）：

- **买入**：信号日 \(i\) 满足 **\(s(i-3),s(i-2),s(i-1)<0\)**、**\(s(i)>0\)**，且当日 **MA5>MA10>MA20**；在 **次日开盘价** 买入；`trigger_date` 为信号日，`buy_date` 为次日。
- **卖出**：自买入次日起逐日看 **收盘价** 相对买入价；**先判止损**再判止盈：若 `close <= buy×(1-0.08)` 则当日 **收盘价** 止损；否则若 `close >= buy×(1+0.15)` 则当日 **收盘价** 止盈；否则继续持仓至延伸数据用尽则 `unclosed`。
- **选股 `execute`**：与回测同一规则；在 `as_of_date` 为 **买入日（次日）** 且条件成立时产出候选（`trigger_date` 为信号日）。
- **交付物**：新策略模块、注册与 `STRATEGY_DESCRIPTIONS`、表驱动 **pytest**、可选与现有策略页同构的 **Vue 选股页 + 菜单 + 路由**（满足前端能力说明与可发现性）；**无新数据库表**。

## 技术背景

- **语言/版本**: Python 3（与仓库 `backend/requirements.txt` 及部署运行时一致）、TypeScript / Vue 3（`frontend`）  
- **主要依赖**: FastAPI、SQLAlchemy、MySQL；策略层 `app/services/strategy/`  
- **存储**: MySQL；复用 `stock_daily_bar`（`close`、`ma60`、`trade_date` 等）、`stock_basic`；回测结果仍写入 `backtest_task` / `backtest_trade`  
- **测试**: `pytest`，新建 `backend/tests/test_ma60_slope_buy.py`（纯函数 + 构造 `StockDailyBar` 或轻量 namedtuple/简单对象列表）  
- **目标平台**: 本地 / 服务器 + 浏览器  
- **性能目标**: 与 `ma_golden_cross` 等同量级全市场日线扫描；单次查询按 `stock_code` 分组后在内存推进即可  
- **约束**: 仅日线；参数写死在 `_Params` dataclass（`take_profit_pct=0.15`、`stop_loss_pct=0.08`）  
- **规模/范围**: A 股非 ST / *ST 全市场（与 `di_wei_lian_yang` 等策略一致剔除规则）

## 章程检查

`/.specify/memory/constitution.md` 当前为占位模板，**无额外强制门禁**。本计划遵循：策略类 **简体中文 docstring**（覆盖 `strategy-class-documentation.mdc` 所列要点）、`strategy_descriptions.py` 与 `spec.md` 同步；前端新增页须在标题旁提供 **Tooltip 能力说明**（与 `MaGoldenCrossView.vue` 同级）。

**设计后复检**：Phase 1 工件已覆盖数据流、接口、无定时任务、确定性卖出顺序；仍无章程冲突项。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
新建 Ma60SlopeBuyStrategy + run_ma60_slope_buy_backtest(...)
    → registry.list_strategies() 追加实例
         → GET /api/strategies 历史回测下拉自动出现（BacktestConfigPanel 已动态拉取）
         → GET /api/strategies/{id} 详情与 assumptions
    → POST /api/strategies/ma60_slope_buy/execute（选股，可选）
    → POST /api/backtest/run（body.strategy_id=ma60_slope_buy）
         → backtest_engine.run_backtest → strategy.backtest(...)
    → 任务明细 / 筛选 / 分年 等接口与现网一致（不修改契约，仅多一个 strategy_id）
```

#### 后端分层与文件

| 层级 | 路径 | 职责 |
|------|------|------|
| 策略内核 | `backend/app/services/strategy/strategies/ma60_slope_buy.py`（新建） | `_Params`、`run_ma60_slope_buy_backtest(...)`、`Ma60SlopeBuyStrategy`：`describe`、`execute`、`backtest` |
| 注册表 | `backend/app/services/strategy/registry.py` | `from ... ma60_slope_buy import Ma60SlopeBuyStrategy`，`list_strategies()` 插入实例（建议放在 `MAGoldenCrossStrategy` 邻近，便于均线类维护） |
| 策略说明 | `backend/app/services/strategy/strategy_descriptions.py` | 增加键 `ma60_slope_buy`，正文与 `spec.md` 买入链、±15%/-8%、收盘价监测、同日双触优先级一致 |
| API | `app/api/strategies.py`、`app/api/backtest.py` | **不新增路由**；注册后即自动可用 |

#### 日线查询与窗口

- **SELECT 字段**：`stock_code, trade_date, open, close, ma5, ma10, ma20, ma60`。**必须** `close`、`ma60` 非空；买入日 `open` 须有效。  
- **时间窗**：`trade_date ∈ [start_date - Δ, end_date + Δ2]`。建议 **`Δ = timedelta(days=120)`**（覆盖 MA60 稳定预热 + 链前一日斜率）；**`Δ2 = timedelta(days=400)`**（与 `di_wei_lian_yang` 等一致，保证买入后有足够日历跨度寻止盈/止损）。  
- **分组**：按 `stock_code` 升序、`trade_date` 升序组成 `bars_list`。  
- **ST 剔除**：从 `stock_basic` 建 `name` 以 `ST`、`*ST` 开头的 `code` 集合，循环中跳过。

#### 主循环与索引（每只股票）

- 设 `bars_list` 0 基下标，**`i` 为信号日**；**`buy_idx = i+1`** 为买入日。  
- **斜率**：`s(i) = ma60[i] - ma60[i-1]`（`i>=1`）。  
- **条件**：`i >= 4` 且 `i+1 < len`；`s(i-3),s(i-2),s(i-1) < 0`；`s(i) > 0`；当日 `ma5 > ma10 > ma20`（均非空）；次日 `open` 有效且 `>0`。  
- **回测区间内成交**：`buy_date = bars_list[i+1].trade_date` 落在 `[start_date, end_date]`。  
- **单仓阻塞**：`last_block` 与平仓后从 `sell_idx` 继续扫描。

#### 卖出仿真（收盘价口径）

- `buy_price = float(open[i+1])`（信号日次日开盘）。  
- 对 `j > k` 且 `trade_date[j] <= end_date_extended`（由查询上界保证）：  
  - 若 `close[j] <= buy_price * (1 - stop_loss_pct)`：`sell_date=trade_date[j]`，`sell_price=float(close[j])`，`exit=stop`  
  - `elif close[j] >= buy_price * (1 + take_profit_pct)`：`sell_date=trade_date[j]`，`sell_price=float(close[j])`，`exit=profit`  
- 若循环结束未触发：`BacktestTrade(..., trade_type="unclosed", sell_date=None)`。  
- **`extra` 建议字段**：`slope_ma60_day_minus_3` … `slope_ma60_signal_day`、`signal_day_ma5/10/20`、`turn_date`（信号日）、`exit_reason`。

#### `execute(as_of_date)` 语义

- 对每个非 ST 股票，取截至 `as_of_date`（含）的历史 bars 升序。  
- 若存在信号使得 **`bars_list[i+1].trade_date == as_of_date`** 且条件成立，则产生 `StrategyCandidate`：`trigger_date = bars_list[i].trade_date`（信号日）。  
- 无 `cum_hist_high` 依赖，本策略**不**因缺该列报错。

#### 前端（与现有策略页对齐）

| 项 | 说明 |
|----|------|
| 路由 | `frontend/src/router/index.ts` 增加 `path: 'strategy/ma60-slope-buy'`，`component` 指向新视图 |
| 菜单 | `frontend/src/views/Layout.vue`「策略选股」下增加一项 **60 日均线买入法** |
| 视图 | 新建 `frontend/src/views/Ma60SlopeBuyView.vue`（可自 `MaGoldenCrossView.vue` 复制骨架）：日期选择、`executeStrategy` API、表格列展示代码/名称/触发日、`el-tooltip` 写清买入链与止盈止损 |
| 历史回测页 | **通常无需改**：`BacktestConfigPanel` 已 `listStrategies()` |

### 定时任务与部署设计

**本功能不涉及定时任务。** 不新增 APScheduler Job；不要求部署时额外执行一次。若产品后续要求「收盘后自动选股落库」，可另开规格沿用 `scheduler.py` 中现有策略任务模式。

### 其他关键设计

- **`ma60` 口径**：实现以 **`stock_daily_bar.ma60`** 为准（与日线同步任务预计算一致）；若某行 `ma60` 为空则该日不参与斜率计算。若上线前验收发现与手工 60 日滚动均值不一致，应排查同步脚本而非在策略内重复算 MA（避免双口径）。  
- **回测确定性**：不在策略内引入随机数；同一 `strategy_id`+日期区间+数据快照，结果须可复现（`SC-002`）。  
- **引擎侧**：`panic_pullback` 以外的策略走默认单仓仿真；本策略 **不需要** `allow_rebuy_same_day_as_prior_sell`。

## 项目结构

### 本功能文档

```text
specs/022-60日均线回测/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型（复用说明）
├── quickstart.md        # Phase 1 本地验证
├── contracts/           # Phase 1 接口契约（沿用现有端点）
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/                     # strategies / backtest 路由（不改路径，仅注册新策略）
│   ├── services/
│   │   ├── strategy/
│   │   │   ├── strategies/
│   │   │   │   └── ma60_slope_buy.py   # 新建
│   │   │   ├── registry.py
│   │   │   └── strategy_descriptions.py
│   │   └── backtest/
│   │       └── backtest_engine.py      # 一般无需改
│   └── models/
│       └── stock_daily_bar.py          # 已含 ma60
└── tests/
    └── test_ma60_slope_buy.py          # 新建

frontend/
├── src/
│   ├── views/
│   │   ├── Ma60SlopeBuyView.vue        # 新建
│   │   └── Layout.vue                  # 菜单 +1
│   └── router/index.ts                 # 路由 +1
```

**结构说明**：策略以「单文件 + 注册表」接入，与 `ma_golden_cross`、`di_wei_lian_yang` 一致，回测与选股共用内核函数，降低分叉风险。

## 复杂度与例外

无需填写（无章程违反项）。
