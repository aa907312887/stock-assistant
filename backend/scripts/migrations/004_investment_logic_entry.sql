-- 004 首页投资逻辑：investment_logic_entry（若已存在请用 quickstart 中的 ALTER 补 extra_json）
CREATE TABLE IF NOT EXISTS `investment_logic_entry` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `technical_content` TEXT NULL COMMENT '技术面',
  `fundamental_content` TEXT NULL COMMENT '基本面',
  `message_content` TEXT NULL COMMENT '消息面',
  `weight_technical` INT NOT NULL,
  `weight_fundamental` INT NOT NULL,
  `weight_message` INT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `extra_json` JSON NULL COMMENT '扩展字段',
  PRIMARY KEY (`id`),
  KEY `ix_investment_logic_entry_user_id` (`user_id`),
  CONSTRAINT `fk_investment_logic_entry_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
