# API 契约：同步任务与监控

**功能**: 005-数据源重构 | **日期**: 2026-03-21

## 1. 手动触发同步

- **路径**: `POST /api/admin/stock-sync`
- **鉴权**: Header `X-Admin-Secret`
- **说明**: 手动触发一次增量同步或历史回灌；请求成功后异步执行，立即返回批次号

### 请求体

```json
{
  "mode": "incremental",
  "modules": ["basic", "daily", "weekly", "monthly", "financial"],
  "start_date": null,
  "end_date": null
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | `incremental` 或 `backfill`；规格上**全量回灌**指相对结束日回溯约**近三年**（与 `--preset three-year` 一致） |
| `modules` | string[] | 否 | 指定执行模块；不传表示执行默认全模块 |
| `start_date` | string | 否 | 回灌开始日期，`YYYY-MM-DD` |
| `end_date` | string | 否 | 回灌结束日期，`YYYY-MM-DD` |

### 成功响应

```json
{
  "status": "started",
  "batch_id": "stock-20260321-170001",
  "mode": "incremental",
  "message": "同步任务已触发"
}
```

### 错误约定

- `403`：鉴权失败
- `422`：参数非法，例如 `backfill` 缺少日期范围
- `503`：未配置 `ADMIN_SECRET`

## 2. 任务列表

- **路径**: `GET /api/admin/sync-jobs`
- **鉴权**: Bearer Token 登录态；仅允许用户 `杨佳兴`（`id=2`）访问

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，上限 100 |
| `status` | string | 否 | 任务状态筛选 |
| `job_mode` | string | 否 | `incremental` / `backfill` |
| `job_name` | string | 否 | 任务名筛选 |

### 成功响应

```json
{
  "items": [
    {
      "batch_id": "stock-20260321-170001",
      "job_name": "stock_sync_daily",
      "job_mode": "incremental",
      "status": "partial_failed",
      "trade_date": "2026-03-21",
      "started_at": "2026-03-21T17:00:01",
      "finished_at": "2026-03-21T17:15:22",
      "basic_rows": 5000,
      "daily_rows": 5000,
      "weekly_rows": 0,
      "monthly_rows": 0,
      "report_rows": 4820,
      "failed_stock_count": 180,
      "error_message": "financial 模块存在部分股票失败"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

## 3. 任务详情

- **路径**: `GET /api/admin/sync-jobs/{batch_id}`
- **鉴权**: Bearer Token 登录态；仅允许用户 `杨佳兴`（`id=2`）访问

### 成功响应

```json
{
  "batch_id": "stock-20260321-170001",
  "job_name": "stock_sync_daily",
  "job_mode": "incremental",
  "status": "partial_failed",
  "trade_date": "2026-03-21",
  "started_at": "2026-03-21T17:00:01",
  "finished_at": "2026-03-21T17:15:22",
  "stock_total": 5000,
  "basic_rows": 5000,
  "daily_rows": 5000,
  "weekly_rows": 0,
  "monthly_rows": 0,
  "report_rows": 4820,
  "failed_stock_count": 180,
  "error_message": "financial 模块存在部分股票失败",
  "extra_json": {
    "modules": {
      "basic": "success",
      "daily": "success",
      "weekly": "skipped",
      "monthly": "skipped",
      "financial": "partial_failed"
    },
    "failed_codes": ["000001.SZ", "600000.SH"]
  }
}
```

### 错误约定

- `403`：非 `杨佳兴` 用户或无权查看
- `404`：批次号不存在

## 3.1 子任务状态列表（`sync_task`）

- **路径**: `GET /api/admin/sync-tasks`
- **鉴权**: Bearer Token；仅允许用户 `杨佳兴`（`id=2`）访问（与批次列表相同）

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，上限 100 |
| `status` | string | 否 | 子任务状态：`pending` / `running` / `success` / `failed` 等 |
| `task_type` | string | 否 | `basic` / `daily` / `weekly` / `monthly` |
| `trigger_type` | string | 否 | `auto`（定时） / `manual`（预留） |
| `trade_date_from` | string | 否 | 交易日下限，`YYYY-MM-DD` |
| `trade_date_to` | string | 否 | 交易日上限，`YYYY-MM-DD` |

### 成功响应

```json
{
  "items": [
    {
      "id": 1,
      "trade_date": "2026-03-21",
      "task_type": "daily",
      "trigger_type": "auto",
      "status": "success",
      "batch_id": "stock-auto-20260321-170001",
      "rows_affected": 5000,
      "error_message": null,
      "started_at": "2026-03-21T17:00:05",
      "finished_at": "2026-03-21T17:02:10",
      "created_at": "2026-03-21T17:00:00"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 20
}
```

## 3.2 补偿重试某一交易日

- **路径**: `POST /api/admin/sync-jobs/retry-date`
- **鉴权**: Bearer Token 登录态；仅允许用户 `杨佳兴`（`id=2`）访问
- **说明**: 选择某个交易日，手动触发一次该交易日的**增量补偿同步**，成功后立即返回新的 `batch_id`。

### 请求体

```json
{
  "trade_date": "2026-03-21",
  "modules": ["basic", "daily", "weekly", "monthly"]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trade_date` | string | 是 | 需补偿的交易日，`YYYY-MM-DD` |
| `modules` | string[] | 否 | 指定模块；不传表示默认增量模块 |

### 成功响应

```json
{
  "status": "started",
  "batch_id": "stock-retry-20260321-211500",
  "mode": "incremental",
  "message": "已触发 2026-03-21 的补偿同步"
}
```

### 错误约定

- `403`：非 `杨佳兴` 用户或无权查看
- `422`：参数非法，例如日期格式错误

## 4. 状态语义

| 状态 | 说明 |
|------|------|
| `running` | 任务正在执行 |
| `success` | 所有模块全部成功 |
| `partial_failed` | 至少一个模块部分失败或部分股票失败 |
| `failed` | 整批失败 |
| `skipped` | 非交易日或执行条件不满足而跳过 |

## 5. 契约约定

- 任务监控页面只依赖本契约返回的结构化数据，不依赖日志文件。
- 任务监控页面不再要求输入管理密钥；页面打开后直接基于当前登录用户权限拉取数据。
- `modules` 的合法值由后端统一校验；前端仅按契约传递。
- `incremental` 模式默认面向最新交易日；`backfill` 模式必须显式给出日期范围。
- 周/月线增量以 `stk_weekly_monthly` 为准：优先按 `trade_date` 查询；若该日返回空，后端会自动回退到 `start_date/end_date` 区间查询并按股票取最新快照，避免非周/月末日期出现全量 0 行。
