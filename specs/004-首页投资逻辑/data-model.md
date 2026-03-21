# 数据模型：首页投资逻辑（三面 + 历史 + 权重）

## 1. 变更范围

- **不再**在 `user` 表存放整段投资逻辑正文（若历史实现曾增加 `investment_logic` 列，升级时应**移除该列**或弃用并迁移数据后删除，以本表为准）。  
- **新增**独立表 **`investment_logic_entry`**：每行表示某用户的一条投资逻辑快照，含**技术面 / 基本面 / 消息面**三面正文、三面权重及时间字段。

## 2. 表：`investment_logic_entry`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK, AUTO_INCREMENT | 主键 |
| user_id | BIGINT | NOT NULL, FK → `user.id` | 所属用户 |
| technical_content | TEXT | NULL | 技术面正文 |
| fundamental_content | TEXT | NULL | 基本面正文 |
| message_content | TEXT | NULL | 消息面正文 |
| weight_technical | TINYINT UNSIGNED | NOT NULL | 技术面权重（百分比整数 0–100） |
| weight_fundamental | TINYINT UNSIGNED | NOT NULL | 基本面权重 |
| weight_message | TINYINT UNSIGNED | NOT NULL | 消息面权重 |
| created_at | DATETIME | NOT NULL | **新增**该条时写入，语义为「本条投资逻辑的产生时间」 |
| updated_at | DATETIME | NOT NULL | **修改**该条时更新；新建时可与 `created_at` 相同或由应用写入 |
| extra_json | JSON | NULL | **扩展字段**：与全库「结构化 + `extra_json`」策略一致。约定键 **`insights`**：`string[]`，表示「重要感悟」第1点、第2点…（仅非空项落库）；其它键可后续扩展 |

### 2.1 校验规则（应用层）

- **权重**：`weight_technical + weight_fundamental + weight_message = 100`，且各值 ∈ [0, 100] 的整数。  
- **正文**：保存时三面经**去首尾空白**后，**至少一面**非空；否则拒绝保存。  
- **长度**：每一面 `TEXT` 字段受 MySQL `TEXT` 上限约束，应用层可再设字符/字节上限并返回 400。  
- **extra_json**：可选；若提供则须为合法 JSON 对象（顶层为 object）。**`insights`**：字符串数组，表示重要感悟，条数与单条长度由应用层限制（与后端常量一致）。

### 2.2 索引

- `user_id`：索引，便于按用户查列表与取「当前」条。  
- 可选：`(user_id, updated_at DESC)` 辅助「查当前最新」；若数据量小，单 `user_id` + 应用层排序亦可。

### 2.3 关系

- `user` 1 : N `investment_logic_entry`。

### 2.4 「当前」用于首页

- 对该 `user_id` 下所有行，取 **`updated_at` 最大**的一条；若并列，取 **`id` 最大**的一条。  
- 无行则首页为空状态。

## 3. ORM 映射（SQLAlchemy）

- 新建模型：`app.models.investment_logic_entry.InvestmentLogicEntry`（或项目命名风格一致）；`extra_json` 使用 SQLAlchemy `JSON` 类型映射 MySQL `JSON`。  
- `User` 模型增加 `relationship` 到 `InvestmentLogicEntry`（可选，按需）。

## 4. 与文档同步

- 实现时同步更新 **`docs/数据库设计.md`**：在「用户模块」下新增小节 **1.2 投资逻辑条目表 `investment_logic_entry`**；若 `user` 表曾文档化 `investment_logic` 列，应删除该说明。
