# 接口契约：历史模拟分析（筛选复算与分年）

**基础路径前缀**：`/api/simulation`（与现有 `app.api.simulation` 路由一致）  
**鉴权**：与现有 `/api/simulation/*` 相同（若全局 JWT，则沿用）。

---

## 1. 扩展交易明细列表 `GET /tasks/{task_id}/trades`

在现有查询参数基础上**新增**（与回测对齐）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `market_temp_levels` | string，可选 | 多选温度级别，**逗号分隔**，如 `冷,温,热` |
| `year` | int，可选 | 按**买入日自然年**筛选，范围建议 1990–2100 |

语义与 `GET /api/backtest/tasks/{task_id}/trades` 一致（同维 OR、跨维 AND、`markets` 含 `__EMPTY__` 表示空板块）。

**响应 `items[]` 中每条交易扩展字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `market_temp_score` | number \| null | 买入日温度分数 |
| `market_temp_level` | string \| null | 买入日温度级别 |

---

## 2. 新增筛选复算 `GET /tasks/{task_id}/filtered-report`

**用途**：对已落库的模拟交易按条件筛选后，**复算**胜率、笔数、总收益（简单加总）、平均收益等，**不**重新跑策略。

**Query 参数**（与回测 `filtered-report` 对齐，模拟无 `not_traded` 时可不传 `trade_type` 或仅 `closed`/`unclosed`）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `trade_type` | string，可选 | `closed` \| `unclosed`；不传=全部 |
| `market_temp_levels` | string，可选 | 逗号分隔 |
| `markets` | string，可选 | 逗号分隔，含 `__EMPTY__` |
| `exchanges` | string，可选 | 逗号分隔 |
| `year` | int，可选 | 买入日自然年 |

**响应 JSON**（建议与 `BacktestFilteredReportResponse` 同构，便于前端复用）：

```json
{
  "task_id": "sim-xxx",
  "filters": {
    "trade_type": null,
    "market_temp_levels": ["冷"],
    "markets": [],
    "exchanges": ["SSE"],
    "year": null
  },
  "metrics": {
    "matched_count": 120,
    "total_trades": 100,
    "win_trades": 55,
    "lose_trades": 45,
    "win_rate": 0.55,
    "total_return": 0.1234,
    "avg_return": 0.001234,
    "max_win": 0.08,
    "max_loss": -0.05,
    "unclosed_count": 5
  }
}
```

**错误**：

| HTTP | code | 说明 |
|------|------|------|
| 404 | `TASK_NOT_FOUND` | 任务不存在 |

---

## 3. 新增分年度分析 `GET /tasks/{task_id}/yearly-analysis`

**用途**：按买入日自然年聚合；可与温度、交易所、板块、`year`（单年）组合。

**Query 参数**：与 `filtered-report` 相同。

**响应 JSON**（与 `BacktestYearlyAnalysisResponse` 同构）：

```json
{
  "task_id": "sim-xxx",
  "filters": { },
  "items": [
    {
      "year": 2023,
      "matched_count": 40,
      "total_trades": 38,
      "win_trades": 20,
      "lose_trades": 18,
      "win_rate": 0.526,
      "total_return": 0.05,
      "avg_return": 0.0013
    }
  ]
}
```

**错误**：同 `filtered-report`。

---

## 4. 兼容性

- 旧前端未传新参数时行为与当前一致（全量明细）。
- 旧任务无温度列时：新字段为 `null`，筛选温度时无匹配或依赖产品对「未知」的定义。
