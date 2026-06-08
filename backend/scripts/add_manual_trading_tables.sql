-- 手动模拟交易相关表
-- 执行方式：mysql -u root -p stock_assistant < add_manual_trading_tables.sql

CREATE TABLE IF NOT EXISTS `manual_trading_session` (
    `id`                   BIGINT        NOT NULL AUTO_INCREMENT,
    `session_id`           VARCHAR(64)   NOT NULL COMMENT '业务唯一标识，格式 mt-{uuid8}',
    `user_id`              BIGINT        NOT NULL COMMENT '所属用户',
    `name`                 VARCHAR(100)  NULL     COMMENT '会话备注名',
    `asset_name`           VARCHAR(100)  NOT NULL COMMENT '自定义标的名称',
    `start_date`           DATE          NOT NULL COMMENT '起始模拟日',
    `current_date`         DATE          NOT NULL COMMENT '当前模拟日',
    `reference_price`      DECIMAL(16,4) NULL     COMMENT '比例跟盘参考价',
    `position_value`       DECIMAL(20,2) NOT NULL DEFAULT 0 COMMENT '持仓名义金额（元）',
    `total_invested`       DECIMAL(20,2) NOT NULL DEFAULT 0 COMMENT '累计买入金额（元）',
    `awaiting_reval`       TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否待录入收盘价',
    `last_advance_step`    VARCHAR(10)   NULL     COMMENT '最近一次推进步长',
    `first_operation_date` DATE          NULL     COMMENT '首笔操作日',
    `status`               VARCHAR(20)   NOT NULL DEFAULT 'active' COMMENT 'active / ended',
    `end_date`             DATE          NULL     COMMENT '结束日',
    `created_at`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mts_session_id` (`session_id`),
    KEY `idx_mts_user_status` (`user_id`, `status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='手动模拟交易会話';

CREATE TABLE IF NOT EXISTS `manual_trading_operation` (
    `id`               BIGINT        NOT NULL AUTO_INCREMENT,
    `session_id`       VARCHAR(64)   NOT NULL COMMENT '所属会话',
    `op_type`          VARCHAR(20)   NOT NULL COMMENT 'buy / reval / end',
    `op_date`          DATE          NOT NULL COMMENT '操作对应模拟日',
    `price`            DECIMAL(16,4) NULL     COMMENT '成交价或收盘价',
    `buy_amount`       DECIMAL(20,2) NULL     COMMENT '买入金额',
    `advance_step`     VARCHAR(10)   NULL     COMMENT '推进步长',
    `position_before`  DECIMAL(20,2) NOT NULL COMMENT '操作前持仓名义金额',
    `position_after`   DECIMAL(20,2) NOT NULL COMMENT '操作后持仓名义金额',
    `segment_pnl`      DECIMAL(20,2) NULL     COMMENT '本段盈亏',
    `created_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_mto_session_date` (`session_id`, `op_date`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='手动模拟交易操作流水';
