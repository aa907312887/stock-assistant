# Research: 综合选股

**Feature**: 002-综合选股 | **Date**: 2025-03-15

## 1. Tushare 数据源与本期数据范围

**Decision**: 数据源以 `docs/Tushare股票接口接入文档.md` 与 [Tushare Pro](https://tushare.pro/) 为准；本期使用 `stock_basic`（上市列表）+ `daily`（按交易日一次性拉全市场日线）+ `income`（按标的利润表）落库，字段以 Tushare 返回为准。

**Rationale**:
- `daily` 支持按 `trade_date` 拉取当日全市场，减少逐标的请求次数；`income` 仍按 `ts_code` 调用，需在 service 层节流以适配积分与频率限制。
- 本期筛选仅基础+行情+基本面，技术面下一期；优先保证：基础（代码、名称、交易所）、行情（开高低收、涨跌额/幅、成交量额、振幅等）、基本面（利润表口径：营收、净利润、EPS、毛利率等）。

**Alternatives considered**:
- 保留 HTTP 自建数据源：维护成本高；统一用官方 SDK。
- 使用其他数据源：与当前 spec「Tushare」口径不一致时不采纳。

---

## 2. 定时任务与拉数策略

**Decision**: 使用 APScheduler 在进程内注册每日 17:00 的 cron 任务，调用「Tushare 拉数」服务；部署时执行一次全量拉数（与现有 spec 一致）。

**Rationale**:
- 技术选型已定：APScheduler 与 FastAPI lifespan 集成，无需 Redis/Celery。
- Tushare 调用频率与积分因账户等级而异；日线已合并为按日一次全市场，`income` 按标的串行/间隔请求，避免超限。

**Alternatives considered**:
- 独立 worker 进程跑定时：增加部署复杂度；当前单进程即可。
- 拉数失败重试：建议在实现时加入有限次重试与日志，具体策略在 tasks 中细化。

---

## 3. 后端选股 API 设计

**Decision**: 提供 REST 接口：分页列表 + 多条件筛选（本期：基础/行情 + 基本面）；筛选参数与 spec FR-002、FR-003 对齐（股票代码、涨跌幅、股价区间、市盈率、市净率、ROE、毛利率等）；响应中带「数据日期」或「更新时间」以便前端展示「今天/昨天」。

**Rationale**:
- 列表与筛选由后端统一查询 MySQL，避免前端一次拉全量。
- 分页参数：page、page_size；筛选参数：可选 keyword/code、price_min/max、pct_min/max、pe_min/max、pb_min/max、roe_min/max、gpm_min/max 等，与 data-model 字段一致。

**Alternatives considered**:
- 前端内存筛选：数据量大时不可行；不采纳。
- GraphQL：当前技术选型为 REST，保持 REST。

---

## 4. 前端表格与筛选

**Decision**: 使用现有技术选型中的表格/分页组件（如 Element Plus / Naive UI 的 Table），支持服务端分页与筛选；筛选区放置本期支持的维度（代码、涨跌幅、股价、市盈率、市净率、ROE、毛利率等），技术面/消息面/人气不展示或置灰并标注「下期」。

**Rationale**:
- 与 spec「筛选框全部可用」「本期仅基础+基本面」一致。
- 服务端分页与筛选减少前端负载，与后端 API 契约一致。

**Alternatives considered**:
- 前端分页：仅适合小数据量；不采纳。

---

## 5. 数据模型与表结构（概要）

**Decision**: 见 Phase 1 的 `data-model.md`。概要：至少需「股票基础表」（代码、名称、交易所等）+「股票日快照表」（按日存储行情+基本面，便于按数据日期查询与展示今天/昨天）；按标的+交易日 upsert 日线，按标的+报告期 upsert 利润表。

**Rationale**:
- 每日 17:00 拉数落库后，选股 API 只读 MySQL，不实时调 Tushare。
- 日维度快照便于「显示更新时间」和后续按日回溯。

**Alternatives considered**:
- 仅存最新一条/标的：不便于「今天/昨天」与审计；不采纳。
