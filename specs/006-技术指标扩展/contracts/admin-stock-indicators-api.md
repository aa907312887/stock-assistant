# 接口契约：管理端 - 股票技术指标回填

**功能**: 006-技术指标扩展 | **本期范围**: 触发均线/MACD 计算写入 bar 表，**不提供**用户选股接口。

## POST `/api/admin/stock-indicators`

**用途**：手工触发指标填充（全量/区间/增量），便于首次上线与环境修复。

**鉴权**：与现有 `POST /api/admin/stock-sync` **同级**（仅管理员或内网；以实现为准）。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | `incremental`：按最近窗口更新；`backfill`：按日期区间重算；`full`：每标的该周期**全部** K 线重算并写回 |
| `timeframes` | string[] | 否 | 默认 `["daily","weekly","monthly"]` |
| `start_date` | string | `backfill` 必填 | `YYYY-MM-DD`，区间起 |
| `end_date` | string | `backfill` 必填 | `YYYY-MM-DD`，区间止 |
| `limit` | int | 否 | 仅处理前 N 只标的（演练） |

### 响应（JSON）

| 字段 | 类型 | 说明 |
|------|------|------|
| `batch_id` | string | 本次任务批次号 |
| `status` | string | `success` / `partial_failed` / `failed` |
| `rows_updated` | object | 可选，各周期或合计更新行数近似 |
| `error_message` | string \| null | 失败摘要 |

### 错误码

| HTTP | 说明 |
|------|------|
| 401 | 未登录或无权限 |
| 422 | 参数非法 |
| 500 | 服务异常 |

**说明**：若本期优先 CLI 而暂缓 HTTP，可将本契约标记为「可选实现」，但须在 `plan.md` 中保持一致。
