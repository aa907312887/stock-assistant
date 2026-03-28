# 实现计划：恐慌回落选股（策略选股界面）

**分支**：`main`（仓库主分支；规格目录 `012-恐慌回落选股`） | **日期**：2026-03-28 | **规格**：[spec.md](./spec.md)  
**输入**：功能规格来自 `specs/012-恐慌回落选股/spec.md`，调研结论见 [research.md](./research.md)。

**说明**：全文使用中文；细化到可直接按文档实现。**Phase 2 任务拆解**由 `/speckit.tasks` 生成 `tasks.md`，本计划止于 Phase 1 设计交付。

## 概要

在现有「策略选股」体系上，为 **恐慌回落法**（`panic_pullback`）提供与 **冲高回落** 同级的独立页面：用户可 **查询最新已落库结果**、**手动执行** 基于日线截止日的全市场扫描；列表展示 **交易所、板块、触发日** 及策略摘要字段；支持 **前端多选筛选**（交易所 OR、板块 OR、两维 AND，含 **空板块** `__EMPTY__`）。策略判定 **零重复实现**，直接调用已有 `PanicPullbackStrategy.execute` / 内部 `_run_backtest` 单日扫描，与 `specs/011-恐慌回落法/spec.md` 一致。

后端在通用 `strategy_execute_service` 中 **统一补齐** `stock_basic.exchange` / `market` 至 API 响应；**不新增**数据表。恐慌回落与冲高回落共用 **APScheduler**：交易日 **17:20（Asia/Shanghai）** 自动 `execute_strategy(panic_pullback)`。

## 技术背景

- **语言/版本**：Python 3.x（与仓库一致）、TypeScript + Vue 3（与 `frontend` 一致）
- **主要依赖**：FastAPI、SQLAlchemy、Element Plus、Vue Router、Axios
- **存储**：MySQL；复用 `strategy_execution_snapshot`、`strategy_selection_item`、`strategy_signal_event`、`stock_basic`、`stock_daily_bar` 等
- **测试**：以现有后端/前端测试惯例为准（pytest / 可选 e2e）；本计划不强制新增测试类型名
- **目标平台**：后端 Linux/容器或本机；前端现代浏览器
- **项目类型**：Web 应用（前后端分离）
- **性能目标**：单次执行与现有恐慌回落单日回测扫描同量级；首屏以「latest 只读」为主，避免不必要的重复全量扫描；具体耗时依赖库内数据量，第一版不设硬编码 SLA，但应记录日志条数便于观测
- **约束**：无分时数据；买卖口径为触发日收盘 / 次日收盘；与回测共用策略代码
- **规模/范围**：全 A 股日线（与当前回测加载范围一致），单用户登录后使用

## 章程检查

*门禁：Phase 0 调研前须通过；Phase 1 设计后复检。*

当前 `.specify/memory/constitution.md` 仍为模板占位，**视为未核定，无强制门禁**。本设计遵循仓库内 **spec 012**、**spec 011** 与 **spec 003** 的字段语义；与「主分支开发」工作流一致，不依赖特性分支。

**Phase 1 后复检**：无新增违背项；接口扩展向后兼容（仅增加可选字段）。

## 关键设计详述

### 数据流与接口职责

1. **手动执行路径**  
   - 前端：`PanicPullbackView.vue` 调 `POST /api/strategies/panic_pullback/execute`，body 可为 `{}`（截止日默认库内最新日线日期）。  
   - 后端：`api/strategies.py` → `execute_strategy(db, strategy_id="panic_pullback", as_of_date=...)`。  
   - 服务层：`get_latest_bar_date(db, "daily")` 解析截止日；调用 `PanicPullbackStrategy.execute(as_of_date=dd)`。  
   - 策略内：打开独立 `SessionLocal()`（**保持现有写法**），加载区间日线 → `_run_backtest(start=end=as_of_date)` → `_select_trigger_day` 过滤出触发日等于 `as_of_date` 的 `BacktestTrade`，转为 `StrategyCandidate` + `StrategySignal`。  
   - 落库：删除同 `execution_id` 旧行后写入 `strategy_execution_snapshot`、`strategy_selection_item`、`strategy_signal_event`（与冲高回落同一套表）。  
   - 返回前：`_candidates_to_api_items` **批量查询** `stock_basic`，为每条补充 **`exchange`、`market`**（以及名称兜底）；组装 `ExecuteStrategyResponse`。

2. **只读最新路径**  
   - 前端：进入页面时 `GET /api/strategies/panic_pullback/latest`。  
   - 后端：`get_latest_strategy_result` → join `strategy_selection_item` 与 `stock_basic`，组装 `items` 时写入 **`exchange`、`market`**（**不再**用 `exchange or market` 混填单一业务列；若需兼容字段 `exchange_type` 可填展示用拼接或仅填 `exchange`）。  

3. **响应结构**  
   - 在 Pydantic `StrategySelectionItem` 上增加 `exchange: str | None`、`market: str | None`（详见 [contracts/strategy-panic-selection-api.md](./contracts/strategy-panic-selection-api.md)）。  
   - `execution` 块保持与现有一致；确保 OpenAPI 中 `strategy_id` 等与前端类型对齐（若前端 `ExecutionSnapshot` 缺少字段，实现时补全 TS 类型）。

4. **错误约定**  
   - **409** `DATA_NOT_READY`：无可用日线截止日。  
   - **404** `NOT_FOUND`：策略不存在或 `latest` 无快照。  
   - **500** `INTERNAL_ERROR`：未捕获异常。  
   - 前端统一从 `detail.message` 提示用户（与 `ChongGaoHuiLuoView.vue` 一致）。

5. **前端筛选（不调用新 API）**  
   - 使用 `computed` 从 `items` 派生 `filteredItems`：  
     - 交易所多选集合为空 → 不筛交易所；否则 `exchange` 属于所选。  
     - 板块多选集合为空 → 不筛板块；否则若选中 `__EMPTY__`，则 `(market == null || market === '')` 命中，**或** `market` 属于其余选中值。  
     - 两维同时生效时为 **AND**。  
   - 下拉选项：`exchange` / `market` 的**去重唯一值**来自当前全量 `items`，并追加「空板块」选项（当存在空 `market` 时显示或始终显示由产品决定，建议**仅当全量结果中存在空板块时**显示该选项）。  
   - 筛选结果为空时展示文案：「当前筛选条件下无结果」（规格边界）。

6. **可选模拟收益**  
   - 在 `_select_trigger_day` 循环中，对 `trade_type == "closed"` 的 `BacktestTrade`，将 `return_rate`、`sell_date`、`sell_price` 合并进 `summary`（或写入 `StrategyCandidate.summary`）；`unclosed` 则不写收益率，避免误解。  
   - 前端表格可增加一列「模拟收益率（T+1 收盘）」带 Tooltip 说明口径。

7. **页面与导航**  
   - 新建 `frontend/src/views/PanicPullbackView.vue`（命名可按团队习惯，与路由一致即可），布局参考 `ChongGaoHuiLuoView.vue`：标题、口径卡片、执行信息卡片、筛选区、表格。  
   - `router/index.ts` 增加 `path: 'strategy/panic-pullback'`，`name` 自定。  
   - `Layout.vue` 子菜单「策略选股」下增加「恐慌回落法」菜单项。  
   - **产品能力提示**：在页面标题行末增加 `el-tooltip`（或等价），简述本页能力、**交易日 17:20 自动落选**、无分时等（遵守 `.cursor/rules/frontend-product-capability-hints.mdc`）。

8. **后端文件 touch 清单（实现时）**  
   - `backend/app/schemas/strategy.py`：`StrategySelectionItem` 增字段。  
   - `backend/app/services/strategy/strategy_execute_service.py`：`_candidates_to_api_items`、`get_latest_strategy_result` 组装逻辑。  
   - `backend/app/services/strategy/strategies/panic_pullback.py`：可选增强 `summary`（收益率字段）。  
   - 前端：`api/strategies.ts` 类型；新视图 + 路由 + 菜单。

### 定时任务与部署设计

- **使用的组件**：**APScheduler** `BackgroundScheduler`，与全站一致；位置：`backend/app/core/scheduler.py`。
- **注册方式**：在 `start_scheduler()` 内 `add_job`，应用启动时由 `main.py` lifespan / 启动流程调用 `start_scheduler()`（与现有股票同步、冲高回落定时任务相同）。
- **调度策略**：`CronTrigger(hour=17, minute=20, timezone="Asia/Shanghai")`，与 **冲高回落战法** 定时任务**同一时刻**；仅当 `get_latest_open_trade_date(today) == today` 时执行。
- **部署时是否执行一次**：**否**（与冲高回落一致，无「启动后立刻跑一次恐慌回落」的单独 DateTrigger；依赖每日 17:20）。
- **手动触发方式**：页面 **手动执行选股**；或任意可调用 `POST /api/strategies/panic_pullback/execute` 的客户端。
- **失败与重试**：捕获异常走 `log_scheduled_job_failure`；`StrategyDataNotReadyError` 仅打 info 日志跳过，不重试。
- **日志与可观测**：成功打 `恐慌回落定时筛选完成 as_of_date=...`；跳过打非交易日或数据未就绪原因。

### 其他关键设计

- **鉴权**：`strategies` 路由若已挂登录依赖，新页面沿用；与冲高回落页一致。  
- **整体失败 vs 部分结果**：规格要求数据异常时整体失败；当前策略若全市场加载成功则返回列表；若策略内部抛错则 500。不在第一版引入「部分股票缺基础信息仍展示其余」的分支，与 spec 012 假设一致。  
- **路由与策略元数据**：`PanicPullbackStrategy.describe().route_path` 已为 `/strategy/panic-pullback`，前端路由应与其一致，避免菜单与注册信息漂移。  
- **ST 股**：与回测一致，`_run_backtest` 中已排除名称以 ST 开头的标的，无需在本页单独说明逻辑，仅在 Tooltip 中可写「已排除 ST 名称股票」若需透明。

## 项目结构

### 本功能文档

```text
specs/012-恐慌回落选股/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/           # Phase 1 接口契约
│   └── strategy-panic-selection-api.md
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/
│   │   └── strategies.py              # 已有：panic_pullback 走通用 execute/latest
│   ├── core/
│   │   └── scheduler.py             # 交易日 17:20 自动 execute_strategy(panic_pullback)
│   ├── schemas/
│   │   └── strategy.py                # 扩展 StrategySelectionItem
│   ├── services/
│   │   └── strategy/
│   │       ├── strategy_execute_service.py   # 补全 exchange/market
│   │       ├── registry.py            # 已注册 PanicPullbackStrategy
│   │       └── strategies/
│   │           └── panic_pullback.py # 可选：summary 增加收益率
│   └── models/
│       ├── strategy_execution_snapshot.py
│       ├── strategy_selection_item.py
│       └── stock_basic.py
└── tests/                              # 按需补充

frontend/
├── src/
│   ├── views/
│   │   ├── Layout.vue                  # 策略选股子菜单
│   │   ├── ChongGaoHuiLuoView.vue      # 参考模板
│   │   └── PanicPullbackView.vue       # 本功能新建
│   ├── router/
│   │   └── index.ts
│   └── api/
│       └── strategies.ts               # 类型扩展
└── tests/
```

**结构说明**：策略逻辑集中在 `services/strategy`；HTTP 层保持薄；前端按视图 + API 模块划分，与现有「策略选股」页面一致，便于复制交互模式并降低维护成本。

## 复杂度与例外

无。章程未核定且无额外违反项，不填例外表。
