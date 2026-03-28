# 接口契约：Tushare 日线前复权探测（管理端）

**目的**：满足 `spec.md` FR-007 / SC-006——在正式将 `pro_bar`（`qfq`）接入同步链路前，提供可 HTTP 调用的探测接口，验证 Token、参数与返回结构。

**基础路径前缀**：与现有后端一致，为 `/api`（见 `backend/app/main.py`）。

**鉴权**：与现有管理接口一致，请求头 **`X-Admin-Secret`**，值等于服务端环境变量配置的 `ADMIN_SECRET`（同 `backend/app/api/admin.py` 中 `_check_admin`）。未配置 `ADMIN_SECRET` 时返回 **503**。

---

## 1. 探测日线前复权 `pro_bar`

**建议路径与方法**：`GET /api/admin/tushare-probe/pro-bar-qfq`（实现阶段可微调路径，但须在 `quickstart.md` 与本文档保持一致）。

### 1.1 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_code` | string | 是 | Tushare 证券代码，如 `000001.SZ` |
| `start_date` | string | 是 | `YYYYMMDD` |
| `end_date` | string | 是 | `YYYYMMDD`，可与 `start_date` 相同以测单日 |
| `limit` | int | 否 | 最大返回行数，默认如 `20`，防止一次拉满全历史 |

### 1.2 成功响应（200）

**Content-Type**：`application/json`

**Body 结构（逻辑）**：

```json
{
  "ok": true,
  "ts_code": "000001.SZ",
  "adj": "qfq",
  "freq": "D",
  "row_count": 5,
  "sample": [
    {
      "trade_date": "20240102",
      "open": 10.12,
      "high": 10.34,
      "low": 10.05,
      "close": 10.20,
      "vol": 1234567.0,
      "amount": 23456789.0
    }
  ],
  "error": null
}
```

- `sample` 为按日期倒序或正序均可，**须在契约中固定一种**并在实现中写清；建议**时间正序**便于阅读。
- 数值精度以 Python/JSON 序列化为准；与落库 `Decimal` 转换规则在实现层统一。

### 1.3 错误响应

| HTTP 状态 | 场景 | Body 建议 |
|-----------|------|-----------|
| 400 | 缺少 `ts_code` / 日期格式错误 | `{"ok": false, "detail": "..."}` |
| 403 | `X-Admin-Secret` 错误 | 同现有 admin |
| 503 | 未配置 `ADMIN_SECRET` 或 `TUSHARE_TOKEN` | `detail` 说明 |
| 502 / 500 | Tushare 调用失败 | `{"ok": false, "detail": "TushareClientError: ..."}` |

---

## 2. （可选）探测周/月线复权 `stk_week_month_adj`

**建议路径**：`GET /api/admin/tushare-probe/stk-week-month-adj-qfq`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_code` | string | 否 | 不填则配合 `trade_date` 拉全市场（注意 6000 行上限） |
| `freq` | string | 是 | `week` 或 `month` |
| `start_date` / `end_date` | string | 与文档一致 | `YYYYMMDD`；与现有 `stk_week_month_adj` 用法对齐 |

**响应**：返回原始行中 `open_qfq`、`close_qfq` 等字段的抽样数组，用于确认积分权限与字段存在性。

---

## 3. 验收与门禁

- **通过标准**：探测接口在预发/本地对至少 1 只 A 股、至少 1 个交易日返回非空 `sample`，且 `adj` 为 `qfq`；责任人签字或工单勾选。
- **门禁**：未通过前，**禁止**在 `get_daily_by_trade_date` 替换为生产全量同步路径合并入主干（或禁止在生产环境开启新同步开关）。
