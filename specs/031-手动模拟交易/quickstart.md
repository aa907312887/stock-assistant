# 本地运行与验证：手动模拟交易

**日期**: 2026-06-06 | **规格**: [spec.md](./spec.md)

## 前置条件

- MySQL 已启动，后端 `.env` 配置正确
- 已存在登录用户（本功能 API 需 JWT）

## 1. 数据库迁移

```bash
cd backend
mysql -u root -p stock_assistant < scripts/add_manual_trading_tables.sql
# 或按项目惯例：
python scripts/run_migration.py
```

确认存在表：`manual_trading_session`、`manual_trading_operation`。

## 2. 启动服务

```bash
# 终端 1 - 后端
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 2 - 前端
cd frontend
npm run dev
```

## 3. 菜单与路由

- 侧栏：**智能回测 → 手动模拟交易**（最后一项）
- 列表：`/backtest/manual-trading`
- 详情：`/backtest/manual-trading/:sessionId`

## 4. 核心验收路径（规格 SC-001 / SC-002）

1. 登录后进入「手动模拟交易」，新建会话：标的「纳斯达克100」，起始 `2001-01-01`。
2. 买入：金额 `100000`，成交价 `2000` → 持仓 10 万，累计买入 10 万。
3. 点击「推进一年」→ 当前日变为 `2002-01-01`，页面提示待录入收盘价。
4. 录入收盘价 `1800` → 持仓 **90000**，本段盈亏 **−10000**。
5. 结束交易 → 状态「已结束」，总盈亏 −1 万，总交易时间 365 天（2001-01-01 至 2002-01-01）。
6. 刷新或重新登录 → 会话与流水仍存在。

## 5. API 快速验证（可选）

```bash
TOKEN="<登录后 access_token>"

curl -s -X POST http://localhost:8000/api/manual-trading/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"asset_name":"纳斯达克100","start_date":"2001-01-01"}'

# 将返回的 session_id 代入后续请求
SID="mt-xxxxxxxx"

curl -s -X POST "http://localhost:8000/api/manual-trading/sessions/$SID/buy" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":100000,"price":2000}'

curl -s -X POST "http://localhost:8000/api/manual-trading/sessions/$SID/advance" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"step":"year"}'

curl -s -X POST "http://localhost:8000/api/manual-trading/sessions/$SID/reval" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"close_price":1800}'
```

## 6. 自动化测试

```bash
cd backend
pytest tests/test_manual_trading.py -v
```

用例须覆盖：比例跟盘公式、awaiting_reval 门禁、无买入不可结束、用户隔离。
