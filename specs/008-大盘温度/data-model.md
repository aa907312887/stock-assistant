# 数据模型：大盘温度

## 1. 实体总览

本功能涉及 5 个核心实体：

1. 大盘温度日结果（`market_temperature_daily`）
2. 大盘温度因子分项（`market_temperature_factor_daily`）
3. 指数日级行情（`market_index_daily_quote`）
4. 温度分级规则（`market_temperature_level_rule`）
5. 策略提示与口径说明（`market_temperature_copywriting`）

---

## 2. 实体定义

## 2.1 大盘温度日结果

- **表名**：`market_temperature_daily`
- **用途**：存放每个交易日的最终温度结果，用于首页展示与历史回测
- **主键**：`id`（bigint）
- **唯一键**：`uk_trade_date_version (trade_date, formula_version)`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | bigint | 是 | 自增主键 |
| trade_date | date | 是 | 交易日 |
| temperature_score | decimal(5,2) | 是 | 温度总分，0~100 |
| temperature_level | varchar(16) | 是 | 档位：极冷/偏冷/中性/偏热/过热 |
| trend_flag | varchar(8) | 是 | 升温/降温/持平 |
| delta_score | decimal(5,2) | 是 | 较上一交易日分差 |
| strategy_hint | varchar(255) | 是 | 当前档位策略提示简述 |
| data_status | varchar(16) | 是 | normal/stale/failed |
| formula_version | varchar(32) | 是 | 公式版本，如 v1.0.0 |
| generated_at | datetime | 是 | 计算完成时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**校验规则**
- `temperature_score` 必须在 `[0,100]` 区间
- `temperature_level` 必须与 `temperature_score` 区间一致
- 同一 `trade_date + formula_version` 仅允许一条记录

---

## 2.2 大盘温度因子分项

- **表名**：`market_temperature_factor_daily`
- **用途**：记录每个交易日三因子分项与权重，支持可追溯与版本回测
- **主键**：`id`
- **唯一键**：`uk_trade_date_version (trade_date, formula_version)`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | bigint | 是 | 自增主键 |
| trade_date | date | 是 | 交易日 |
| trend_score | decimal(5,2) | 是 | 趋势因子得分（0~100） |
| liquidity_score | decimal(5,2) | 是 | 量能因子得分（0~100） |
| risk_score | decimal(5,2) | 是 | 风险因子得分（0~100） |
| trend_weight | decimal(4,2) | 是 | 固定 0.40 |
| liquidity_weight | decimal(4,2) | 是 | 固定 0.30 |
| risk_weight | decimal(4,2) | 是 | 固定 0.30 |
| formula_version | varchar(32) | 是 | 公式版本 |
| generated_at | datetime | 是 | 计算完成时间 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**校验规则**
- 三个分项得分均在 `[0,100]`
- 三个权重和必须为 `1.00`

---

## 2.3 指数日级行情

- **表名**：`market_index_daily_quote`
- **用途**：缓存计算所需指数日线，支持重算与审计
- **主键**：`id`
- **唯一键**：`uk_index_date (index_code, trade_date)`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | bigint | 是 | 自增主键 |
| index_code | varchar(16) | 是 | 指数代码 |
| trade_date | date | 是 | 交易日 |
| open | decimal(12,4) | 是 | 开盘点位 |
| high | decimal(12,4) | 是 | 最高点位 |
| low | decimal(12,4) | 是 | 最低点位 |
| close | decimal(12,4) | 是 | 收盘点位 |
| vol | decimal(20,4) | 否 | 成交量 |
| amount | decimal(20,4) | 否 | 成交额 |
| source | varchar(32) | 是 | 数据源标识（tushare） |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**校验规则**
- `high >= low`
- `open/high/low/close` 均大于 0

---

## 2.4 温度分级规则

- **表名**：`market_temperature_level_rule`
- **用途**：定义5档分级和默认策略建议
- **主键**：`id`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | bigint | 是 | 自增主键 |
| level_name | varchar(16) | 是 | 档位名称 |
| score_min | decimal(5,2) | 是 | 区间下限 |
| score_max | decimal(5,2) | 是 | 区间上限 |
| strategy_action | varchar(32) | 是 | 建议动作（减仓/中性/进攻） |
| strategy_hint | varchar(255) | 是 | 档位策略提示 |
| visual_token | varchar(32) | 是 | 前端展示用十六进制颜色，如 `#1e3a8a` |
| is_active | tinyint | 是 | 是否生效 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

---

## 2.5 策略提示与口径说明

- **表名**：`market_temperature_copywriting`
- **用途**：管理悬浮提示文案和「?」口径说明的**可选补充段落**（`content`）。三因子的详细公式与设计思路由接口内嵌返回（`score_pipeline`、`factors.calculation_detail` / `design_rationale`，与 `formula.md` 同源），便于与代码同步；数据库正文可为空或仅存法务/运营短注。
- **主键**：`id`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | bigint | 是 | 自增主键 |
| content_type | varchar(32) | 是 | level_hint/formula_explain |
| level_name | varchar(16) | 否 | 对应档位，可空 |
| title | varchar(64) | 是 | 标题 |
| content | text | 是 | 正文；`formula_explain` 时可为空字符串，主说明以前端调用的 explain 接口内嵌字段为准 |
| formula_version | varchar(32) | 否 | 口径版本 |
| is_active | tinyint | 是 | 是否生效 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

---

## 3. 实体关系

- `market_temperature_daily` 1:1 `market_temperature_factor_daily`（按 trade_date + formula_version）
- `market_temperature_daily` N:1 `market_temperature_level_rule`（按 temperature_level）
- `market_temperature_factor_daily` 依赖 `market_index_daily_quote`（计算输入）
- `market_temperature_copywriting` 与 `market_temperature_level_rule` 通过 `level_name` 逻辑关联

---

## 4. 状态与流转

## 4.1 数据状态（`data_status`）

- `normal`：当日计算成功
- `stale`：当日失败，回退最近有效交易日结果用于展示
- `failed`：重试后仍失败，需人工介入

流转规则：`normal -> stale -> failed`（按调度结果驱动）；补算成功后可回到 `normal`。

---

## 5. 索引建议

- `market_temperature_daily`：
  - `uk_trade_date_version (trade_date, formula_version)`
  - `idx_trade_date (trade_date desc)`
- `market_temperature_factor_daily`：
  - `uk_trade_date_version (trade_date, formula_version)`
- `market_index_daily_quote`：
  - `uk_index_date (index_code, trade_date)`
  - `idx_trade_date (trade_date desc)`
