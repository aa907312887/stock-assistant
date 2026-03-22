# 调研结论：数据源重构

**功能**: 005-数据源重构 | **日期**: 2026-03-21

## 1. 数据源切换范围

**决策**：本次股票数据链路统一切换到 **Tushare**，不再保留智兔兼容逻辑。  

**理由**：
- 当前后端正式接入的股票数据接口已主要集中在 [backend/app/services/tushare_client.py](../../backend/app/services/tushare_client.py)。
- 用户已明确说明“数据源从智兔切换到 Tushare，旧数据不想保留”。
- [backend/app/api/stock_basic.py](../../backend/app/api/stock_basic.py) 中仍有对旧 `zhitu` 数据源展示名的兼容映射，本次应逐步移除。

**备选**：
- 保留智兔兼容层：不采用。会增加表结构迁移、监控口径和查询逻辑复杂度，且与“旧数据全部删除”的决策冲突。

## 2. Tushare 接口选型

**决策**：使用以下接口完成本期目标：
- `stock_basic`
- `daily`
- `daily_basic`
- `weekly`
- `monthly`
- `income`
- `trade_cal`

**理由**：
- `stock_basic`：提供股票主数据。
- `daily`：提供历史日线行情。
- `daily_basic`：补齐日级 PE、PE TTM、PB、股息率、市值、换手率等字段。
- `weekly` / `monthly`：直接提供历史周线、月线，避免本地聚合带来的口径偏差。
- `income`：当前已有利润表接入基础，可继续复用到财报历史表。
- `trade_cal`：用于判断 17:00 任务当天是否为交易日，以及计算最近交易日。

**备选**：
- 仅保留 `daily`，在本地聚合出周线和月线：不采用。虽然依赖更少，但会增加本地聚合逻辑和校验成本。
- 将股息率等字段从财报接口推导：不采用。口径与“交易日收盘后决策字段”不一致。

## 3. 日级表建模

**决策**：采用一张新的**历史日线主表**，由 `daily + daily_basic` 按 `(ts_code, trade_date)` 合并写入；表名建议为 `stock_daily_bar`。  

**理由**：
- 用户已明确“日线不需要快照，日线也是历史日线数据，最新的数据只可能是今天的收盘价格”。
- 当前 [docs/数据库设计.md](../../docs/数据库设计.md) 的 `stock_daily_quote` 与 `stock_valuation_daily` 拆分方案，不利于选股查询直接按日级字段筛选。
- 现有 [backend/app/services/screening_service.py](../../backend/app/services/screening_service.py) 通过 `stock_daily_quote + stock_financial_report` 拼装结果，若继续拆表会让筛选与查询复杂度继续增加。

**备选**：
- 继续保留 `stock_daily_quote + stock_valuation_daily` 两表：不采用。与用户刚确认的“日级单表”方向冲突。

## 4. 周线和月线的存储方案

**决策**：周线、月线分别单独建表，建议命名为 `stock_weekly_bar`、`stock_monthly_bar`。  

**理由**：
- 用户已确认周/月行情需要单独入库。
- 后续若需要周 MACD、月 MACD 等技术指标，独立表更利于索引设计、增量同步和技术指标计算。
- 直接使用 Tushare `weekly`、`monthly` 能减少本地聚合误差。

**备选**：
- 查询时从日线实时聚合：不采用。实现简单，但每次查询都要计算周期聚合，不利于后续扩展和性能优化。

## 5. 财报历史策略

**决策**：保留 `stock_financial_report`，初版继续以 `income` 为主写入历史财报数据，后续按需求扩展资产负债表、现金流量表和财务指标。  

**理由**：
- 当前 [backend/app/models/stock_financial_report.py](../../backend/app/models/stock_financial_report.py) 和 [backend/app/services/stock_sync_service.py](../../backend/app/services/stock_sync_service.py) 已具备基础能力。
- 先保留财报历史表，可以避免本轮重构同时引入更多报表分表复杂度。

**备选**：
- 本轮就拆成利润表 / 资产负债表 / 现金流表多张表：暂不采用。当前用户尚未要求如此细的财报域拆分。

## 6. 定时任务策略

**决策**：继续使用 APScheduler，在每个交易日下午 17:00 执行同步；同步前先用 `trade_cal` 判断是否为交易日。  

**理由**：
- 当前 [backend/app/core/scheduler.py](../../backend/app/core/scheduler.py) 已有 APScheduler 17:00 调度基础，可复用框架而不是推倒重来。
- 用户已明确当前只需要基于收盘价决策，不需要实时数据。
- 非交易日直接跳过，可减少无效调用和误报警。

**备选**：
- 每天固定 17:00 不判断交易日：不采用。周末和节假日会产生空任务和误导性监控记录。
- 应用启动后自动执行一次全量同步：不采用。当前任务涉及删旧表和历史回灌，自动执行风险过高。

## 7. 同步任务监控

**决策**：复用数据库中的 `sync_job_run` 表设计，新增 ORM 与查询接口，页面监控以该表为唯一数据源。  

**理由**：
- [backend/scripts/reset_and_init_v2.sql](../../backend/scripts/reset_and_init_v2.sql) 已有 `sync_job_run` 建表 SQL，可直接作为设计起点。
- 当前 [backend/app/core/scheduled_job_logging.py](../../backend/app/core/scheduled_job_logging.py) 只解决日志告警，不足以支撑页面化监控。
- 用户在规格中明确要求“监控信息用页面展示，错误原因需可追溯”。

**备选**：
- 只依赖日志文件：不采用。日志不适合作为页面查询的稳定数据源。

## 8. 受影响的关键模块

**决策**：本轮改造边界以以下文件为主：
- [backend/app/services/stock_sync_service.py](../../backend/app/services/stock_sync_service.py)
- [backend/app/services/screening_service.py](../../backend/app/services/screening_service.py)
- [backend/app/api/stock.py](../../backend/app/api/stock.py)
- [backend/app/api/admin.py](../../backend/app/api/admin.py)
- [backend/app/core/scheduler.py](../../backend/app/core/scheduler.py)
- [backend/app/services/tushare_client.py](../../backend/app/services/tushare_client.py)
- [frontend/src/views/StockScreeningView.vue](../../frontend/src/views/StockScreeningView.vue)
- [frontend/src/api/stock.ts](../../frontend/src/api/stock.ts)

**理由**：
- 这些文件直接控制同步、查询、调度、管理触发与选股页面展示。
- 当前 `stock_valuation_daily` 仅有模型和 SQL 定义，几乎未接入业务，可直接废弃。

**备选**：
- 只改数据库，不改服务层：不采用。会导致代码仍然依赖旧表结构。

## 9. 主要风险

**决策**：本轮实现需要重点控制以下风险：
- `daily` 与 `daily_basic` 某些交易日可能数据不齐，需要容错合并
- 财报历史回灌耗时长，建议和行情回灌分批执行
- 前后端字段升级要同步推进，避免选股页响应结构断裂

**理由**：
- 这是最容易导致“表结构已改，但链路不通”的三类问题。

**备选**：
- 一次性做完所有链路后再联调：不采用。风险集中，回滚成本高。
