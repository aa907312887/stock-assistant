# API 契约：综合选股

**Feature**: 002-综合选股 | **Date**: 2025-03-15

## 1. 选股列表（分页 + 筛选）

- **路径**: `GET /api/stock/screening`（或 `/api/stocks`，与后端路由一致即可）
- **鉴权**: 需要登录态（Session/JWT），与 001 登录一致。
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，从 1 开始，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，建议上限 100 |
| code | string | 否 | 股票代码（模糊或精确，由实现约定） |
| pct_min | number | 否 | 涨跌幅下限（%） |
| pct_max | number | 否 | 涨跌幅上限（%） |
| price_min | number | 否 | 现价/收盘价下限 |
| price_max | number | 否 | 现价/收盘价上限 |
| gpm_min | number | 否 | 毛利率下限（%） |
| gpm_max | number | 否 | 毛利率上限（%） |
| revenue_min | number | 否 | 营业收入下限（元） |
| revenue_max | number | 否 | 营业收入上限（元） |
| net_profit_min | number | 否 | 净利润下限（元） |
| net_profit_max | number | 否 | 净利润上限（元） |
| data_date | string | 否 | 数据日期 YYYY-MM-DD，不传则取最新交易日 |

- **响应**（JSON）:

```json
{
  "items": [
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "exchange": "SZ",
      "trade_date": "2025-03-14",
      "open": 12.50,
      "high": 12.65,
      "low": 12.31,
      "close": 12.60,
      "prev_close": 12.50,
      "price": 12.60,
      "change_amount": 0.10,
      "pct_change": 0.80,
      "amplitude": 2.72,
      "volume": 1000000,
      "amount": 12600000.00,
      "report_date": "2024-12-31",
      "revenue": 123456789000.0,
      "net_profit": 9988776600.0,
      "eps": 2.35,
      "gross_profit_margin": 30.2,
      "updated_at": "2025-03-15T17:00:00"
    }
  ],
  "total": 5000,
  "page": 1,
  "page_size": 20,
  "data_date": "2025-03-14"
}
```

- **错误**:
  - 401 未登录
  - 500 服务异常（含友好信息，详见 spec 异常提示）
- **空结果**: total=0，items=[]，仍返回 data_date（若有）；前端提示「暂无符合条件的数据」。

---

## 2. 数据日期/最新交易日

- **路径**: `GET /api/stock/screening/latest-date`（或等价）
- **鉴权**: 需要登录态。
- **响应**: `{ "date": "2025-03-14" }`，供前端展示「数据为今天/昨天」。

---

## 3. 触发拉数（可选，管理用）

- **路径**: `POST /api/stock/sync` 或 `POST /api/admin/stock-sync`
- **鉴权**: 需登录且建议仅管理员或本地调用。
- **说明**: 部署时或手动触发一次全量拉数；实现时与定时任务共用同一套「Tushare 拉数」逻辑。
- **响应**: 202 Accepted + 任务已入队或同步执行结果摘要（由实现决定）。

---

## 4. 契约与实现约定

- 上述为契约级描述；具体路径、参数名与后端路由、Pydantic schema 一致即可。
- 技术面/消息面/人气筛选本期不暴露；后续可在本契约下扩展 query 参数与响应字段。
