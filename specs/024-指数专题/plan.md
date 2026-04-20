# 实现计划：指数专题

**分支**: `main`（规格目录 `024-指数专题`） | **日期**: 2026-04-18 | **规格**: [`spec.md`](./spec.md)

**输入**: `specs/024-指数专题/spec.md` 及 **Clarifications Session 2026-04-18**（非 ETF、指数仿真 T+1、无个股涨跌停拦截、成分仅详情、`index_weight`、全量展示）。

**说明**: 全文中文，粒度达到**可直接按本方案实现**。若实现中发现与 Tushare 积分/限量冲突，以本计划「外部依赖与失败模式」章节调整批处理与监控，并同步更新 `spec.md` 假设。

## 概要

构建**指数基础信息 + 日/周/月 K 线入库与指标填充 + 专题列表 API + 前端「指数基金」菜单页（对齐综合选股交互层级）+ 成分权重详情接口（含指数详情内**指数 PE 百分位**：由成分权重与个股 `pe_percentile` 加权推理）+ 历史模拟交易/回测对指数标的的贯通**。

**持久化结论（回应 FR-008）**：采用**独立表族** `index_basic`、`index_daily_bar`、`index_weekly_bar`、`index_monthly_bar`、`index_weight`（及可选 `index_weight_sync_meta`），**不与** `stock_daily_bar` 混用单表加 `type` 字段。理由：`stock_code` 与指数 `ts_code` 命名空间与业务校验分支不同；混表将拖长个股查询路径并放大索引；周线/月线已与个股分表一致，指数侧保持对称更易维护。现有 `market_index_daily_quote` + `INDEX_CODES` 仍为**大盘温度**服务：实现阶段评估**双写**（新指数日线写入 `index_daily_bar` 且温度仍读旧表）或**迁移温度读新表**（推荐最终统一从 `index_daily_bar` 按代码取数，减少重复存储），在任务清单中择一固化。

**仿真规则（回应规格）**：历史模拟交易中，标的若解析为**指数**（存在于 `index_basic`），则成交路径使用 `index_daily_bar`；**保留 T+1**；**跳过** `_validate_price`（个股涨跌停）；`prev_close` 仍用于展示与必要时其他校验。名称解析优先 `index_basic.name`，不再要求 `StockBasic` 命中。

## 技术背景

- **语言/版本**: Python 3.12、TypeScript、Vue 3（与仓库一致）
- **主要依赖**: FastAPI、SQLAlchemy、MySQL、APScheduler、pandas（若批处理对齐个股指标）
- **存储**: MySQL；新增指数相关表（见 [`data-model.md`](./data-model.md)）
- **测试**: `pytest`（服务层单元测试 + 少量 API 集成测试）；关键规则：指数买入不触发涨跌停错误码
- **目标平台**: 浏览器 + 现有后端部署方式
- **性能目标**: 专题列表首屏与综合选股同量级（分页查询、索引命中 `index_code + trade_date`）；全量指数下**禁止**无分页一次拉全表到前端
- **约束**: Tushare `index_daily` 单次最多约 8000 行、`index_weekly`/`index_monthly` 单次最多 1000 行；全市场 `index_basic` 需按 `market` 分批；积分与频次以账号为准
- **规模**: 指数全量可达数千级（随 Tushare 返回）

## 章程检查

遵循项目 **简体中文**注释/规格、**spec 与实现同步**；策略类本期以**接入指数回测数据源**为主，若新增指数专用策略类须按策略类注释规范编写。前端新页须在标题区提供**悬浮能力说明**（`FR-007`）。

## 关键设计详述

### 数据流与接口职责

#### 整体数据流

```
Tushare index_basic / index_daily / index_weekly / index_monthly / index_weight
    → 同步编排服务（增量 + 可回灌）
         → MySQL 指数表族
              → GET /api/index/screening（列表，分页）
              → GET /api/index/screening/latest-date
              → GET /api/index/{ts_code}/composition（详情抽屉：成分权重 + **指数 PE 百分位推理**）
              → 历史模拟：paper_trading_service 解析 ts_code → 指数 K 线分支
              → 回测引擎：按标的类型选择 index_*_bar 查询路径
```

#### Tushare 映射要点

| 接口 | 用途 | 限量/注意 |
|------|------|-----------|
| `index_basic` | 全量标的清单，多 `market` 参数循环 | 字段见 [doc 94](https://tushare.pro/document/2?doc_id=94) |
| `index_daily` | 日线 | 单次 ≤8000 行，按 code + 区间分段拉取 |
| `index_weekly` | 周线 | 单次 ≤1000 行 |
| `index_monthly` | 月线 | 单次 ≤1000 行；描述为每月更新 |
| `index_weight` | 成分与权重 | 月度；建议按指数 + 当月区间拉取 |

日线字段含 `pre_close`、`pct_chg` 等，入库时写入 `index_daily_bar`，与个股列级对齐展示（价格为**点位**）。

#### 后端分层（建议路径）

| 层级 | 路径（建议） | 职责 |
|------|----------------|------|
| 模型 | `backend/app/models/index_basic.py`、`index_daily_bar.py`、`index_weekly_bar.py`、`index_monthly_bar.py`、`index_weight.py` | SQLAlchemy 映射 |
| Tushare | `app/services/tushare_client.py` | 已有 `get_index_daily_range`；补充 `index_basic`、`index_weekly`、`index_monthly`、`index_weight` 封装（含重试与 DataFrame 转 dict） |
| 同步 | `app/services/index_sync/`（新建包）或 `index_sync_service.py` | `run_index_basic_sync`、`run_index_daily_incremental`、`backfill_range`；周线/月线在日线就绪后或与个股相同「按交易日触发增量」 |
| 指标 | 复用个股「均线/MACD」填充函数的模式 | 对 `index_daily_bar` 批量重算或与 `stock` 共用纯函数入参为 OHLCV 序列 |
| API | `app/api/index.py`（新建），路由前缀 `/api/index` | screening、latest-date、composition |
| 选股服务 | `app/services/index_screening_service.py` | 对标 `screening_service.list_screening`，数据源换为指数表 |
| 指数 PE 推理 | `app/services/index_pe_percentile_service.py`（或并入 composition 依赖模块） | 成分权重 × `stock_daily_bar.pe_percentile` 加权重归一；供 `GET .../composition` 组装 |
| 模拟交易 | `app/services/paper_trading_service.py` | `_get_daily_bar_or_index_bar`、买入/卖出前分支 `is_index_ts_code`、指数跳过涨跌停校验 |
| 回测 | `app/services/backtest/`（视现有结构） | 标的解析后分支加载 `index_daily_bar` |

#### API 契约（摘要）

**GET `/api/index/screening`**

- **鉴权**: `get_current_user`（与 `/api/stock/screening` 一致）
- **Query**: `page`、`page_size`（上限 100）、`timeframe`: `daily|weekly|monthly`、`code`、`name`（模糊）、`data_date`（可选快照日）；技术指标筛选可与综合选股对齐的可选布尔参数（实现时对照 `screening_service` 裁剪）
- **响应**: `{ items: [...], total, page, page_size, timeframe, data_date }`  
  - `items` 字段集合**对标** `ScreeningItem` 中与 K 线相关的列（PE/PB 等可无或置空）；增加 `instrument_type: "index"` 或文档约定全部为指数

**GET `/api/index/screening/latest-date`**

- **Query**: `timeframe`
- **响应**: 与 `LatestDateResponse` 同形

**GET `/api/index/{ts_code}/composition`**

- **用途**: 详情抽屉拉取成分（`FR-009`）并返回**指数 PE 百分位**（`FR-010`）
- **Query**: 
  - `trade_date` 可选：用于对齐 **个股日线快照日**，从 `stock_daily_bar` 取各成分 `pe_percentile`；默认取专题列表当前使用的「最近可用交易日」或与用户上下文一致。
  - `weight_as_of` 可选：若不传，权重取 **`index_weight.trade_date` ≤ `trade_date` 的最新一期**（保证展示日已有权重口径）；若本期简化实现，可仅用「库中最新权重」并在响应 `meta` 中返回权重表日期。
- **响应**（扩展）：  
  - `items`: `[{ con_code, weight, pe_percentile | null }, ...]`（`pe_percentile` 可为空便于表格展示剔除情况）  
  - `index_pe_percentile`: `number | null` — 加权推理结果，量纲与个股 PE 百分位一致（通常 0～100）  
  - `pe_percentile_meta`: `{ formula: "weighted_mean", snapshot_trade_date, weight_table_date, participating_weight_ratio, constituents_with_pe }` — 便于前端提示「推理依据与覆盖率」  
- **计算逻辑（须与 `spec.md` Clarifications 一致）**：  
  设展示参考日为 \(T\)，可选用权重日为 \(W\)（权重行按上款选取）。对每个成分 \(i\)：权重 \(w_i\)（百分比或小数需与 Tushare 返回一致后**归一为和=1**），在 \(T\) 日从 `stock_daily_bar` 取 `pe_percentile_i`（仅 A 股普通代码且库内格式与 `stock_code` 对齐）。  
  **指数 PE 百分位** = \(\sum_{i \in S} \tilde{w}_i \cdot pe\_percentile_i\)，其中 \(S\) 为「`pe_percentile_i` 非空」的成分集，\(\tilde{w}_i = w_i / \sum_{j \in S} w_j\)（剔除缺失后重归一）。若 \(\sum_{j \in S} w_j = 0\) 或 \(S\) 为空，`index_pe_percentile` 为 `null`。  
- **代码规范化**：`index_weight.con_code` 可能与 `StockBasic.code` 写法差异（后缀大小写），统一走与现有选股/模拟交易相同的 **ts_code 规范化函数**后再 join。  
- **性能**：单次详情请求成分数上限高时可只算一遍；可选异步缓存键 `(ts_code, trade_date, weight_revision)`。

**错误约定**: 与全局一致；400 带 `code/message` JSON。

#### 前端职责

| 页面/组件 | 职责 |
|-----------|------|
| `Layout.vue` | 增加子菜单「指数基金」，路由如 `/index-fund` |
| 新视图 `IndexScreeningView.vue`（命名可与菜单一致） | 对标 `StockScreeningView.vue`：表格列、分页、周期切换、`latest-date` 展示、标题旁 `el-tooltip` 能力说明（含：点位非元、指数仿真边界、成分在详情） |
| `api/index.ts` | 封装 screening、latest-date、composition |
| 详情抽屉 | 行点击或「详情」打开 `el-drawer`，内嵌成分表 + 异步加载 `/composition`；顶部或摘要区展示 **指数 PE 百分位** + `el-tooltip` 说明「成分加权推理、非官方」 |

### 定时任务与部署设计

- **使用的组件**: **APScheduler**（`backend/app/core/scheduler.py`），与现有股票同步并存。
- **注册方式**: 在 scheduler 初始化处 `add_job`（与 `_job_sync_stock` 同级或作为子任务挂到 `sync_task` 体系——若沿用 `sync_task` 驱动，则增加 `index_basic`/`index_daily` 子任务类型并在 `execute_pending_auto_sync` 链式或并行执行；**最小可行**为独立 cron job，避免一次改太大时可先独立定时任务）。
- **调度策略**: 建议 **交易日 17:05**（股票主同步之后）执行**指数增量**；周线/月线可 **17:15** 或并入同一 job 内顺序执行。具体 cron：`minute=5, hour=17` 等，时区 `Asia/Shanghai`。
- **部署时是否执行一次**: **否**（默认）；可选「启动后延迟触发一次指数 basic」仅在开发文档说明，避免生产风暴。
- **手动触发方式**（至少一种）:
  - [x] **脚本**: `python -m app.scripts.sync_index`，参数：`--mode incremental|backfill`、`--start-date`、`--end-date`、`--modules basic daily weekly monthly weight`；**白名单**：`--preset common`（上证 `000001.SH`、深证成指 `399001.SZ`、创业板 `399006.SZ`、科创50、沪深300 `000300.SH`、中证500 `000905.SH`）或 `--ts-codes` 逗号分隔自定义。**清空指数表数据**（保留表结构）：执行 `backend/scripts/truncate_index_tables.sql` 后再按需白名单回灌。
  - [x] **HTTP**（可选）: `POST /api/admin/index-sync` 需与现有 admin 鉴权一致；若无统一 admin，则仅用脚本 + 运维手动执行。
- **失败与重试**: Tushare 调用失败：**最多 3 次**指数退避重试（与 `tushare_client` 一致）；单日任务失败写入 `sync_job_run` 或日志表；**不全量回滚**已写入批次。
- **日志与可观测**: 每条任务记录 **拉取代码数、写入行数、耗时**；异常打 `ERROR` 并带 `ts_code` 片段。

### 指数同步批处理策略（全量展示）

1. **`index_basic`**: 按 `market`（SSE/SZSE/SW/CSI…）循环调用，结果 upsert；去重键 `ts_code`。
2. **`index_daily`**: 对每个 `ts_code` 增量区间 `[last_trade_date+1, latest_trade_date]`；若区间过长按 **≤7000 交易日**切段（预留余量）。
3. **周线/月线**: 按代码增量拉取；注意1000行限制切段。
4. **`index_weight`**: 按月批量；详情请求按需补拉单次指数亦可。

### 历史模拟交易改造要点

1. **解析**: `resolve_stock` 类函数扩展为「先查 `StockBasic`，若无则查 `index_basic`」，返回类型 `kind: stock|index`。
2. **日线**: `_get_daily_bar` → 拆为 `_get_stock_daily_bar` / `_get_index_daily_bar`；对外统一返回「含 open/high/low/close/prev_close/volume…」的适配对象（可用 **NamedTuple 或 Protocol**）。
3. **买入/卖出**: 在 `_validate_price` 前判断 `kind == index` 则 **跳过**；保留资金与数量、T+1；错误文案区分「股票涨跌停」与指数无关。
4. **持仓展示**: `_build_position_summaries` 中取参考价时，指数走 `index_daily_bar`。
5. **图表接口**: `get_chart_data` 等对 `StockDailyBar` 的查询增加指数分支（周/月同理）。
6. **前端会话页**: 搜索框支持指数代码；tooltip 标明指数仿真规则。

### 历史回测改造要点

1. 标的输入层：允许选择指数 `ts_code`（与股票并列或下拉分栏）。
2. 数据加载：若标的为指数，从 `index_daily_bar`（及策略所需区间）装载；**禁用**依赖 `cum_hist_high`、PE 等个股字段的策略需在注册层声明「仅股票」并在 UI 禁用或报错。
3. 若引擎内部存在涨跌停模拟：对指数标的 **关闭** 或与模拟交易一致跳过。

### 指数 PE 百分位（详情，`FR-010`）

- **数据源**: `index_weight`（权重）+ `stock_daily_bar.pe_percentile`（与综合选股同源，依赖个股日线已同步且 PE 百分位管线有效）。  
- **不落库（首期）**：可在 `GET .../composition` 内即时计算；若线上验证耗时超阈值，再考虑表 `index_pe_percentile_snapshot`（`ts_code`, `snapshot_trade_date`, `value`, `meta_json`）按日批量预计算。  
- **测试**: `pytest` 构造 3 个成分、给定权重与 `pe_percentile`，断言加权结果与剔除重归一行为。

### 其他关键设计

- **手续费**: 指数仿真沿用现有佣金函数（规格允许）；在指数能力 tooltip 注明「费率模型与个股一致，仅为仿真」。
- **数量单位**: 指数无「股」概念，可与现网一致仍用「手/股」整数约束保持账户公式不变，或在 UI 标注「仿真份额」；计划采用**不改变 quantity 整数类型**，避免数据库迁移会话订单表。
- **大盘温度**: `market_temperature` 使用的四条指数若已写入 `index_daily_bar`，可逐步改为单源；首期可**维持** `sync_index_quotes` 不变，避免耦合过大。

## 项目结构

### 本功能文档

```text
specs/024-指数专题/
├── spec.md
├── plan.md           # 本文件
├── data-model.md     # 表结构与字段
├── checklists/
└── contracts/        # 可选：openapi 摘要
```

### 源码结构（增量）

```text
backend/app/
├── api/index.py                 # 新建
├── models/index_*.py            # 新建若干
├── services/index_screening_service.py
├── services/index_sync_service.py（或 index_sync/ 包）
├── services/paper_trading_service.py  # 修改
├── services/tushare_client.py         # 扩展
└── scripts/sync_index.py              # 新建

frontend/src/
├── views/IndexScreeningView.vue   # 新建
├── api/index.ts                   # 新建
└── views/Layout.vue               # 菜单
```

## 外部依赖与失败模式

- **Tushare 积分不足或频次限制**: 同步任务部分失败；列表展示「最后成功同步日期」；管理端可见失败日志。
- **申万等行业指数权限**: 文档注明部分 `market` 拉取失败时跳过并记录，不阻塞其他 `market`。
- **全量代码过多**: 首次部署采用 **backfill 脚本分月/分年** 执行，避免单次 job 超时。

## 复杂度与例外

| 项目 | 说明 |
|------|------|
| 新建多表 | 规格要求指数与个股字段对齐且独立演进；混表节省表数量但查询与迁移风险更高 |
| 模拟交易分支 | 为满足 FR-005，必须在服务层显式分支，避免用「假股票代码」污染 `stock_daily_bar` |

## 验收与测试清单（开发自检）

1. `GET /api/index/screening` 分页与 `latest-date` 正常；大数据量下响应时间可接受。
2. 详情 `composition` 空数据友好；**指数 PE 百分位**在有一半成分有 `pe_percentile` 时可算且展示 `meta`；全无则为 `null`。
3. 模拟交易：指数买入卖出不受涨跌停拦截；T+1 仍生效。
4. 回测：至少一条内置/通用回测路径可在指数上跑通并出摘要。
5. **单元测试**：加权 PE 百分位公式与边界（全缺失、单成分、权重重归一）。

## 建议后续命令

- 实现任务拆解：`/speckit.tasks`（若项目启用）
- 开发完成后同步更新 `spec.md` 中「状态」与任何假设变更
