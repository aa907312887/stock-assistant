# 快速开始：首页投资逻辑（三面 · 历史表）

## 1. 数据库

在 MySQL 执行（库名与 `.env` 一致）：

```sql
CREATE TABLE `investment_logic_entry` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `technical_content` TEXT NULL COMMENT '技术面',
  `fundamental_content` TEXT NULL COMMENT '基本面',
  `message_content` TEXT NULL COMMENT '消息面',
  `weight_technical` TINYINT UNSIGNED NOT NULL,
  `weight_fundamental` TINYINT UNSIGNED NOT NULL,
  `weight_message` TINYINT UNSIGNED NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `extra_json` JSON NULL COMMENT '扩展字段',
  PRIMARY KEY (`id`),
  KEY `ix_investment_logic_entry_user_id` (`user_id`),
  CONSTRAINT `fk_investment_logic_entry_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

若表已存在但缺少扩展列，可执行：

```sql
ALTER TABLE `investment_logic_entry`
  ADD COLUMN `extra_json` JSON NULL COMMENT '扩展字段' AFTER `updated_at`;
```

若早期曾在 `user` 表增加 `investment_logic` 列，请按迁移策略处理后再执行：

```sql
-- 若确认弃用该列（请先备份数据）
-- ALTER TABLE `user` DROP COLUMN `investment_logic`;
```

## 2. 后端验证顺序

1. `POST /api/auth/login` 获取 Token。  
2. `GET /api/investment-logic/current` → 初始多为 `{ "entry": null }`。  
3. `POST /api/investment-logic/entries`，body 示例：

```json
{
  "technical_content": "趋势与量价",
  "fundamental_content": "ROE 与估值",
  "message_content": "政策与舆情",
  "weight_technical": 40,
  "weight_fundamental": 40,
  "weight_message": 20
}
```

4. `GET /api/investment-logic/current` 与 `GET /api/investment-logic/entries` 核对。  
5. `PUT /api/investment-logic/entries/1`、`DELETE /api/investment-logic/entries/1` 按需验证。

## 3. 前端

登录后访问 `/`，检查空状态 → 新增 → 首页三面与权重 → 历史入口与列表。

## 4. 文档

更新 **`docs/数据库设计.md`** 用户模块小节，与 `data-model.md` 一致。
