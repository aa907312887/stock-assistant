# Quickstart: 综合选股

**Feature**: 002-综合选股 | **Date**: 2025-03-15

## 前提

- 已安装 Python 3.12、Node 18+、MySQL；项目 `backend`、`frontend` 依赖已安装。
- Tushare Token 已配置（如 `backend/.env` 中 `TUSHARE_TOKEN=...`）。
- 已执行数据库迁移（若有）或建表（Stock、StockDaily）。

## 1. 后端

```bash
cd backend
# 若未安装依赖
pip install -r requirements.txt
# 配置 .env：DATABASE_URL、TUSHARE_TOKEN 等
uvicorn app.main:app --reload
```

- 健康检查: `GET http://localhost:8000/health`
- API 文档: `http://localhost:8000/docs`
- 选股接口: `GET http://localhost:8000/api/stock/screening?page=1&page_size=20`（需先登录获取鉴权）

## 2. 定时拉数

- 每日 17:00 由 APScheduler 自动执行。
- **首次部署后**请务必执行一次同步，否则选股列表无数据：调用 `POST /api/admin/stock-sync`（Header 带 `X-Admin-Secret: 与 .env 中 ADMIN_SECRET 一致`），或执行 `cd backend && python -m app.scripts.sync_stock`。
- 拉数逻辑在 `backend/app/services/stock_sync_service.py`，依赖 Tushare（`tushare_client.py`）与 data-model 中的 stock_basic、stock_daily_quote、stock_financial。

## 3. 前端

```bash
cd frontend
npm install
npm run dev
```

- 打开综合选股页（左侧菜单「综合选股」）；确认列表分页、筛选（代码、涨跌幅、市盈率等）与后端 API 一致；数据日期展示为「今天/昨天」。

## 4. 验证清单（与 spec 对应）

- [ ] 列表分页正常，可切换每页条数。
- [ ] 筛选：股票代码、涨跌幅、股价、市盈率、市净率、ROE、毛利率 生效。
- [ ] 数据日期/更新时间展示正确（今天/昨天）。
- [ ] 无数据/异常时友好提示，并写日志（后端 logs/app.log）。
