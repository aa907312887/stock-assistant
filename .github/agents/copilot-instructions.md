# stock-assistant Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-21

## Active Technologies
- Python 3.12（后端）、TypeScript（前端） + FastAPI、Vue 3、Vite、SQLAlchemy、MySQL、pandas、APScheduler、Tushare API (002-综合选股)
- MySQL（用户、股票基础、股票日维度行情/基本面等表） (002-综合选股)

- Python 3.12 (backend), TypeScript (frontend) + FastAPI, Vue 3, Vite, SQLAlchemy, MySQL, Pinia, Element Plus (001-用户登录)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.12 (backend), TypeScript (frontend): Follow standard conventions

## Recent Changes
- 004-首页投资逻辑: 表 `investment_logic_entry`（三面+权重+历史）、`/api/investment-logic/current` 与 `entries` CRUD、首页 `HomeView` 显著区与历史回顾（见 specs/004-首页投资逻辑/plan.md）
- 003-股票基本信息: 周频仅写 stock_basic、APScheduler 周任务、`GET/POST /api/stock/basic` 无鉴权、Vue 页面 + 悬浮能力说明（见 specs/003-股票基本信息/plan.md）


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
