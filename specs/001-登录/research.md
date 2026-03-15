# 研究结论：用户登录（仅用户名）

**功能**: 001-登录 | **日期**: 2025-03-15

## 认证方式

- **Decision**: 仅用户名登录，不校验密码；本项目为个人使用，用户于 MySQL 预置，用户名即唯一标识。
- **Rationale**: Spec 与澄清已明确「不需要密码」；降低实现与使用成本，与本地部署、单用户场景一致。
- **Alternatives considered**: 用户名+统一密码（已拒绝，spec 要求仅用户名）；OAuth/SSO（超出范围）。

## 会话保持

- **Decision**: JWT（access token），前端存于内存或 localStorage，请求头 `Authorization: Bearer <token>` 携带。
- **Rationale**: 技术选型已定「Session/JWT 二选一」；JWT 无状态、易与 FastAPI 集成，便于快速登出与切换用户。
- **Alternatives considered**: 服务端 Session + Cookie（需存 session store，当前无 Redis；若日后需服务端撤销可再引入）。

## 技术栈（与项目一致）

- **Backend**: Python 3.12、FastAPI、SQLAlchemy、MySQL；认证依赖现有 `app.core.security`（create_access_token）、`app.models.User`。
- **Frontend**: Vue 3、TypeScript、Vite、Pinia、Element Plus；登录页已有，需调整为仅提交 username、不再提交 password，并处理「无此用户」等错误文案。
- **Testing**: pytest（后端）、Vitest/Playwright（前端可按需）；本功能以接口与 E2E 验证为主。

## 错误与安全

- **Decision**: 用户名不存在时统一返回「无此用户」（或 401 + detail），不区分「用户不存在」与「密码错误」；不暴露技术堆栈。
- **Rationale**: Spec FR-002、边界情况与澄清一致；个人部署无需防暴力枚举策略，若有需要可在后续迭代加限流。
