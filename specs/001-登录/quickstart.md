# 快速启动：用户登录

**功能**: 001-登录

## 前置条件

- MySQL 已启动，已执行 `scripts/init.sql` 建库建表，并已插入用户（如 `scripts/insert_users.sql` 或手动 INSERT）。
- 后端 `backend/.env` 已配置 `DATABASE_URL`（见 `backend/.env.example`）。

## 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档: http://localhost:8000/docs  
- 登录接口: POST http://localhost:8000/api/auth/login  
  - Body: `{"username": "已存在的用户名"}`  
  - 成功返回 `access_token` 与 `user`。

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

- 前端: http://localhost:5173  
- 登录页输入用户名（不需密码），提交后应跳转首页；若用户不存在则提示「无此用户」。

## 验收要点

1. 输入已存在用户名 → 登录成功 → 进入首页。
2. 输入不存在的用户名 → 提示「无此用户」，不报 500。
3. 空用户名 → 前端提示必填或后端 400。
4. 登出后再次访问受保护页 → 重定向登录页。
