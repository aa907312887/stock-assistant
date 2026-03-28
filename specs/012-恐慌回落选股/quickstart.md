# 快速验证：恐慌回落选股

**前置**：本地 MySQL 已迁移、日线与 `stock_basic` 有数据；后端 `uvicorn`、前端 dev server 已启动；用户已登录。

## 1. 确认策略已注册

```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://localhost:8000/api/strategies" | head
```

响应 `items` 中应包含 `strategy_id: "panic_pullback"`，`route_path` 为 `/strategy/panic-pullback`。

## 2. 拉取策略说明

```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://localhost:8000/api/strategies/panic_pullback"
```

应返回 `name`、`description`、`assumptions`、`risks`。

## 3. 执行选股

```bash
curl -s -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{}' \
  "http://localhost:8000/api/strategies/panic_pullback/execute"
```

检查：

- `execution.as_of_date` 为最近交易日；
- `items[].exchange`、`items[].market` 存在且与数据库 `stock_basic` 一致；
- `summary` 中含策略口径字段（如 `day_drop_pct` 等）。

## 4. 只读最新结果

```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://localhost:8000/api/strategies/panic_pullback/latest"
```

应与上次执行（同 `as_of_date`、未改库）条目一致。

## 5. 前端

1. 浏览器打开 `#/strategy/panic-pullback`（或项目路由等价路径）。
2. 点击「手动执行」或「查询最新结果」，表格展示代码、名称、**交易所**、**板块**、触发日。
3. 使用交易所、板块多选缩小列表；清空后条数恢复。
4. 标题旁「?」悬浮可见口径说明（与 spec 一致）。

## 6. 定时自动选股（可选）

- 后端进程需调用 `start_scheduler()`（与日常部署一致）。
- **交易日 17:20（Asia/Shanghai）** 应自动执行 `panic_pullback` 并落库；日志关键字：`恐慌回落定时筛选完成` 或跳过原因。
- 与「冲高回落战法」同一时刻触发，逻辑均为「先校验当日开市再 `execute_strategy`」。

## 7. 异常场景（可选）

- 停库或清空日线后执行 POST，应收到 **409** `DATA_NOT_READY`。
- 从未执行过时 GET `latest`，应 **404** `NOT_FOUND`。
