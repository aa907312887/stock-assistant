# 后端 (FastAPI)

## 环境

- Python 3.12
- 建议使用项目内虚拟环境：`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`

## 配置

- 复制 `.env.example` 为 `.env`，填写 `DATABASE_URL`（MySQL 连接串）。数据库需自行创建并执行 `docs/数据库设计.md` 中的建库建表语句。
- 可选：`DEFAULT_PASSWORD` 设置统一密码后，前端可仅输入用户名登录。
- 首次使用需在 `user` 表中插入用户（无注册入口）。密码可为 bcrypt 哈希或留空（配合 `DEFAULT_PASSWORD` 仅用户名登录）。生成哈希示例：
  ```bash
  .venv/bin/python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('你的密码'))"
  ```

## 启动

```bash
# 在 backend 目录下
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：http://127.0.0.1:8000/docs  
- 健康检查：http://127.0.0.1:8000/health  
