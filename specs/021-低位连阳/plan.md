# 实现计划：红三兵（回测内置策略，`strategy_id`: `di_wei_lian_yang`）

**分支**: `main`（规格目录 `021-低位连阳`） | **日期**: 2026-04-16 | **规格**: [`spec.md`](./spec.md)  
**输入**: 功能规格来自 `specs/021-低位连阳/spec.md`（已由多路径收敛为**仅红三兵**）

**说明**: 全文使用中文，粒度达到**可直接按方案实现**。

## 概要

在现有「智能回测 + 策略注册表 + 策略选股页 + 定时筛选」架构上，内置策略 **`di_wei_lian_yang`** 对外展示为 **红三兵**：**三连阳**（实体每日 1%～5%、影线占振幅≤25%、收盘逐级抬高、**T−1/T 开盘相对前收高开≤1%**）+ **股价不太高**（收盘 ≤ 累计历史高 50%，且若 MA60 有效则收盘 < MA60）+ **第三日成交量 ≥ 前 5 日均量×1.1**；**T+1 开盘价**买入；**卖出**与「早晨十字星」相同（8% 止损、15%+5% 移动止盈）。

交付物：**新策略模块** `di_wei_lian_yang.py`、**注册表与策略说明字典**、**选股视图与路由**、**定时任务**（与早晨十字星同模式）、**回测明细 Tooltip/文案**小补、**策略类中文 docstring**（符合 `.cursor/rules/strategy-class-documentation.mdc`）、**pytest 表驱动单测**（覆盖三路与卖出边界）。**无新数据库表**；复用 `stock_daily_bar` 既有字段（含 `cum_hist_high`）。

## 技术背景

- **语言/版本**: Python（与仓库一致）、TypeScript / Vue 3  
- **主要依赖**: FastAPI、SQLAlchemy、MySQL；策略层 `app/services/strategy/`  
- **存储**: MySQL，复用 `stock_daily_bar`；回测结果仍写入既有 `backtest_task` / `backtest_trade`  
- **测试**: `pytest`，见 `backend/tests/test_di_wei_lian_yang.py`（纯函数 + 构造 bar 列表）  
- **目标平台**: 本地 / 服务器 + 浏览器  
- **性能目标**: 与「早晨十字星」全市场日线扫描同量级；单次回测多两路形态判定，增量可忽略  
- **约束**: 仅日线；内置策略参数写死在 `_Params` dataclass（与现有内置策略一致）  
- **规模/范围**: A 股非 ST 全市场；索引下界 **`i ≥ 9`**（与早晨十字星相同）

## 章程检查

`/.specify/memory/constitution.md` 若为占位，则无额外强制门禁。本计划遵循：**简体中文**注释与规格同步、策略类 docstring 写全口径、前端能力说明以**悬浮/轻量**方式补充（与 `ZaoChenShiZiXingView.vue` 的卡片说明同级，不占满首屏）。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
新建 DiWeiLianYangStrategy + run_di_wei_lian_yang_backtest(...)
    → registry.list_strategies() 追加实例
         → GET /api/strategies 回测下拉展示
         → GET /api/strategies/{id} 详情
    → POST /api/strategies/{id}/execute 选股执行（与早晨十字星相同入口）
    → POST /api/backtest/run（strategy_id=di_wei_lian_yang）
         → backtest_engine 调用 strategy.backtest(...)
    → 定时任务 execute_strategy(db, strategy_id="di_wei_lian_yang", as_of_date=today)
```

#### 后端分层与文件

| 层级 | 路径 | 职责 |
|------|------|------|
| 策略内核 | `backend/app/services/strategy/strategies/di_wei_lian_yang.py`（新建） | `run_di_wei_lian_yang_backtest(db, start_date, end_date, p)` + `DiWeiLianYangStrategy`：`describe`、`execute`、`backtest` |
| 锤头复用 | `backend/app/services/strategy/strategies/zao_chen_shi_zi_xing.py` | **从本模块导出** `is_hammer_bar`（已存在），低位连阳 **import** 调用，避免两套锤头数值 |
| 注册表 | `backend/app/services/strategy/registry.py` | `from ... di_wei_lian_yang import DiWeiLianYangStrategy`，`list_strategies()` 在「早晨十字星」邻近位置插入实例 |
| 策略说明 | `backend/app/services/strategy/strategy_descriptions.py` | 增加键 `di_wei_lian_yang`，文案与 `spec.md` 三路买入及卖出参数一致（修改参数时必须同步此文件——见文件头注释） |
| API | `app/api/strategies.py`、`app/api/backtest.py` | **不新增路由**；注册后即自动可用 |

#### 数据查询（与早晨十字星对齐）

- `select` 字段集合与 `run_morning_star_backtest` **保持一致**：`stock_code, trade_date, open, high, low, close, ma5, ma10, ma20, cum_hist_high, volume`（`pe_percentile` 可不带，本策略不使用）。
- `extended_start = start_date - timedelta(days=60)`、`extended_end = end_date + timedelta(days=400)` 与早晨十字星一致，保证买入后足够持仓仿真区间。
- 缺列 `cum_hist_high` 时：抛出与早晨十字星**同类**的 `RuntimeError` 指引（可复用相同错误前缀便于运维识别）。

#### 索引与触发区间

- 令 **`bar_t = bars_list[i]` 为形态完成日 T**（第三根 K 日），则 **T−k** 对应 `bars_list[i-k]`。
- **前窗**：`j ∈ [i-9, i-3]`（Python `range(i-9, i-2)` 与 `_Params.prior_weak_range_stop_offset=2` 一致），阴线计数与 **`close[i-3]/close[i-9]-1 ≤ -10%`** 与早晨十字星**同一实现**。
- **主循环**：`for i in range(9, len(bars_list))`，且仅当 `trigger_date = bars_list[i].trade_date ∈ [start_date, end_date]` 时尝试产出信号。
- **单仓**：沿用 `last_block` 语义——该标的产生未平仓交易后 `break`；已平仓则从 `sell_idx` 继续扫描。

#### 共用低位过滤（函数化建议）

在 `di_wei_lian_yang.py` 内实现**模块级**函数，例如 `def common_low_position_ok(bars_list, i, p) -> bool:`，逻辑从 `run_morning_star_backtest` 中 **T 日 MA、cum_hist、前窗阴线数、累计跌幅** 四块**逐行拷贝**并加单元测试对照早晨十字星样例（确保数值一致）。**不要**从早晨十字星 import 私有循环片段（避免循环依赖），以**拷贝+注释「与 zao_chen_shi_zi_xing L237–266 对齐」**为首选；若后续重构再抽公共模块。

#### 路径判定（互斥与短路顺序）

同一索引 `i` 下：

1. **若 `close_{i-2} < open_{i-2}`（T−2 阴）**：只可能为 **路径 A**。判定 T−1 锤头或十字星、T 阳实体≥3%；通过后走路径 A 买入（MA5）。
2. **否则（T−2 阳）**：不可能为路径 A。依次判定：  
   - **路径 B2**：`i-2` 阳、`i-1` 阴（小阴）、`i` 阳且 `high_i > high_{i-2}`；  
   - **路径 B1**：三连阳且每日 `0 < (c-o)/o ≤ 4%`。  
   若 B2 与 B1 在同一窗口上**同时**数学可成立（极少：中间日既阴又阳不可能），则 **优先 B2**（结构更具体）。实际上中间日阴阳互斥，**二者天然互斥**；实现顺序可先 B2 后 B1 或反之，**不影响结果**。

每条路径在调用 `common_low_position_ok` 前应先完成该路径的形态快速失败判定，减少无效前窗计算。

#### 路径 A：类十字星（T−1）

- **T−2**：`close < open` 且 `close_{T-2}/close_{T-3} - 1 ≤ -2%`。  
- **T−1**：`is_hammer_bar(...)` **或** `is_doji_bar(...)`（新建本地函数：`body/range ≤ 0.1` 且 `|close_{T-1}/close_{T-2}-1| ≤ 0.01`，`high==low` 返回 False）。  
- **T**：`close > open` 且 `(close-open)/open ≥ 3%`。  
- **买入**：`for j in range(i, len):` 找首次 `close > ma5`，`buy_price = close`，`buy_idx = j`；若 `buy_date > end_date` 跳过。  
- **`extra`**：至少 `pattern_path: "star_like"`、`pattern_yin_date`、`pattern_mid_date`、`pattern_yang_date`、`mid_bar_kind: "hammer"|"doji"`。

#### 路径 B1 / B2：次日开盘买

- **买入**：`buy_idx = i+1`，若 `i+1 >= len` 或 `bars_list[i+1].trade_date > end_date` 或 `open` 无效则**不成交**跳过。`buy_price = open_{T+1}`。  
- **`extra`**：`pattern_path: "red_three_soldiers"` 或 `"two_yang_sandwich_yin"`，并写入三日日期、各日实体涨幅等便于选股表格展示。

#### 卖出仿真（与早晨十字星严格一致）

从 `zao_chen_shi_zi_xing.py` 中 **`buy_idx` 确定之后** 的 `for k in range(buy_idx + 1, ...)` 块（止损固定价、收盘价触发移动止盈、`holding_high` 滚动、`trailing_active` 由 **`close >= buy*(1+0.15)`** 激活）**逐行对齐复制**到 `di_wei_lian_yang.py` 的私有函数，例如 `_simulate_exit_same_as_morning_star(bars_list, buy_idx, buy_price, end_date, p) -> ...`。

- **止损**：`close <= buy*(1-0.08)` → `exit_reason="stop_loss_8pct"`，`sell_price = round(buy*0.92, 4)`。  
- **移动止盈**：若曾满足 `close >= arm_trigger_px`，则当 `close <= holding_high*(1-0.05)` 时 `exit_reason="trailing_stop_5pct"`，`sell_price = 当日 close`。  
- **顺序**：先判止损，再更新 `holding_high` / `trailing_active`，再判移动止盈（与现有代码顺序一致，避免同日逻辑偏差）。

#### `execute()`（单日选股）

- 与 `ZaoChenShiZiXingStrategy.execute` 相同模式：`dd = as_of_date or get_latest_bar_date(db, "daily")`，调用 `run_di_wei_lian_yang_backtest(db, start_date=dd, end_date=dd, p=p)`，筛 **`t.buy_date == dd`** 的 `BacktestTrade` 转为 `StrategyCandidate` / `StrategySignal`。  
- **`assumptions.params`**：写入本策略关键阈值，便于前端「本次执行信息」展示。

#### 前端

| 区域 | 行为 |
|------|------|
| `frontend/src/router/index.ts` | 增加子路由 `strategy/di-wei-lian-yang` → 新视图 |
| `frontend/src/views/Layout.vue` | 侧栏增加「低位连阳」菜单项（与「早晨十字星」相邻） |
| `frontend/src/views/DiWeiLianYangView.vue`（新建） | 参照 `ZaoChenShiZiXingView.vue`：标题、**悬浮或标题旁 `?` Tooltip**（产品能力提示）、口径卡片、调用 `execute` 与列表 API；表格列展示 `pattern_path`、三日日期、买入规则（MA5 / 次日开盘） |
| `frontend/src/components/BacktestResultDetail.vue` | 在触发日/收益说明的 Tooltip 中**追加**「低位连阳」形态完成日与路径 A/B 可能与买入日不同的说明；移动止盈文案已与早晨十字星一致处可合并表述 |

#### 错误与异常

- `strategy_id` 非法：现有 `404 STRATEGY_NOT_FOUND`。  
- 数据未就绪：`StrategyDataNotReadyError` 由 `execute_strategy` 与定时任务捕获（与早晨十字星一致）。

### 定时任务与部署设计

**本功能涉及定时任务**（与「早晨十字星」对称，便于每日自动落库选股结果）。

| 子项 | 内容 |
|------|------|
| **使用的组件** | APScheduler `BackgroundScheduler`，任务注册于 `backend/app/core/scheduler.py` 的 `start_scheduler()` |
| **注册方式** | 在 `start_scheduler()` 内 `add_job(..., replace_existing=True)`，与 `_job_strategy_zao_chen_shi_zi_xing_daily` 并列 |
| **调度策略** | 建议 **每日 17:21**（上海时区），错开早晨十字星 17:20，降低同一进程内连续重扫描锁竞争；若希望统一 17:20，需确认与现有多个 17:20 Job 的执行顺序可接受 |
| **部署时是否执行一次** | **否**（与早晨十字星一致，无 bootstrap DateTrigger） |
| **手动触发方式** | ① 前端「低位连阳」选股页「手动执行筛选」按钮 → 现有 `POST /api/strategies/{strategy_id}/execute`；② 与早晨十字星相同的运维调用链（若有） |
| **失败与重试** | 无自动重试；异常走 `log_scheduled_job_failure`（与 `_job_strategy_zao_chen_shi_zi_xing_daily` 相同） |
| **日志与可观测** | Job 内 `logger.info` 记录 `as_of_date`、完成或跳过原因（非交易日、数据未就绪） |

### 其他关键设计

1. **`strategy_id`**：`di_wei_lian_yang`；**类名**：`DiWeiLianYangStrategy`；**version**：建议 `v1.0.0` 起。  
2. **`describe().route_path`**：`/strategy/di-wei-lian-yang`。  
3. **`_Params`**：与早晨十字星对齐的字段名：`stop_loss_pct=0.08`、`arm_profit_trigger_pct=0.15`、`trailing_stop_pct=0.05`、`min_first_yin_drop_pct`、`max_close_to_cum_hist_high_ratio`、`weak_lookback_days`、`min_bearish_days_in_lookback`、`min_prior_window_cumulative_drop_pct`、`min_yang_body_gain_pct`、`max_hammer_day_close_pct`（路径 A T−1 锤头日相对 T−2 收盘 ±1%）、红三兵 `max_small_yang_body_pct=0.04`、夹阴 `max_small_yin_body_pct=0.04`、十字星 `max_doji_body_to_range=0.1`。  
4. **文档同步**：实现完成后将 `specs/021-低位连阳/spec.md` 顶部 **状态** 改为「已实现」，并勾选/更新 `checklists/requirements.md` 若需。  
5. **可选**：`contracts/strategy-api.md` 若其他策略有同类契约可追加 `di_wei_lian_yang` 条目；**非阻塞**。

## 项目结构

### 本功能文档

```text
specs/021-低位连阳/
├── spec.md              # 功能规格（已实现后改状态）
├── plan.md              # 本文件
├── checklists/
│   └── requirements.md  # 规格质量清单
├── quickstart.md        # 可选：由实现者补充 curl / 页面验证步骤
└── tasks.md             # 由 /speckit.tasks 生成（若使用）
```

### 源码结构（增量）

```text
backend/app/services/strategy/strategies/di_wei_lian_yang.py   # 新建：内核 + 策略类
backend/app/services/strategy/registry.py                      # 注册
backend/app/services/strategy/strategy_descriptions.py       # 文案
backend/app/core/scheduler.py                                # 定时 Job + start_scheduler 注册
backend/tests/test_di_wei_lian_yang.py                       # 新建：单元测试

frontend/src/views/DiWeiLianYangView.vue                       # 新建
frontend/src/router/index.ts                                   # 路由
frontend/src/views/Layout.vue                                  # 菜单
frontend/src/components/BacktestResultDetail.vue               # Tooltip 文案
```

## 测试与验收建议

1. **`GET /api/strategies`**：响应中含 `di_wei_lian_yang` 与中文名「低位连阳」。  
2. **`POST /api/backtest/run`**：`strategy_id=di_wei_lian_yang`，区间选含已知样本，检查 `trigger_date`、`extra.pattern_path`、`buy_price` 与路径规则一致。  
3. **路径 B**：构造 `T+1` 超出 `end_date` 的样本，应无成交。  
4. **路径 A**：自 T 起永不 `close>MA5`，应无 `buy_date`。  
5. **卖出**：对固定 `buy_price` 做持仓仿真表测试，止损价与移动止盈触发与早晨十字星用例对齐。  
6. **回归**：跑一条「早晨十字星」回测确保未因 `is_hammer_bar` import 路径调整而破坏（若仅 import 不变则无影响）。

## 复杂度与例外

无章程违反项。路径三合一增加分支复杂度，通过**互斥分支 + 独立小函数**控制；卖出逻辑**强制与早晨十字星同一实现片段**以降低漂移风险。
