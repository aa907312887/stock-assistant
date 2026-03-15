# 我的股票分析助手 (Stock Assistant)

个人量化与股票分析项目，从 0 搭建。支持股票分析、买入/卖出分析、个人账户分析，后续可接入 AI，并配有现代前端界面。

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLAlchemy + MySQL
- **前端**：Vue 3 + TypeScript + Vite + Element Plus + Pinia
- **说明**：详见 [docs/技术选型.md](docs/技术选型.md)

## 项目结构

```
stock-assistant/
├── backend/          # Python 后端（API、认证、DB）
├── frontend/         # Vue 3 前端（登录、首页 Demo）
├── docs/             # 项目文档
└── README.md
```

详见 [docs/项目结构.md](docs/项目结构.md)。

## 快速运行 Demo

**详细步骤与 Demo 效果说明**见 [docs/启动说明.md](docs/启动说明.md)。

### 1. 数据库（由你本地处理）

- 创建 MySQL 数据库 `stock_assistant`，并执行 [docs/数据库设计.md](docs/数据库设计.md) 中的建库与建表语句（至少创建 `user` 表）。
- 在 `user` 表中插入一个用户，例如：
  ```sql
  INSERT INTO user (username, password_hash) VALUES ('demo', NULL);
  ```
  若使用密码登录，可用后端提供的哈希（见下方「首次密码」）。

### 2. 后端

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 填写 DATABASE_URL
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

- 访问：<http://localhost:5173>，使用上面创建的用户名（及密码，若已设置）登录即可进入首页 Demo。

### 可选：统一密码（仅用户名登录）

在 `backend/.env` 中设置 `DEFAULT_PASSWORD=你的统一密码`，则前端可只输入用户名、不输入密码即可登录（需与 DB 中用户配置一致，见 [产品能力](docs/产品能力.md)）。

## 当前状态

- 已完成初始版本：后端认证（登录、JWT、/auth/me）、前端登录页与首页 Demo。
- 数据库由你本地创建与维护；后续按模块迭代：综合选股、持仓助手、定时任务等。
