# 快速开始：股票基本信息（003）

**功能**: 003-股票基本信息 | **日期**: 2026-03-21

## 1. 前置条件

- MySQL 已初始化，`stock_basic` 表已存在（与 `docs/数据库设计.md` 一致）。
- `backend/.env` 已配置 `DATABASE_URL`、`TUSHARE_TOKEN`（见 `docs/Tushare股票接口接入文档.md`）。
- 可选：配置 `STOCK_BASIC_WEEKLY_*` 等周任务环境变量（见 `plan.md`）。

## 2. 本地启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3. 验证接口（无鉴权）

```bash
# 分页列表
curl -s "http://127.0.0.1:8000/api/stock/basic?page=1&page_size=5"

# 手动触发基础信息同步（202）
curl -s -X POST "http://127.0.0.1:8000/api/stock/basic/sync"
```

## 4. CLI（实现后）

```bash
cd backend
python -m app.scripts.sync_stock_basic
```

## 5. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问（在实现路由后）：`/stock-basic`（需登录进入 Layout 时，先登录再点侧栏「股票基本信息」）。

## 6. 定时任务

- 应用启动后，在日志中应看到 `stock_basic_weekly`（或等价 id）已注册，默认每周一 03:00（上海时区）执行（具体以 `plan.md` 与环境变量为准）。

## 7. 安全提示

- 无鉴权接口**仅建议在可信网络**部署；公网需由网关/防火墙限制来源 IP 或 VPN。
