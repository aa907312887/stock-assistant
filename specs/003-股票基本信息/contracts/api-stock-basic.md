# 接口契约：股票基本信息（003）

**功能**: 003-股票基本信息 | **日期**: 2026-03-21

**前缀**: 假设后端 `app` 挂载在 `/api` 下，则完整路径为 `/api/stock/basic/...`（以 `main.py` 中 `include_router(..., prefix="/api")` + 路由 `prefix="/stock/basic"` 为准）。

**鉴权**: 本功能接口**不**要求 `Authorization`、**不**要求 `X-Admin-Secret`（与 `003/spec.md` 一致）。

---

## 1. 分页查询股票基本信息

- **方法/路径**: `GET /stock/basic`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 默认 `1`，≥1 |
| page_size | int | 否 | 默认 `20`，建议 1～100 |
| code | string | 否 | 代码模糊匹配 |
| name | string | 否 | 名称模糊匹配 |
| exchange | string | 否 | 交易所等值（SSE/SZSE/BSE） |
| market | string | 否 | 板块等值（主板/创业板/科创板/北交所等） |
| industry | string | 否 | 行业名称模糊 |

- **响应 200** JSON:

```json
{
  "items": [
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "exchange": "SZSE",
      "market": "主板",
      "industry_name": "银行",
      "region": "深圳",
      "list_date": "1991-04-03",
      "synced_at": "2026-03-21T10:00:00"
    }
  ],
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "last_synced_at": "2026-03-21T10:00:00"
}
```

- `last_synced_at`: 对 `stock_basic.synced_at` 的 **MAX**（全表最近一次写入时间）；若无数据可为 `null`。

- **错误**: `500` 时 `{ "detail": "中文说明" }`（与项目统一）。

---

## 2. 手动触发基础信息同步

- **方法/路径**: `POST /stock/basic/sync`
- **请求体**: 无（或空 JSON）

- **响应 200**（**同步**执行，请求在同步完成后返回；全市场可能耗时较长，前端宜放宽超时）:

```json
{
  "status": "ok",
  "message": "已写入 5200 条股票基本信息",
  "stock_basic": 5200
}
```

- **语义**: 在同一请求内执行 `run_sync_basic_only`；`stock_basic` 为本次处理的列表条数（与全市场股票数一致）。

- **错误**: `502` 上游 Tushare 拉取失败；`500` 数据库或其它错误；`detail` 为中文说明。

---

## 3. 与现有接口区分

| 接口 | 说明 |
|------|------|
| `POST /api/admin/stock-sync` | 全量同步（行情+财务等），需 `X-Admin-Secret` |
| `POST /api/stock/basic/sync` | **仅**基础信息，**无**鉴权 |

---

## 4. 前端调用约定

- 列表：`GET /api/stock/basic?page=1&page_size=20&code=...`
- 手动同步：`POST /api/stock/basic/sync`
- 使用 `fetch`/`axios` 时**不**附带登录 token（若全局 axios 自动带 token，需对本路径单独处理或允许后端忽略——实现时以「后端不校验」为准）。
