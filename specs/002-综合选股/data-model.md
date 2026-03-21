# 数据模型：综合选股

**功能**: 002-综合选股 | **日期**: 2025-03-15

**表结构以项目文档为准**：本功能使用的数据库表定义见 [docs/数据库设计.md](../../docs/数据库设计.md)，此处仅做对齐说明与写入方式约定。

---

## 1. 本功能涉及的表（与 数据库设计.md 一致）

| 表名 | 说明 | 本期用途 |
|------|------|----------|
| **stock_basic** | 股票基础（相对静态） | 列表展示代码、名称、市场；筛选按代码、市场等 |
| **stock_daily_quote** | 股票日行情 | 列表展示与筛选：开盘/收盘/涨跌幅、成交量/额、换手率、市值等；按 trade_date 区分「今天/昨天」 |
| **stock_financial** | 股票业绩/估值 | 列表展示与筛选：市盈率（pe/pe_ttm/pe_dynamic 等）、市净率、ROE、毛利率等 |

- **stock_basic**：主键 `id`，唯一 `code`。字段含 code、name、market、industry_code、industry_name、region、list_date、created_at、updated_at。
- **stock_daily_quote**：唯一 `(stock_code, trade_date)`。字段含 stock_code、trade_date、open、close、high、low、pct_change、volume、amount、turnover_rate、total_market_cap、float_market_cap 等（见数据库设计文档）。
- **stock_financial**：按业务可「仅最新一份」或「按报告期」；字段含 stock_code、report_date、pe、pe_ttm、pe_static、pe_dynamic、pb、roe、gross_margin、net_margin 等（见数据库设计文档）。

选股列表与筛选：**后端从上述三张表取数**，按 `trade_date` 取最新一个交易日（或指定 data_date）的行情，再 JOIN stock_basic、按需 JOIN stock_financial（取该股票最新一条或 report_date 最大一条），做分页与条件筛选。

---

## 2. 数据写入方式（插入/更新到表中）

**结论**：数据**通过后端 Python 代码 + SQLAlchemy** 写入 MySQL，在**定时任务**或**手动触发同步**时执行；不依赖外部 ETL 或脚本直接写库。

### 2.1 写入时机

- **定时任务**：每日 17:00 触发的同步任务（见 plan.md「定时任务与部署设计」）。
- **手动触发**：调用 `POST /api/admin/stock-sync` 或执行管理命令/脚本（同上）。
- **部署时首次**：部署后执行一次同步（同上）。

### 2.2 写入流程（逻辑顺序）

1. **拉取 Tushare 数据**：在 backend 的 service 层（`app/services/stock_sync_service.py` + `tushare_client.py`）调用 Tushare Pro，获取：
   - 股票列表 → 对应 **stock_basic**
   - 日行情（按日、按标的）→ 对应 **stock_daily_quote**
   - 利润表（按标的 `income`）→ 对应 **stock_financial**
2. **解析与映射**：将接口返回的 JSON/字段 映射为与表结构一致的 Python 字典或 ORM 模型实例（字段名与 docs/数据库设计.md 一致）。
3. **写入数据库**：使用 SQLAlchemy **Session**，对每张表采用「存在则更新、不存在则插入」：
   - **stock_basic**：按 `code` 唯一，使用 `merge()` 或先 `query.filter_by(code=...).first()` 再 `session.add()`/更新属性，或 MySQL 的 `INSERT ... ON DUPLICATE KEY UPDATE`（通过 SQLAlchemy 的 `insert().on_duplicate_key_update()` 或原生 SQL）。
   - **stock_daily_quote**：按 `(stock_code, trade_date)` 唯一，同样 upsert（merge 或 ON DUPLICATE KEY UPDATE）。
   - **stock_financial**：按业务约定「仅最新一份」则按 `stock_code` upsert；若按报告期则按 `(stock_code, report_date)` upsert。
4. **提交**：每批或全量完成后 `session.commit()`；异常时 `session.rollback()` 并打日志。

### 2.3 实现方式建议

- **ORM 方式**：定义 SQLAlchemy Model（如 `StockBasic`、`StockDailyQuote`、`StockFinancial`），与 docs/数据库设计.md 表结构一致；同步时构造模型实例或字典，使用 `session.merge(model)` 或 `session.add(model)`（先查再决定 add 或更新）。
- **批量 upsert**：若单条 merge 性能不足，可对一批数据使用 MySQL `INSERT ... ON DUPLICATE KEY UPDATE`（通过 SQLAlchemy 的 `execute(insert(...).on_duplicate_key_update(...))` 或 `bulk_insert_mappings` + 自定义 UPDATE 逻辑）。
- **事务与限流**：建议单次同步在一个事务或分批提交（如每 500 条 commit 一次），避免长事务；调用 Tushare 时遵守账户积分与频率限制，日线可一次按交易日拉全市场，`income` 按标的节流。

### 2.4 小结

| 表 | 写入方式 | 唯一键 | 说明 |
|----|----------|--------|------|
| stock_basic | Python + SQLAlchemy upsert | code | Tushare `stock_basic` → 解析 → upsert |
| stock_daily_quote | Python + SQLAlchemy upsert | (stock_code, trade_date) | Tushare `daily`（按交易日全市场）→ 解析 → upsert |
| stock_financial | Python + SQLAlchemy upsert | (stock_code, report_date) 或按业务仅最新 | Tushare `income` → 解析 → upsert |

不在表结构文档之外的脚本或 ETL 中直接写库；所有写入统一由后端应用内的「同步服务」完成，便于鉴权、日志与错误处理一致。

---

## 3. 与现有模型的关系

- **user**（已存在）：选股列表与筛选接口需登录态（与 001 登录一致）；本期不持久化「用户级选股结果」，仅读上述三张表。
- **user_position / user_trade**：持仓功能用；综合选股不写这两张表。

---

## 4. 状态与一致性

- 无复杂状态机；数据为「当日/最新快照」只读使用。
- 同步任务：先更新 stock_basic（保证代码存在），再写入 stock_daily_quote、stock_financial；失败与重试见 plan.md「定时任务与部署设计」。
