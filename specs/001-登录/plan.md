# Implementation Plan: 用户登录

**Branch**: `001-用户登录` | **Date**: 2025-03-15 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/001-登录/spec.md`

## Summary

- **需求要点**: 仅用户名登录（无密码）；用户预置在 MySQL；登录成功进入首页并展示产品能力；登出后需重新登录；错误提示统一为「无此用户」等，不暴露技术细节。
- **技术路线**: 沿用现有 FastAPI + Vue 3 + MySQL；后端登录接口改为「仅校验用户名存在即发 JWT」；前端登录页仅提交 username，并统一处理 401/「无此用户」；会话采用 JWT，登出由前端丢弃 token。

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript (frontend)  
**Primary Dependencies**: FastAPI, Vue 3, Vite, SQLAlchemy, MySQL, Pinia, Element Plus  
**Storage**: MySQL（用户表已存在；本功能不新增表）  
**Testing**: pytest（后端）, 前端可选 Vitest/E2E；本功能以接口与手工/E2E 验收为主  
**Target Platform**: 本地部署、浏览器 + 后端服务  
**Project Type**: Web 应用（frontend + backend）  
**Performance Goals**: 登录流程 30 秒内完成（spec SC-001）；快速登出与切换用户  
**Constraints**: 无密码、无注册；单机个人使用  
**Scale/Scope**: 单用户/少量预置用户

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- 项目 Constitution（`.specify/memory/constitution.md`）当前为占位模板，未定制具体原则与门禁。
- **结论**: 未启用强制门禁；本计划与现有技术选型、spec 一致，可直接进入 Phase 0/1。

## Project Structure

### Documentation (this feature)

```text
specs/001-登录/
├── plan.md              # 本文件
├── spec.md              # 功能规格
├── research.md          # Phase 0 研究结论
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 快速启动
├── contracts/           # Phase 1 接口契约
│   └── auth-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 由 /speckit.tasks 生成
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── auth.py      # 登录/me；需改为仅用户名校验、无密码
│   │   └── deps.py      # get_current_user 等
│   ├── core/
│   │   └── security.py  # create_access_token
│   ├── models/
│   │   └── user.py      # User 模型
│   ├── schemas/
│   │   └── auth.py      # UserLogin(username), Token, UserOut
│   ├── config.py
│   ├── database.py
│   └── main.py
└── requirements.txt

frontend/
├── src/
│   ├── api/
│   │   ├── auth.ts      # login(username), me(); 登录仅传 username
│   │   └── http.ts      # 请求头携带 token
│   ├── views/
│   │   ├── LoginView.vue  # 仅用户名输入框；错误展示「无此用户」
│   │   └── HomeView.vue   # 首页欢迎 + 产品能力
│   ├── router/
│   ├── stores/
│   │   └── user.ts      # 登录态、登出
│   └── main.ts
├── package.json
└── vite.config.ts
```

**Structure Decision**: 采用现有 backend + frontend 结构；登录功能仅修改认证相关 API 与登录页/路由/状态，不新增顶层目录。

## Complexity Tracking

无需填写；无 Constitution 违规或额外复杂度引入。
