# Tasks: 综合选股

**Input**: Design documents from `specs/002-综合选股/`  
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md

**Organization**: Tasks are grouped by user story. US1（数据导入）must complete before US2（选股列表）can show data.

**Format**: `- [ ] [TaskID] [P?] [Story?] Description with file path`

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 依赖与配置就绪，满足定时任务与 Tushare 调用

- [x] T001 在 backend/requirements.txt 中加入 APScheduler（apscheduler）与 requests（或 httpx），并说明版本
- [x] T002 在 backend/app/config.py 中增加 Tushare 相关配置（`TUSHARE_TOKEN`），并从环境变量读取；在 backend/.env.example 中增加对应项说明
- [x] T003 确认 docs/数据库设计.md 中 stock_basic、stock_daily_quote、stock_financial 三张表已在库中存在；若尚未建表，在 backend 中提供建表 SQL 或 Alembic 迁移脚本，使三张表可被创建

---

## Phase 2: Foundational（阻塞性前置）

**Purpose**: 后端模型与数据库访问就绪，所有用户故事依赖此阶段

- [x] T004 [P] 在 backend/app/models/ 下新增 StockBasic、StockDailyQuote、StockFinancial 三个 SQLAlchemy 模型，字段与 docs/数据库设计.md 中三张表一致，表名映射正确
- [x] T005 在 backend/app/models/__init__.py 中导出上述三个模型，便于其他地方 import

**Checkpoint**: 模型与表就绪，US1/US2 可开始实现

---

## Phase 3: User Story 1 - 数据导入（按天拉取股票基础、行情、基本面）

**Goal**: 每日 17:00 定时从 Tushare 拉取数据并写入 stock_basic、stock_daily_quote、stock_financial；支持部署时执行一次与手动触发。

**Independent Test**: 调用手动触发接口或执行同步命令后，数据库中三张表有数据；或等待至 17:00 后检查表中是否有当日数据。

### Implementation for US1

- [x] T006 [US1] 在 backend/app/services/ 下实现 Tushare 客户端（`tushare_client.py`），封装 `stock_basic`、`daily`、`income`，读取 config 中的 `TUSHARE_TOKEN`，请求失败时抛异常或返回可区分的错误
- [x] T007 [US1] 在 backend/app/services/ 下实现 stock_sync_service.py：调用 Tushare 客户端获取数据，按 data-model 约定顺序先写 stock_basic（按 code upsert），再写 stock_daily_quote（按 stock_code+trade_date upsert）、stock_financial（按业务约定 upsert）；使用 SQLAlchemy Session，支持限流与单次请求重试 2～3 次、间隔 5～10 秒；打 INFO/WARNING/ERROR 日志（开始/结束、成功失败条数、单只失败、整次失败）
- [x] T008 [US1] 在 backend/app/core/ 下实现 scheduler.py：创建 APScheduler BackgroundScheduler，注册 cron 任务每日 17:00（0 17 * * *，时区 Asia/Shanghai）执行 stock_sync_service 的同步函数；提供 start() 与 shutdown() 供 lifespan 调用
- [x] T009 [US1] 在 backend/app/main.py 的 lifespan 中启动 scheduler（start），应用关闭时调用 shutdown；可选：启动后延迟 30 秒执行一次同步（部署时首次拉数）
- [x] T010 [US1] 在 backend/app/api/ 下新增 admin 或 stock 路由，实现 POST /api/admin/stock-sync（或 POST /api/stock/sync）：鉴权采用环境变量 X-Admin-Secret 或本机 IP 等其一；返回 202 Accepted 与 JSON { "status": "started", "message": "同步任务已触发" }；在后台异步执行同步逻辑，不阻塞请求
- [x] T011 [US1] 可选：在 backend 下提供管理命令或脚本（如 python -m app.scripts.sync_stock 或 scripts/sync-stock.sh），内部调用与 T007 相同的同步函数，便于运维手动执行

**Checkpoint**: US1 完成——定时拉数、手动触发、部署时首次执行均可用，数据写入三张表

---

## Phase 4: User Story 2 - 综合选股分页查询（P1）

**Goal**: 用户登录后在综合选股页看到全市场股票列表，分页、按基础与行情（代码、涨跌幅、股价）及基本面（市盈率、市净率、ROE、毛利率）筛选；展示数据日期（今天/昨天）；左侧菜单含首页、综合选股。

**Independent Test**: 登录后打开综合选股页，列表有数据、分页可切换、筛选条件生效、数据日期展示正确；无数据或接口异常时前端友好提示。

### Implementation for US2

- [x] T012 [US2] 在 backend/app/schemas/ 下新增 stock.py（或 screening.py）：定义选股列表 Query 参数（page、page_size、code、pct_min/max、price_min/max、pe_min/max、pb_min/max、roe_min/max、gpm_min/max、data_date）与列表响应 Schema（items、total、page、page_size、data_date），与 contracts/api-stock-screening.md 一致
- [x] T013 [US2] 在 backend/app/services/ 下实现 screening_service.py：根据 query 从 stock_basic、stock_daily_quote、stock_financial 三表 JOIN 查询，取最新交易日（或 data_date）的行情，按条件筛选，分页（page_size 上限 100，默认 20）；返回 (items, total, data_date)
- [x] T014 [US2] 在 backend/app/api/ 下实现 GET /api/stock/screening（需登录，使用现有 deps 获取当前用户）：调用 screening_service，返回 JSON 符合契约；空结果时 total=0、items=[]；500 时返回统一 detail，不打栈到前端
- [x] T015 [US2] 在 backend/app/api/ 下实现 GET /api/stock/screening/latest-date（需登录）：查询 stock_daily_quote 中最大 trade_date，返回 { "date": "YYYY-MM-DD" }
- [x] T016 [US2] 在 backend/app/main.py 中挂载选股相关路由（/api/stock 或 /api/stock/screening），确保鉴权与 001 登录一致
- [x] T017 [P] [US2] 在前端路由中增加综合选股页（如 path /stock-screening），对应视图组件（如 views/StockScreening.vue 或同名）
- [x] T018 [US2] 在前端实现综合选股页：表格展示列表（code、name、trade_date、open、close、pct_change、pe、pb、roe、gross_margin 等），服务端分页（page、page_size），筛选区（代码、涨跌幅、股价、市盈率、市净率、ROE、毛利率），调用 GET /api/stock/screening 与 GET /api/stock/screening/latest-date；展示数据日期（今天/昨天）；空结果时提示「暂无符合条件的数据」，接口异常时提示「数据暂时不可用，请稍后重试」
- [x] T019 [US2] 在前端左侧菜单中增加两个一级菜单：首页、综合选股；当前为综合选股页时菜单高亮正确，无 bug（FR-005）

**Checkpoint**: US2 完成——选股列表、分页、筛选、数据日期、左侧菜单均符合 spec 与契约

---

## Phase 5: Polish & Cross-Cutting

**Purpose**: 错误提示统一、日志完善、文档与验证

- [x] T020 统一后端选股与同步相关接口的错误响应格式，确保 500 不向前端暴露堆栈；关键操作（同步开始/结束、筛选查询失败）打日志到 app.log
- [x] T021 在 specs/002-综合选股/quickstart.md 或项目 README 中补充：首次部署后需调用一次 POST /api/admin/stock-sync 或执行同步脚本，以便有数据可查
- [x] T022 按 quickstart.md 执行一遍后端与前端启动、选股页访问、分页与筛选验证，确认与 spec 验收场景一致

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，可立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成，阻塞 US1、US2
- **Phase 3 (US1)**: 依赖 Phase 2；US2 依赖 US1 有数据（否则列表为空仍可开发）
- **Phase 4 (US2)**: 依赖 Phase 2；可与 Phase 3 顺序执行（先做后端接口再做前端，或并行）
- **Phase 5 (Polish)**: 依赖 Phase 3、4 完成

### User Story Dependencies

- **US1（数据导入）**: 无其他故事依赖，先完成则 US2 列表有数据
- **US2（综合选股分页）**: 不依赖 US1 代码，但依赖三张表已有数据才能看到非空列表；接口与前端可先实现

### Parallel Opportunities

- T004 可与同 Phase 内其他任务并行（不同文件）
- T012、T017 可与同 Phase 内无依赖任务并行
- T017 前端路由与 T012 后端 schema 可并行

---

## Implementation Strategy

### MVP First（建议先完成 US1 + US2 核心）

1. 完成 Phase 1、2
2. 完成 Phase 3（US1）：同步与定时、手动触发
3. 完成 Phase 4（US2）：选股 API + 前端列表与筛选、菜单
4. 执行 Phase 5 中 T022 验收

### Incremental Delivery

- Phase 1+2 完成后即可开发 US1、US2
- US1 完成 → 可验证数据是否入表
- US2 完成 → 可验证端到端选股与筛选
- Phase 5 收尾 → 文档与错误提示统一

---

## Notes

- 所有任务均带明确文件路径，便于直接实现
- [P] 表示可与同阶段无依赖任务并行
- [US1]/[US2] 表示归属用户故事，便于追溯
- Spec 未要求 TDD，故未单独列出测试任务；若需可后续在 Phase 2 后为 US1/US2 增加接口或集成测试
