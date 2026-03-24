-- 个人持仓：portfolio_trade / portfolio_operation / portfolio_trade_image
-- MySQL 8+，与 specs/007-个人持仓/data-model.md 对齐

CREATE TABLE IF NOT EXISTS portfolio_trade (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'open' COMMENT 'open | closed',
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    avg_cost DECIMAL(18, 6) NULL,
    total_qty DECIMAL(20, 6) NULL,
    total_cost_basis DECIMAL(24, 6) NULL COMMENT '持仓成本基数，用于加权',
    accumulated_realized_pnl DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '未平仓前已实现的卖出盈亏累计',
    realized_pnl DECIMAL(20, 6) NULL COMMENT '清仓后整笔已实现盈亏',
    review_text TEXT NULL,
    manual_realized_pnl DECIMAL(20, 6) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_pt_user_stock_open (user_id, stock_code, status),
    KEY idx_pt_user_closed (user_id, closed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS portfolio_operation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    op_type VARCHAR(16) NOT NULL COMMENT 'open | add | reduce | close',
    op_date DATE NOT NULL,
    qty DECIMAL(20, 6) NOT NULL,
    price DECIMAL(18, 6) NOT NULL,
    amount DECIMAL(20, 6) NULL,
    fee DECIMAL(20, 6) NULL DEFAULT 0,
    operation_rating VARCHAR(8) NULL COMMENT 'good | bad',
    note VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_po_trade (trade_id),
    KEY idx_po_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS portfolio_trade_image (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trade_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    mime_type VARCHAR(64) NOT NULL,
    size_bytes INT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_pti_trade (trade_id),
    KEY idx_pti_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
