# 实现计划：策略选股（冲高回落战法）

**分支**: `main` | **日期**: 2026-03-25 | **规格**: `./spec.md`  
**输入**: 功能规格来自 `specs/009-策略选股/spec.md`

**说明**: 本模板由 `/speckit.plan` 命令填写。全文须使用**中文**，且达到**可直接按方案实现**的粒度。

## 概要

本期交付“策略选股”能力：在侧边栏新增一级菜单“策略选股”，二级菜单“冲高回落战法”。用户进入策略页面后可一键执行策略，系统基于数据库中的 A 股日线数据计算并返回候选股票列表与信号事件。

本期**不交付历史回测**页面与回测执行，但在后端数据结构上必须为未来回测预留：每次策略执行需要写入“策略执行快照”与“信号事件”，并记录策略版本、参数与数据口径，确保未来回测能复用与复现。

## 技术背景

- **语言/版本**: Python（版本以项目现状为准），TypeScript 5.x
- **主要依赖**: FastAPI、SQLAlchemy、MySQL；Vue 3、Vite、Element Plus、Pinia、Axios
- **存储**: MySQL
- **测试**: pytest（前端暂未引入专用测试框架，按项目现状）
- **目标平台**: 本地部署（开发机）+ 现代浏览器
- **项目类型**: Web 应用（前后端分离）
- **性能目标**:
  - 策略执行：在“最新交易日”数据已就绪的情况下，冲高回落战法执行在 3 秒内返回首屏结果（以 5000 只标的估算）
  - 列表展示：前端分页/虚拟化避免一次性渲染过多行
- **约束**:
  - 仅日/周/月数据，暂无分时数据；“开盘买入/卖出”口径按日线开盘价解释
  - 策略由代码实现，用户不能在界面配置策略逻辑
- **规模/范围**: A 股全市场（约 5000+ 标的），单用户/少量用户并发

## 章程检查

`backend/.specify/memory/constitution.md` 当前为占位模板，未包含已核定的强制原则与门禁条款，因此本计划按项目既有规范执行（中文文档、Spec 驱动、避免超范围交付）。

## 关键设计详述

### 数据流与接口职责

#### 前端页面与路由

- **侧边栏菜单**：在 `frontend/src/views/Layout.vue` 增加一级菜单“策略选股”，二级菜单“冲高回落战法”。
- **路由**：在 `frontend/src/router/index.ts` 增加策略页面路由，例如：
  - `/strategy`（可选：策略列表/入口页，若暂不做列表，可直接省略）
  - `/strategy/chong-gao-hui-luo`（冲高回落战法页）
- **策略页面职责**：
  - 展示策略说明（核心理念摘要、适用场景、风险提示、数据口径）
  - 提供“执行/刷新”按钮与可选参数（本期建议仅提供“截止时间点 as_of_date（可选）”，默认取数据库最新交易日）
  - 展示执行元信息（截止时间点、策略版本、口径）与结果列表（即“今日符合冲高回落”的列表）

#### 后端接口（本期）

为避免与“综合选股（stock screening）”混淆，建议新增独立路由前缀 `GET/POST /api/strategies/...`。

1) **列出内置策略**

- `GET /api/strategies`
- **响应**：策略列表（id、名称、版本、简介、入口路径）

2) **获取策略详情**

- `GET /api/strategies/{strategy_id}`
- **响应**：策略说明（含口径说明、风险提示），用于策略页面展示

3) **执行策略（生成结果 + 写入快照/事件）**

- `POST /api/strategies/{strategy_id}/execute`
- **请求参数**（JSON）：
  - `as_of_date`（可选，YYYY-MM-DD）：截止时间点；不传则后端从 `stock_daily_bar` 取最大 `trade_date`
  - `dry_run`（可选，默认 false）：为调试/预演准备；若 true 则不落库（本期可不实现，作为扩展点）
- **响应**：
  - `execution`：执行快照元信息（execution_id、strategy_id、strategy_version、as_of_date、market=A 股、price_adjustment、assumptions）
  - `items`：候选股票列表（即“今日符合冲高回落”的列表）
  - `signals`：信号事件列表（触发/买入/卖出/过滤），便于未来回测复用
- **错误约定**：
  - 400：参数不合法（日期格式、日期超范围等）
  - 409：数据未就绪（例如 `stock_daily_bar` 为空）
  - 500：服务异常

#### 数据流（后端内部）

- API 层（FastAPI router）只负责参数校验与响应组装
- Service 层负责：
  - 获取 `as_of_date`（默认最新交易日）
  - 调用策略实现类（代码）执行策略
  - 产出：候选股票 + 信号事件 + 执行口径
  - 写入 DB：
    - `strategy_execution_snapshot`
    - `strategy_signal_event`
    - `strategy_selection_item`（落库“今日符合冲高回落”的候选明细）
- 数据查询层：复用现有 `StockDailyBar`（日线）与 `StockBasic`（股票名称等）表

### 定时任务与部署设计

本功能涉及定时任务（每日自动筛选冲高回落）。

- **使用的组件**: APScheduler（`backend/app/core/scheduler.py`，项目已在 `app.main` 的 lifespan 中调用 `start_scheduler()` 注册任务）
- **注册方式**:
  - 在 `backend/app/core/scheduler.py` 的 `start_scheduler()` 中新增一个 job（例如 `_job_strategy_chong_gao_hui_luo_daily`）
  - 由 `backend/app/main.py` 的 lifespan 启动时调用 `start_scheduler()`，从而注册并启动调度器
- **调度策略**:
  - 建议交易日每日 **17:20**（在项目现有 17:00 数据同步之后）执行
  - Cron：`20 17 * * *`（以 `Asia/Shanghai` 时区运行）
- **部署时是否执行一次**: 否（避免在服务重启时重复生成“今日结果”）
- **手动触发方式**: HTTP 接口（面向页面按钮）
  - [x] HTTP 接口：`POST /api/strategies/chong_gao_hui_luo/execute`（登录用户可用）
- **失败与重试**:
  - 失败不自动重试（避免在外部数据未就绪时反复执行）；失败写日志，下一次调度再执行
  - 若当日为非交易日或当日数据未同步完成：任务应跳过并记录原因
- **日志与可观测**:
  - 每次任务记录：是否执行/跳过、as_of_date、写入 execution_id、候选数量、事件数量、耗时
  - 发生异常时使用项目既有 `log_scheduled_job_failure(...)` 记录上下文

### 其他关键设计

#### 1) 策略注册与版本管理（为未来回测做准备）

- 后端提供一个“策略注册表”（纯代码，不入库）：`strategy_id -> 策略类`
- 每个策略必须提供：
  - `strategy_id`（稳定标识，例如 `chong_gao_hui_luo`）
  - `strategy_version`（语义化版本，例如 `v1.0.0`，策略逻辑变更时递增）
  - `describe()`（返回用于前端展示的说明文本）
  - `execute(as_of_date)`（返回候选与信号事件）
- 执行落库时必须写入 `strategy_version`，以便未来回放复现

#### 2) 冲高回落战法的计算口径（无分时数据）

以 `stock_daily_bar` 的日线字段实现：

- “大涨”：以“从开盘价到最高价的最大涨幅”判断：\((high - open) / open \ge 10%\)。
- “最近 10 天第一根大阳”：向前回看 10 个交易日，确保不存在任何一天满足 \((high - open) / open \ge 10%\)（用于保证“第 0 天”为第一根）。
- “冲高回落至少 3 个点”：用 \((high - close) / high\) 或 \((high - close) / prev_close\) 之一，需在 `research.md` 固化口径并在执行快照中记录；本期先采用 **(high-close)/high** 作为“从最高点回落比例”
- “第 1 天低开至少 3 个点”：用 \((open_1 - prev_close_0) / prev_close_0\) 判断（<= -3%）
- “开盘买入/卖出”：由于无分时数据，信号事件中记录“开盘口径”，未来接入分时数据可升级

#### 3) 结果落库的数据结构（本期必须实现）

本期即便不做回测，也必须落库以下两类数据，避免未来返工：

- `strategy_execution_snapshot`：一次执行的元信息与口径（策略版本、参数、截止时间点）
- `strategy_signal_event`：策略产生的事件（触发/买入/卖出/过滤/备注），与股票与日期绑定，用于“回顾当时的操作现场”与未来回测复现
- `strategy_selection_item`：候选股票列表明细（用于页面展示与审计）

## 项目结构

### 本功能文档

```text
specs/009-策略选股/
├── plan.md              # 本文件
├── research.md          # Phase 0 调研结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 本地运行与验证
├── contracts/           # Phase 1 接口契约
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── api/             # FastAPI 路由（本功能新增 strategies.py）
│   ├── models/          # SQLAlchemy 模型（本功能新增执行快照/信号事件/候选明细）
│   ├── schemas/         # Pydantic schema（本功能新增策略与执行响应）
│   ├── services/        # 业务服务（本功能新增策略注册表与冲高回落实现）
│   └── ...
└── scripts/             # DB 初始化 SQL（本功能新增建表脚本）

frontend/
├── src/
│   ├── router/          # 路由（新增策略页 route）
│   ├── views/           # 页面（新增冲高回落战法页）
│   ├── components/      # 结果表格/元信息卡片等复用组件
│   └── api/             # Axios 封装（新增 strategies.ts）
└── ...
```

**结构说明**: 本功能遵循项目现有分层：前端路由/页面负责展示与交互；后端 router 负责参数校验；services 负责策略执行；models/schemas 负责落库与响应结构，便于未来扩展到历史回测时复用同一套执行记录与事件结构。

## 复杂度与例外

无。

