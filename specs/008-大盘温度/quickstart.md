# 快速开始：大盘温度

## 1. 目标

在本地完成以下验证：

1. 成功拉取四指数历史数据；
2. 成功计算近三年每日大盘温度并入库；
3. 「股票信息 → 大盘温度」页可展示5档温度、悬浮策略提示与“?”口径说明，并支持按自然日区间查询历史序列；
4. 可手动触发重算并看到结果更新。

---

## 2. 前置准备

- 已配置行情数据访问凭据（Tushare Token）
- 本地 MySQL 已启动
- 后端与前端依赖已安装
- 数据库迁移脚本已执行（包含大盘温度相关新表）

建议环境变量：

```bash
export TUSHARE_TOKEN="你的token"
export MARKET_TEMPERATURE_FORMULA_VERSION="v1.0.0"
```

---

## 3. 初始化历史数据（近三年）

1) 拉取四年指数日线（预热窗口 + 三年正式区间）  
2) 计算并写入近三年结果

```bash
python -m backend.app.scripts.fill_market_temperature --years 3 --warmup-years 1 --version v1.0.0
```

执行成功后应看到：
- 处理交易日数量
- 成功写入条数
- 失败条数（通常应为 0）

---

## 4. 启动服务并验证接口

启动后端：

```bash
# 按项目现有启动方式执行
```

验证接口：

```bash
curl "http://localhost:8000/api/market-temperature/latest"
curl "http://localhost:8000/api/market-temperature/trend?days=20"
curl "http://localhost:8000/api/market-temperature/explain"
curl "http://localhost:8000/api/market-temperature/range?start_date=2024-01-01&end_date=2024-06-30"
```

---

## 5. 手动重算验证

使用管理员 token 调用：

```bash
curl -X POST "http://localhost:8000/api/admin/market-temperature/rebuild" \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
    "formula_version": "v1.0.0",
    "force_refresh_source": false
  }'
```

预期：
- 返回 `accepted`
- 对应日期段温度数据更新成功

---

## 6. 前端验收步骤

1. 打开侧栏「股票信息 → 大盘温度」，进入大盘温度页。  
2. 检查温度为5档之一，且有对应文案。  
3. 鼠标悬停档位，出现策略提示。  
4. 点击“?”按钮，弹出计算口径说明。  
5. 选择历史起止日期并「查询」，确认趋势区展示区间内全部交易日，主区为区间内最后一笔交易日快照。  
6. 点击「恢复默认」，回到近 20 个交易日与最新快照。  
7. 切换移动端模式，确认主区有当日单行操作建议，策略说明弹层可读；近 20 日（或查询区间）为彩色方块：上行档位名、下行温度分；五档并列「档位：操作」全文仅在「?」中查看。  

### US1 验收补充

- 「股票信息」首项子菜单「大盘温度」可进入专属页面并可见大盘温度卡片
- 卡片展示：分值、档位、更新时间
- 当数据状态为 `stale/failed` 时有异常提示

### US2 验收补充

- 可看到最近 20 个交易日趋势：每日两行（档位名 + 分数）
- 可看到升温/降温/持平方向提示
- 可看到当前档位对应的仓位建议文案

### US3 验收补充

- 鼠标悬停策略文案可查看完整提示（tooltip）
- 点击 `?` 可打开口径说明弹层
- 弹层展示版本、因子权重与分级说明

---

## 7. 常见问题

- **问题**：最新交易日显示 `stale`  
  **处理**：检查当日行情是否拉取成功，必要时执行手动重算。

- **问题**：趋势数据不足 20 日  
  **处理**：确认历史初始化脚本是否完整执行，检查交易日日历缺口。

- **问题**：重算接口返回 401  
  **处理**：确认管理员 token 权限与过期时间。

## 8. 全链路验证记录（示例）

- 验证日期：2026-03-24
- 数据初始化：已执行 `fill_market_temperature.py`（待在真实环境复验）
- 后端接口：`latest/trend/range/explain/rebuild` 已实现（待联调验证）
- 前端模块：「股票信息 → 大盘温度」页、区间查询与口径弹层已接入（待浏览器回归）
