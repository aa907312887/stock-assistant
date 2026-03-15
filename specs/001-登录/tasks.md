# Tasks: 用户登录

**Input**: Design documents from `specs/001-登录/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/auth-api.md

**Tests**: Spec 未要求 TDD/自动化测试，本任务列表不包含测试任务；以 quickstart 手工验收为主。

**Organization**: 按用户需求分阶段，每则需求可独立实现与验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无依赖）
- **[Story]**: 所属用户需求（US1, US2, US3）
- 描述中含具体文件路径

## Path Conventions

- **Backend**: `backend/app/`（api, core, models, schemas）
- **Frontend**: `frontend/src/`（api, views, router, stores）

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 确认项目结构与环境满足开发与运行

- [x] T001 Verify backend structure and dependencies per plan in backend/app/main.py and backend/requirements.txt
- [x] T002 [P] Verify frontend structure and dependencies per plan in frontend/package.json and frontend/vite.config.ts
- [x] T003 Ensure backend/.env exists with DATABASE_URL (copy from backend/.env.example if missing)

---

## Phase 2: Foundational（前置条件）

**Purpose**: 所有用户需求依赖的基础能力，未完成前不得开始需求开发

- [x] T004 Ensure database and User model usable: backend/app/database.py and backend/app/models/user.py
- [x] T005 [P] Ensure JWT creation available in backend/app/core/security.py and backend/app/config.py (SECRET_KEY, create_access_token)
- [x] T006 Ensure auth router mounted and get_db in backend/app/main.py and backend/app/api/auth.py
- [x] T007 [P] Ensure frontend HTTP client and API base URL in frontend/src/api/http.ts

**Checkpoint**: 后端可启动、前端可访问代理 API；可开始按用户需求实现

---

## Phase 3: 用户需求 1 - 使用用户名登录（优先级：P1） MVP

**Goal**: 用户仅输入用户名即可登录，成功则进入首页欢迎并展示产品能力；用户名不存在则停留在登录页并看到「无此用户」提示。

**Independent Test**: 在登录页输入已存在用户名并提交 → 进入首页；输入不存在用户名 → 停留在登录页并显示「无此用户」。

### Implementation for 用户需求 1

- [x] T008 [US1] Change login to username-only in backend/app/api/auth.py: remove password verification, on user not found return 401 with detail "无此用户"
- [x] T009 [P] [US1] Keep UserLogin schema with optional password in backend/app/schemas/auth.py (password optional, backend ignores it)
- [x] T010 [US1] Update login form to single username field in frontend/src/views/LoginView.vue
- [x] T011 [US1] Update login API call to send only username in frontend/src/api/auth.ts
- [x] T012 [US1] On login success store token and redirect to home in frontend/src/views/LoginView.vue and frontend/src/stores/user.ts
- [x] T013 [US1] Ensure home page shows welcome and product capabilities in frontend/src/views/HomeView.vue

**Checkpoint**: 仅用户名登录、成功进首页、失败见「无此用户」可独立验收

---

## Phase 4: 用户需求 2 - 登录失败时的明确提示（优先级：P2）

**Goal**: 空用户名与不存在用户名均有明确、统一提示；不暴露技术堆栈或 500 信息。

**Independent Test**: 提交空用户名 → 前端提示「请输入用户名」或后端 400；提交不存在用户名 → 前端展示「无此用户」；网络/服务异常 → 通用提示「网络异常，请稍后重试」。

### Implementation for 用户需求 2

- [x] T014 [US2] Validate username non-empty in backend/app/api/auth.py and return 400 with clear message when empty (or rely on frontend only)
- [x] T015 [US2] Frontend: validate empty username before submit and show "请输入用户名" in frontend/src/views/LoginView.vue
- [x] T016 [US2] Frontend: on 401 from login API display "无此用户" in frontend/src/views/LoginView.vue
- [x] T017 [US2] Frontend: on network or 5xx error show generic "网络异常，请稍后重试" in frontend/src/views/LoginView.vue or frontend/src/api/auth.ts

**Checkpoint**: 空用户名与无此用户、异常场景均有明确提示，可独立验收

---

## Phase 5: 用户需求 3 - 登录成功后进入首页与登出（优先级：P3）

**Goal**: 已登录可访问受保护页；登出后会话失效并跳转登录页；未登录访问受保护页则重定向登录。

**Independent Test**: 登录后打开首页 → 正常展示；点击登出 → 回到登录页；未登录访问首页 → 重定向登录页。

### Implementation for 用户需求 3

- [x] T018 [US3] Implement logout: clear token and redirect to login in frontend/src/stores/user.ts
- [x] T019 [US3] Add logout entry (e.g. button or link) on home or layout in frontend/src/views/HomeView.vue (or layout component)
- [x] T020 [US3] Protect routes: redirect to login when not authenticated in frontend/src/router/index.ts
- [x] T021 [US3] When already logged in and visiting login page redirect to home (or show "已登录，进入首页") in frontend/src/router/index.ts

**Checkpoint**: 登出与路由保护、已登录访问登录页行为可独立验收

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 多故事共用收尾与验收

- [x] T022 [P] Update quickstart if needed in specs/001-登录/quickstart.md
- [x] T023 Run quickstart validation per specs/001-登录/quickstart.md (backend + frontend start, login flow, 无此用户, logout)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，可立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成，阻塞所有用户需求
- **Phase 3–5 (User Stories)**: 均依赖 Phase 2；US1 → US2 → US3 按优先级顺序实现，或 US2/US3 在 US1 完成后并行
- **Phase 6 (Polish)**: 依赖 Phase 3–5 中需验收的故事完成

### 用户需求依赖

- **US1 (P1)**: 仅依赖 Phase 2；无其他需求依赖
- **US2 (P2)**: 依赖 Phase 2；与 US1 共用登录页与接口，建议在 US1 完成后实现
- **US3 (P3)**: 依赖 Phase 2；依赖 US1 的登录态与首页，建议在 US1 完成后实现

### Parallel Opportunities

- Phase 1: T002 与 T003 可与 T001 并行（不同文件/配置）
- Phase 2: T005 与 T007 可并行
- Phase 3: T009 可与 T008 并行；T010、T011 可与后端任务并行（不同端）
- Phase 6: T022 可与代码收尾并行

---

## Parallel Example: 用户需求 1

```text
# 后端与前端可并行
Backend: T008 backend/app/api/auth.py, T009 backend/app/schemas/auth.py
Frontend: T010 frontend/src/views/LoginView.vue, T011 frontend/src/api/auth.ts
然后: T012 前端存 token 与跳转, T013 首页内容
```

---

## Implementation Strategy

### MVP First（仅 用户需求 1）

1. 完成 Phase 1 + Phase 2
2. 完成 Phase 3（US1）
3. 按 quickstart 验收：仅用户名登录 → 首页；无此用户 → 提示
4. 可在此停止并演示

### Incremental Delivery

1. Phase 1 + 2 → 基础就绪
2. Phase 3 (US1) → 验收 → MVP 可演示
3. Phase 4 (US2) → 错误提示完善 → 验收
4. Phase 5 (US3) → 登出与路由保护 → 验收
5. Phase 6 → 文档与整体验收

---

## Notes

- [P] 表示可并行（不同文件、无未完成依赖）
- [USn] 表示归属用户需求，便于追溯
- 每则用户需求应可独立完成并验收
- 建议每完成一阶段或一故事即提交并验收
- 避免：模糊任务、同文件冲突、破坏故事独立性的跨故事依赖
