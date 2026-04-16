-- Tushare 复权因子 adj_factor 按标的、交易日落库，供日线前复权合成与其它按需计算。
-- 执行后请跑全量/增量同步以灌数；清空迁移见 truncate_for_qfq_migration.sql

CREATE TABLE IF NOT EXISTS stock_adj_factor (
    id BIGINT NOT NULL AUTO_INCREMENT,
    stock_code VARCHAR(20) NOT NULL COMMENT 'ts_code，如 000001.SZ',
    trade_date DATE NOT NULL COMMENT '交易日',
    adj_factor DECIMAL(20, 6) NOT NULL COMMENT 'Tushare adj_factor 累计复权因子',
    sync_batch_id VARCHAR(64) NULL,
    synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_adj_factor_code_date (stock_code, trade_date),
    KEY idx_adj_factor_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
