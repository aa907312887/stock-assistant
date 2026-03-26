# Tasks: 大盘温度

**Input**: 设计文档来自 `/specs/008-大盘温度/`  
**Prerequisites**: `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`、`formula.md`

**Tests**: 本次规格未强制 TDD，任务清单不单列“先写失败测试”阶段；在各故事收尾加入最小必要验证任务。  
**Organization**: 任务按用户故事分组，确保每个故事可独立实现、独立验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无前置冲突）
- **[Story]**: 对应用户故事（US1/US2/US3）
- 每条任务都包含精确文件路径

---

## Phase 1: Setup（共享初始化）

**Purpose**: 建立大盘温度功能所需的基础文件骨架与配置入口

- [X] T001 在 `backend/app/services/market_temperature` 新建模块目录并添加 `__init__.py`
- [X] T002 [P] 在 `backend/app/scripts/` 新建 `fill_market_temperature.py` 历史初始化脚本
- [X] T003 [P] 在 `backend/scripts/` 新建 `add_market_temperature_tables.sql` 数据库迁移脚本
- [X] T004 [P] 在 `frontend/src/api/` 新建 `marketTemperature.ts` 接口封装文件
- [X] T005 [P] 在 `frontend/src/components/` 新建 `MarketTemperatureCard.vue` 组件文件

---

## Phase 2: Foundational（阻塞前置）

**Purpose**: 完成所有用户故事共享的后端计算基础、数据模型与调度基础能力

**⚠️ CRITICAL**: 本阶段完成前，不进入任何用户故事开发

- [X] T006 在 `backend/scripts/add_market_temperature_tables.sql` 创建 `market_index_daily_quote`、`market_temperature_daily`、`market_temperature_factor_daily`、`market_temperature_level_rule`、`market_temperature_copywriting`
- [X] T007 [P] 在 `backend/app/services/market_temperature/index_quote_service.py` 实现四指数日线拉取与入库（含 upsert）
- [X] T008 [P] 在 `backend/app/services/market_temperature/formula_engine.py` 实现 `formula.md` 的三因子与总分计算逻辑（v1.0.0）
- [X] T009 在 `backend/app/services/market_temperature/temperature_repository.py` 实现温度结果与分项结果读写（按 `trade_date + formula_version`）
- [X] T010 在 `backend/app/services/market_temperature/temperature_job_service.py` 实现增量重算（回看80交易日）与失败重试流程
- [X] T011 在 `backend/app/core/scheduler.py` 注册大盘温度定时任务（17:10）与启动补数任务（延迟30秒）
- [X] T012 在 `backend/app/scripts/fill_market_temperature.py` 对接初始化脚本参数（`--years --warmup-years --version`）
- [X] T013 在 `backend/app/services/market_temperature/rule_service.py` 初始化5档分级与策略提示默认规则

**Checkpoint**: 数据链路、计算引擎、调度能力就绪，可进入用户故事实现

---

## Phase 3: User Story 1 - 首页展示当日温度（Priority: P1） 🎯 MVP

**Goal**: 用户进入首页即可在“我的投资逻辑”右侧看到当日温度、5档状态、更新时间  
**Independent Test**: 执行一次日更任务后，首页模块展示当日温度分值、档位和更新时间，且与数据库一致

### Implementation for User Story 1

- [X] T014 [US1] 在 `backend/app/api/` 新增 `market_temperature.py` 并实现 `GET /api/market-temperature/latest`
- [X] T015 [US1] 在 `backend/app/api/` 路由聚合文件中注册 `market_temperature` 路由
- [X] T016 [US1] 在 `frontend/src/api/marketTemperature.ts` 实现 `getLatestMarketTemperature()` 调用
- [X] T017 [US1] 在 `frontend/src/components/MarketTemperatureCard.vue` 实现当日温度、5档样式、更新时间展示
- [X] T018 [US1] 在 `frontend/src/views/` 首页对应文件中将 `MarketTemperatureCard` 放置到“我的投资逻辑”右侧区域
- [X] T019 [US1] 在 `frontend/src/components/MarketTemperatureCard.vue` 添加异常状态展示（`stale/failed`）
- [X] T020 [US1] 在 `specs/008-大盘温度/quickstart.md` 补充 US1 验收步骤与预期结果截图说明占位

**Checkpoint**: US1 可独立演示并满足首屏可见性要求

---

## Phase 4: User Story 2 - 趋势与仓位建议（Priority: P2）

**Goal**: 用户可查看最近20交易日趋势，并看到升温/降温与仓位建议  
**Independent Test**: 接口返回最近20日序列后，前端趋势区正确展示曲线与“升温/降温/持平”标记

### Implementation for User Story 2

- [X] T021 [US2] 在 `backend/app/api/market_temperature.py` 实现 `GET /api/market-temperature/trend?days=20`
- [X] T022 [US2] 在 `backend/app/services/market_temperature/temperature_job_service.py` 输出 `trend_flag` 与 `delta_score`
- [X] T023 [US2] 在 `backend/app/services/market_temperature/rule_service.py` 实现温度档位到仓位建议区间映射
- [X] T024 [US2] 在 `frontend/src/api/marketTemperature.ts` 实现 `getMarketTemperatureTrend(days)`
- [X] T025 [US2] 在 `frontend/src/components/MarketTemperatureCard.vue` 增加最近20交易日趋势区展示
- [X] T026 [US2] 在 `frontend/src/components/MarketTemperatureCard.vue` 增加档位对应仓位建议区间文案
- [X] T027 [US2] 在 `specs/008-大盘温度/quickstart.md` 补充 US2 的趋势与仓位建议验收步骤

**Checkpoint**: US2 单独可验收，用户可理解趋势与动作建议

---

## Phase 5: User Story 3 - 悬浮提示与口径说明（Priority: P3）

**Goal**: 用户通过悬浮提示理解当前策略，通过“?”按钮查看完整计算逻辑  
**Independent Test**: 悬浮任一档位可见策略提示；点击“?”可弹出版本化口径说明，移动端可轻触展开

### Implementation for User Story 3

- [X] T028 [US3] 在 `backend/app/api/market_temperature.py` 实现 `GET /api/market-temperature/explain`
- [X] T029 [US3] 在 `backend/app/services/market_temperature/rule_service.py` 提供口径说明读取（按 `formula_version`）
- [X] T030 [US3] 在 `frontend/src/api/marketTemperature.ts` 实现 `getMarketTemperatureExplain(version?)`
- [X] T031 [US3] 在 `frontend/src/components/MarketTemperatureCard.vue` 实现温度档位悬浮策略提示层
- [X] T032 [US3] 在 `frontend/src/components/` 新建 `MarketTemperatureExplainModal.vue` 并实现“?”按钮弹层
- [X] T033 [US3] 在 `frontend/src/components/MarketTemperatureCard.vue` 增加移动端轻触展开交互降级
- [X] T034 [US3] 在 `specs/008-大盘温度/quickstart.md` 补充 US3 交互验收步骤

**Checkpoint**: US3 完成后，用户可理解“怎么用”与“怎么算”

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 收尾优化、回归验证、文档一致性修正

- [X] T035 [P] 在 `specs/008-大盘温度/data-model.md` 统一表名为 `market_index_daily_quote`（替换 `market_index_daily_snapshot`）
- [X] T036 [P] 在 `specs/008-大盘温度/contracts/market-temperature.openapi.yaml` 校对字段与最新实现一致（含错误码约定）
- [X] T037 在 `backend/app/services/market_temperature/` 增加关键日志与失败告警埋点（任务开始/结束/耗时/失败原因）
- [X] T038 在 `specs/008-大盘温度/quickstart.md` 执行全链路验证清单并记录结果
- [X] T039 在 `specs/008-大盘温度/plan.md` 与 `specs/008-大盘温度/spec.md` 回填最终实现偏差（如有）

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1（Setup）可立即开始
- Phase 2（Foundational）依赖 Phase 1，且阻塞全部用户故事
- Phase 3（US1）、Phase 4（US2）、Phase 5（US3）均依赖 Phase 2 完成
- Phase 6（Polish）依赖已完成的用户故事

### User Story Dependencies

- **US1 (P1)**: 无故事依赖，MVP 首发
- **US2 (P2)**: 依赖 US1 的首页模块承载，但接口与计算可独立开发
- **US3 (P3)**: 依赖 US1 的卡片组件与 US2 的档位/建议数据

### Parallel Opportunities

- Setup 中 `T002/T003/T004/T005` 可并行
- Foundational 中 `T007/T008` 可并行，`T009` 在两者后进行
- 各故事内前后端任务可并行：如 US1 的 `T014` 与 `T017`，US3 的 `T028` 与 `T032`

---

## Parallel Example: User Story 1

```bash
# 并行开发后端与前端（US1）
Task: "T014 [US1] 实现 GET /api/market-temperature/latest in backend/app/api/market_temperature.py"
Task: "T017 [US1] 实现首页温度卡片展示 in frontend/src/components/MarketTemperatureCard.vue"
```

---

## Implementation Strategy

### MVP First（仅 US1）

1. 完成 Phase 1~2（基础能力）
2. 完成 Phase 3（US1）
3. 按 quickstart 验证首页首屏可见、温度正确、更新时间正确
4. 先交付可用 MVP

### Incremental Delivery

1. US1：先让用户“看见并理解当日温度”
2. US2：补足趋势与仓位建议，增强决策价值
3. US3：补足悬浮提示与口径说明，提升可解释性与信任度

### Parallel Team Strategy

1. 一人负责后端数据链路（T006~T013）
2. 一人负责首页组件与交互（T016~T019、T025~T033）
3. 一人负责文档与契约一致性（T020、T027、T034、T035~T039）

---

## Notes

- 所有任务均为可执行粒度，包含明确文件路径
- `[P]` 仅用于无直接文件冲突任务
- 每个用户故事均定义了独立验收标准
- 建议每完成一个故事即做一次小范围演示与回归
