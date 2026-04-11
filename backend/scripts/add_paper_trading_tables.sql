-- 历史模拟交易相关表
-- 执行方式：mysql -u root -p stock_assistant < add_paper_trading_tables.sql

-- 1. 模拟交易会话表
CREATE TABLE IF NOT EXISTS `paper_trading_session` (
    `id`             BIGINT       NOT NULL AUTO_INCREMENT,
    `session_id`     VARCHAR(64)  NOT NULL COMMENT '业务唯一标识，格式 pt-{uuid8}',
    `name`           VARCHAR(100) NULL     COMMENT '用户自定义会话名称',
    `start_date`     DATE         NOT NULL COMMENT '模拟起始日期',
    `current_date`   DATE         NOT NULL COMMENT '当前模拟日期',
    `current_phase`  VARCHAR(10)  NOT NULL DEFAULT 'open' COMMENT '当前时间节点：open（开盘）/ close（收盘）',
    `initial_cash`   DECIMAL(20,2) NOT NULL COMMENT '初始资金（元）',
    `available_cash` DECIMAL(20,2) NOT NULL COMMENT '当前可用现金（元）',
    `status`         VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT '会话状态：active / ended',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pts_session_id` (`session_id`),
    KEY `idx_pts_status` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史模拟交易会话';

-- 2. 持仓批次表（每次买入一条记录，支持 FIFO 卖出和精确 T+1 判断）
CREATE TABLE IF NOT EXISTS `paper_trading_position` (
    `id`                 BIGINT       NOT NULL AUTO_INCREMENT,
    `session_id`         VARCHAR(64)  NOT NULL COMMENT '所属会话标识',
    `stock_code`         VARCHAR(20)  NOT NULL COMMENT '股票代码',
    `stock_name`         VARCHAR(50)  NULL     COMMENT '股票名称（冗余存储）',
    `buy_date`           DATE         NOT NULL COMMENT '买入日期（模拟日期），T+1 判断依据',
    `buy_price`          DECIMAL(12,4) NOT NULL COMMENT '买入价格（用户输入）',
    `quantity`           INT          NOT NULL COMMENT '买入数量（股），100 的整数倍',
    `remaining_quantity` INT          NOT NULL COMMENT '剩余未卖出数量',
    `commission`         DECIMAL(12,4) NOT NULL COMMENT '买入手续费（元）',
    `status`             VARCHAR(20)  NOT NULL DEFAULT 'holding' COMMENT '批次状态：holding / closed',
    `created_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ptp_session_stock` (`session_id`, `stock_code`, `buy_date`),
    KEY `idx_ptp_session_status` (`session_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史模拟交易持仓批次';

-- 3. 交易记录表（每笔买入/卖出操作的完整记录）
CREATE TABLE IF NOT EXISTS `paper_trading_order` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT,
    `session_id`  VARCHAR(64)  NOT NULL COMMENT '所属会话标识',
    `order_type`  VARCHAR(10)  NOT NULL COMMENT '交易类型：buy / sell',
    `stock_code`  VARCHAR(20)  NOT NULL COMMENT '股票代码',
    `stock_name`  VARCHAR(50)  NULL     COMMENT '股票名称',
    `trade_date`  DATE         NOT NULL COMMENT '交易日期（当前模拟日期）',
    `price`       DECIMAL(12,4) NOT NULL COMMENT '成交价格（用户输入）',
    `quantity`    INT          NOT NULL COMMENT '成交数量（股）',
    `amount`      DECIMAL(20,2) NOT NULL COMMENT '成交金额（price × quantity）',
    `commission`  DECIMAL(12,4) NOT NULL COMMENT '手续费（元）',
    `cash_after`  DECIMAL(20,2) NOT NULL COMMENT '交易后账户可用现金（元）',
    `position_id` BIGINT       NULL     COMMENT '关联持仓批次 ID（卖出时填写）',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_pto_session` (`session_id`, `trade_date`),
    KEY `idx_pto_session_stock` (`session_id`, `stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史模拟交易记录';
