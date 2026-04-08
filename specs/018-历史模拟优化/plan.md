# 实现计划：历史模拟优化

**分支**: `018-历史模拟优化` | **日期**: 2026-04-06 | **规格**: [spec.md](./spec.md)  
**输入**: 功能规格来自 `/specs/018-历史模拟优化/spec.md`

**说明**: 全文为中文，粒度达到可直接按方案实现。

## 概要

在现有历史模拟链路（`strategy.backtest` → 补充维度 → 写入 `simulation_task` / `simulation_trade`）上，补齐**买入日大盘温度**落库，使交易明细具备与**历史回测**相同的分析维度；新增与回测对称的 **筛选复算**、**分年度分析** API；任务完成时可选写入**温度/交易所/板块**分组摘要至 `assumptions_json`。前端在 `SimulationResultDetail` 增加温度、年份筛选及分年/筛选后指标展示，并强化与回测差异的 Tooltip。

不涉及定时任务；不涉及新的外部 HTTP 数据源。

## 技术背景

- **语言/版本**: Python 3.12；TypeScript 5.x；Vue 3。
- **主要依赖**: FastAPI、SQLAlchemy、MySQL；Element Plus。
- **存储**: MySQL；表 `simulation_task`、`simulation_trade`（本期扩展 `simulation_trade` 列）。
- **测试**: pytest（后端关键纯函数与筛选逻辑）；前端以接口联调与手测为主（与项目现状一致）。
- **目标平台**: 本地/服务器后端 + 现代浏览器前端。
- **项目类型**: Web 应用（前后端分离）。
- **性能目标**: 与现网回测筛选一致——单次筛选/分年在单任务明细上内存计算，明细量级与回测同一数量级；若明细超万笔，沿用现有分页与「先筛再聚合」策略。
- **约束**: 不改变策略 `backtest()` 数学定义；不在模拟引擎中引入资金仿真。
- **规模/范围**: 全市场策略扫描区间与现模拟一致；用户单租户。

## 章程检查

**未核定，无强制门禁**：仓库内 `constitution.md` 仍为模板占位，本功能不引入额外章程冲突。设计完成后复检：无违背「Spec 与实现同步」——实现时需同步本目录 `spec.md` 状态（若产品验收有变更）。

## 关键设计详述

### 数据流与接口职责

1. **模拟执行（已有，改造）**  
   - 入口：`POST /api/simulation/run`（`backend/app/api/simulation.py`）。  
   - 后台线程：`app.services.backtest.simulation_engine.run_simulation`。  
   - **改造点**：在调用 `enrich_trades_with_stock_dimension` **之前**增加 `enrich_trades_with_temperature`（与 `backtest_engine.run_backtest` 顺序一致：先温度后交易所/板块）。  
   - 持久化：`SimulationTradeModel` 增加 `market_temp_score`、`market_temp_level` 字段赋值；`extra_json` 策略扩展字段逻辑不变。

2. **任务汇总（改造）**  
   - 任务完成时除现有 `total_trades`、`win_rate` 等外，调用 `backtest_report.calculate_temp_level_stats` / `calculate_exchange_stats` / `calculate_market_stats`（入参为已 enrich 的 `BacktestTrade` 列表，与回测相同数据结构），将结果写入 `task.assumptions_json` 的约定键名，与 `BacktestTask` 详情中前端已消费的键名对齐（见 `backtest_engine` 中 `assumptions_base`）。  
   - 若 `calculate_*` 函数强依赖回测专属字段，可只传入模拟侧已闭合且 `closed` 的 `BacktestTrade` 列表。

3. **交易明细列表（扩展）**  
   - `GET /api/simulation/tasks/{task_id}/trades`：增加 Query `market_temp_levels`（逗号分隔）、`year`（自然年）；筛选逻辑与 `backtest.api._apply_trade_filters` **完全一致**（建议抽取共用函数，见下）。  
   - 响应项 `SimulationTradeItem` 增加 `market_temp_score`、`market_temp_level`。

4. **新增接口（与回测对称）**  
   - `GET /api/simulation/tasks/{task_id}/filtered-report`：参数与 `GET /api/backtest/tasks/{task_id}/filtered-report` 一致（`trade_type`、`market_temp_levels`、`markets`、`exchanges`、`year`）；响应体与 `BacktestFilteredReportResponse` **同构**（可复用同一 Pydantic 模型或新建别名模型字段完全一致）。  
   - `GET /api/simulation/tasks/{task_id}/yearly-analysis`：参数与 `GET /api/backtest/tasks/{task_id}/yearly-analysis` 一致；响应与 `BacktestYearlyAnalysisResponse` 同构。  
   - 实现：对 `SimulationTradeModel` 查询应用同一套筛选 → 行列表传入与 `_calculate_metrics_from_rows` 等价的函数（抽取为 `app/services/trade_metrics.py` 或并入现有 `backtest_report` 中的无状态函数）。

5. **前端**  
   - `frontend/src/api/simulation.ts`：扩展 `getSimulationTrades` 参数；新增 `getSimulationFilteredReport`、`getSimulationYearlyAnalysis`（或共用类型名从 `backtest` 类型导入若完全一致）。  
   - `SimulationResultDetail.vue`：  
     - 明细表增加「温度分数/级别」列（或与回测列一致）；  
     - 筛选栏增加温度多选、买入年份（与回测控件数据源一致时可复用常量）；  
     - 增加「筛选后指标」卡片（调 `filtered-report`）与「分年度分析」表格（调 `yearly-analysis`）；加载顺序与回测页一致。  
   - `SimulationConfigPanel.vue`：Tooltip 增加一句「历史模拟不进行资金仿真，统计全部符合条件的闭仓交易；与历史回测的仓位仿真可能笔数不同」。

**错误约定**：与现 API 一致，使用 `HTTPException` + `detail: { code, message }`；`404 TASK_NOT_FOUND`。

### 定时任务与部署设计

本功能不涉及定时任务。

### 其他关键设计

- **共用筛选与指标**  
  - 从 `backend/app/api/backtest.py` 抽出 `_apply_trade_filters` 与 `_calculate_metrics_from_rows` 至新模块（例如 `backend/app/services/trade_query_metrics.py`），以 **泛型或双模型适配** 方式同时支持 `BacktestTradeModel` 与 `SimulationTradeModel`（两表对应字段名已对齐）。  
  - `backtest.py` 与 `simulation.py` 仅保留薄封装路由，避免两处 OR 条件逻辑分叉。

- **缺失温度**  
  - 买入日无 `MarketTemperatureDaily` 记录时，`market_temp_level` 为 `NULL`；  
  - 多选温度筛选时，若需包含「未知」，与回测约定一致（若回测当前无「未知」档，则本功能与回测同步补产品规则，默认：**仅匹配已选级别，NULL 不参与任何具体级别**）。

- **旧数据**  
  - 迁移前已落库的 `simulation_trade` 温度列为空；可选提供一次性 `backend/scripts/backfill_simulation_trade_temperature.sql` 或 Python 脚本按 `buy_date` 回填，不作为 P1 阻塞。

- **Schema**  
  - `backend/app/schemas/simulation.py`：`SimulationTradeItem`、`SimulationTaskDetailResponse` 等按需扩展；`filtered-report` 响应优先复用 `schemas/backtest.py` 中已有 `BacktestFilteredMetrics` / `BacktestFilteredReportResponse`（若命名上「Backtest」易引起歧义，可定义 `FilteredReportResponse` 别名导出）。

## 项目结构

### 本功能文档

```text
specs/018-历史模拟优化/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/           # Phase 1 接口契约
│   └── simulation-analysis-api.md
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/
│   │   ├── simulation.py       # 扩展 trades 参数；新增 filtered-report、yearly-analysis
│   │   └── backtest.py         # 改为调用共用 trade_query_metrics（可选重构）
│   ├── models/
│   │   └── simulation_trade.py # 新增温度列
│   ├── schemas/
│   │   └── simulation.py       # SimulationTradeItem 扩展
│   └── services/
│       ├── backtest/
│       │   ├── simulation_engine.py  # enrich 温度 + 落库 + assumptions_json 分组
│       │   └── backtest_report.py    # 复用 calculate_* 统计
│       └── trade_query_metrics.py    # 新建：共用筛选与指标（推荐）
└── scripts/
    └── xxxx_add_simulation_trade_temperature.sql  # 新增迁移 SQL

frontend/
├── src/
│   ├── api/
│   │   └── simulation.ts       # 新 API 与类型
│   └── components/
│       └── SimulationResultDetail.vue
│       └── SimulationConfigPanel.vue
```

**结构说明**：共用逻辑放在 `services/trade_query_metrics.py` 避免 `simulation` 与 `backtest` 两套筛选；若抽取风险高，可先复制筛选逻辑并加注释「须与 _apply_trade_filters 同步」，第二迭代再合并。

## 复杂度与例外

无需填写（无章程违反项）。

## 章程复检（设计完成后）

- 实现阶段完成后更新 `specs/018-历史模拟优化/spec.md` 中**状态**为「已实现」或等价说明（与仓库 Spec 驱动约定一致）。  
- 新增/变更的 HTTP 契约与 `contracts/simulation-analysis-api.md` 保持一致。
