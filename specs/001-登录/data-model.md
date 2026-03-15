# 数据模型：用户登录

**功能**: 001-登录 | **日期**: 2025-03-15

## 实体

### 用户（User）

与现有 `backend/app/models/user.py` 对齐，本功能仅使用「按用户名存在则登录」。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键，唯一 |
| username | str, unique | 用户名，唯一标识；登录时仅校验此字段存在即可 |
| password_hash | str, nullable | 可选；本规格下登录不校验密码，可为空或保留字段以备日后扩展 |

- **Identity**: 用户名唯一；登录请求仅带 username，后端查询 `User.username == ?`，存在则发 token。
- **Lifecycle**: 预置在 MySQL，无注册/删除流程；本功能不修改用户表结构（若当前无 password_hash 可保留 nullable）。

### 会话 / 凭证（Session / Token）

无持久化表；以 JWT 形式存在客户端与请求头中。

| 概念 | 说明 |
|------|------|
| access_token | JWT，payload 含 sub=user_id、exp；由后端 create_access_token 生成 |
| 存储 | 前端存于内存或 localStorage；请求时置于 Header `Authorization: Bearer <token>` |
| 失效 | 登出即前端丢弃 token；服务端不维护黑名单（可选：若需「立即失效」再引入短 TTL 或黑名单） |

## 状态与校验规则

- **登录成功**: 用户名在 User 表中存在 → 返回 Token + UserOut。
- **登录失败**: 用户名为空 → 400/前端校验；用户名不存在 → 401 + 「无此用户」。
- **登出**: 前端清除 token 并跳转登录页；后端无登出端点亦可（或保留 POST /auth/logout 仅作占位）。
