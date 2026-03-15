# 认证 API 契约（用户登录）

**功能**: 001-登录 | **基准**: 仅用户名登录，无密码校验

## POST /api/auth/login

- **请求**
  - Method: `POST`
  - Body (JSON): `{ "username": string }`  
  - 不传 `password`；若现有 schema 要求字段，可保留 `password` 可选并忽略。
- **成功** (200)
  - Body: `{ "access_token": string, "token_type": "bearer", "user": { "id": number, "username": string } }`
- **失败**
  - 用户名为空/格式错误: 400 + 明确字段错误（或由前端校验不提交）。
  - 用户名不存在: 401 + `{ "detail": "无此用户" }`（或统一文案，不暴露技术信息）。
- **说明**: 后端仅校验用户名是否存在于用户表；存在则签发 JWT，不存在则 401。

## GET /api/auth/me

- **请求**: Header `Authorization: Bearer <access_token>`
- **成功** (200): `{ "id": number, "username": string }`
- **失败**: 401（token 缺失/无效/过期）
- **说明**: 用于前端获取当前用户、校验登录态。

## 登出

- 无强制服务端端点；前端丢弃 token 并跳转登录页即完成登出。
- 若需占位，可保留 `POST /api/auth/logout` 返回 200，不要求服务端使 token 失效。
