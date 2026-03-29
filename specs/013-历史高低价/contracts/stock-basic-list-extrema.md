# 接口契约补充：股票基本信息列表中的历史极值（013）

**主契约**：`specs/003-股票基本信息/contracts/api-stock-basic.md`  
**本文件**：仅描述在 **003** 既有 `GET /stock/basic` 上增加的字段与语义，避免重复整份主契约。

**前缀**：与 003 一致，完整路径为 `GET /api/stock/basic`。

## 1. 变更说明

在 **`items[]` 每条记录**中增加以下可选字段（**语义**来自 `stock_daily_bar` 最新行的累计极值，**非** `stock_basic` 持久化列）：

| 字段 | 类型 | 可空 | 说明 |
|------|------|------|------|
| `hist_high` | `number` | 是 | 最新日线 `cum_hist_high`；无日线或未计算为 `null`。 |
| `hist_low` | `number` | 是 | 最新日线 `cum_hist_low`。 |
| `hist_extrema_computed_at` | `string`（ISO 8601） | 是 | 最新日线行 `updated_at`；无日线为 `null`。 |

**响应示例片段**（仅演示新增字段）：

```json
{
  "items": [
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "hist_high": 18.5,
      "hist_low": 8.2,
      "hist_extrema_computed_at": "2026-03-28T18:00:05"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "last_synced_at": null
}
```

## 2. 错误约定

与 003 一致：`500` 时 `{ "detail": "中文说明" }`。极值字段缺失不应单独报错；若整表查询失败则统一 500。

## 3. 非目标

- **不**新增「触发全量极值重算」的 HTTP 接口（见 `spec.md` Clarifications）。
- 列表仍**不**要求 `Authorization`（与 003 一致）。
