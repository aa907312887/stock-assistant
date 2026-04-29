/*
 Navicat Premium Data Transfer

 Source Server         : localhost
 Source Server Type    : MySQL
 Source Server Version : 80030 (8.0.30)
 Source Host           : localhost:3306
 Source Schema         : stock_assistant

 Target Server Type    : MySQL
 Target Server Version : 80030 (8.0.30)
 File Encoding         : 65001

 Date: 29/04/2026 20:53:50
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for backtest_task
-- ----------------------------
DROP TABLE IF EXISTS `backtest_task`;
CREATE TABLE `backtest_task` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'running',
  `total_trades` int DEFAULT NULL,
  `win_trades` int DEFAULT NULL,
  `lose_trades` int DEFAULT NULL,
  `win_rate` decimal(8,4) DEFAULT NULL,
  `total_return` decimal(12,4) DEFAULT NULL,
  `avg_return` decimal(12,4) DEFAULT NULL,
  `max_win` decimal(12,4) DEFAULT NULL,
  `max_loss` decimal(12,4) DEFAULT NULL,
  `unclosed_count` int NOT NULL DEFAULT '0',
  `skipped_count` int NOT NULL DEFAULT '0',
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `assumptions_json` json DEFAULT NULL,
  `strategy_description` text COLLATE utf8mb4_unicode_ci COMMENT '策略逻辑说明（回测时快照）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_backtest_task_id` (`task_id`),
  KEY `idx_backtest_task_strategy` (`strategy_id`,`created_at`),
  KEY `idx_backtest_task_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=90 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for backtest_trade
-- ----------------------------
DROP TABLE IF EXISTS `backtest_trade`;
CREATE TABLE `backtest_trade` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `buy_date` date NOT NULL,
  `buy_price` decimal(12,4) NOT NULL,
  `sell_date` date DEFAULT NULL,
  `sell_price` decimal(12,4) DEFAULT NULL,
  `return_rate` decimal(12,4) DEFAULT NULL,
  `trade_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'closed',
  `market_temp_score` decimal(5,2) DEFAULT NULL,
  `market_temp_level` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extra_json` json DEFAULT NULL,
  `user_decision` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'excellent=优秀决策 wrong=错误决策',
  `user_decision_reason` varchar(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '评价理由',
  `user_decision_at` datetime DEFAULT NULL COMMENT '评价时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `exchange` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '交易所：SSE/SZSE/BSE',
  `market` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '板块：主板/创业板/科创板/北交所',
  `trigger_date` date DEFAULT NULL COMMENT '形态或信号触发日',
  PRIMARY KEY (`id`),
  KEY `idx_bt_trade_task_id` (`task_id`),
  KEY `idx_bt_trade_stock` (`stock_code`,`buy_date`),
  KEY `idx_bt_trade_type` (`task_id`,`trade_type`),
  KEY `idx_bt_trade_temp` (`task_id`,`market_temp_level`),
  KEY `idx_bt_trade_exchange` (`task_id`,`exchange`),
  KEY `idx_bt_trade_market` (`task_id`,`market`)
) ENGINE=InnoDB AUTO_INCREMENT=927286 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for index_basic
-- ----------------------------
DROP TABLE IF EXISTS `index_basic`;
CREATE TABLE `index_basic` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ts_code` varchar(32) NOT NULL,
  `name` varchar(128) DEFAULT NULL,
  `fullname` varchar(255) DEFAULT NULL,
  `market` varchar(16) DEFAULT NULL,
  `publisher` varchar(64) DEFAULT NULL,
  `index_type` varchar(64) DEFAULT NULL,
  `category` varchar(64) DEFAULT NULL,
  `base_date` date DEFAULT NULL,
  `base_point` decimal(16,4) DEFAULT NULL,
  `list_date` date DEFAULT NULL,
  `weight_rule` varchar(255) DEFAULT NULL,
  `description` text,
  `exp_date` date DEFAULT NULL,
  `data_source` varchar(32) NOT NULL DEFAULT 'tushare',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_basic_ts` (`ts_code`),
  KEY `idx_index_basic_market` (`market`)
) ENGINE=InnoDB AUTO_INCREMENT=12463 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for index_daily_bar
-- ----------------------------
DROP TABLE IF EXISTS `index_daily_bar`;
CREATE TABLE `index_daily_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_code` varchar(32) NOT NULL,
  `trade_date` date NOT NULL,
  `open` decimal(12,4) DEFAULT NULL,
  `high` decimal(12,4) DEFAULT NULL,
  `low` decimal(12,4) DEFAULT NULL,
  `close` decimal(12,4) DEFAULT NULL,
  `ma5` decimal(16,8) DEFAULT NULL,
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `prev_close` decimal(12,4) DEFAULT NULL,
  `change_amount` decimal(12,4) DEFAULT NULL,
  `pct_change` decimal(10,4) DEFAULT NULL,
  `volume` decimal(20,2) DEFAULT NULL,
  `amount` decimal(20,2) DEFAULT NULL,
  `amplitude` decimal(10,4) DEFAULT NULL,
  `data_source` varchar(32) NOT NULL DEFAULT 'tushare',
  `sync_batch_id` varchar(64) DEFAULT NULL,
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_daily_code_date` (`index_code`,`trade_date`),
  KEY `idx_index_daily_trade_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=12167207 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for index_monthly_bar
-- ----------------------------
DROP TABLE IF EXISTS `index_monthly_bar`;
CREATE TABLE `index_monthly_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_code` varchar(32) NOT NULL,
  `trade_month_end` date NOT NULL,
  `open` decimal(12,4) DEFAULT NULL,
  `high` decimal(12,4) DEFAULT NULL,
  `low` decimal(12,4) DEFAULT NULL,
  `close` decimal(12,4) DEFAULT NULL,
  `ma5` decimal(16,8) DEFAULT NULL,
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `change_amount` decimal(12,4) DEFAULT NULL,
  `pct_change` decimal(10,4) DEFAULT NULL,
  `volume` decimal(20,2) DEFAULT NULL,
  `amount` decimal(20,2) DEFAULT NULL,
  `data_source` varchar(32) NOT NULL DEFAULT 'tushare',
  `sync_batch_id` varchar(64) DEFAULT NULL,
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_monthly_code_end` (`index_code`,`trade_month_end`),
  KEY `idx_index_monthly_end` (`trade_month_end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for index_weekly_bar
-- ----------------------------
DROP TABLE IF EXISTS `index_weekly_bar`;
CREATE TABLE `index_weekly_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_code` varchar(32) NOT NULL,
  `trade_week_end` date NOT NULL,
  `open` decimal(12,4) DEFAULT NULL,
  `high` decimal(12,4) DEFAULT NULL,
  `low` decimal(12,4) DEFAULT NULL,
  `close` decimal(12,4) DEFAULT NULL,
  `ma5` decimal(16,8) DEFAULT NULL,
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `change_amount` decimal(12,4) DEFAULT NULL,
  `pct_change` decimal(10,4) DEFAULT NULL,
  `volume` decimal(20,2) DEFAULT NULL,
  `amount` decimal(20,2) DEFAULT NULL,
  `data_source` varchar(32) NOT NULL DEFAULT 'tushare',
  `sync_batch_id` varchar(64) DEFAULT NULL,
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_weekly_code_end` (`index_code`,`trade_week_end`),
  KEY `idx_index_weekly_end` (`trade_week_end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for index_weight
-- ----------------------------
DROP TABLE IF EXISTS `index_weight`;
CREATE TABLE `index_weight` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_code` varchar(32) NOT NULL,
  `con_code` varchar(32) NOT NULL,
  `trade_date` date NOT NULL,
  `weight` decimal(12,4) NOT NULL,
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_weight` (`index_code`,`con_code`,`trade_date`),
  KEY `idx_index_weight_index` (`index_code`),
  KEY `idx_index_weight_td` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for investment_logic_entry
-- ----------------------------
DROP TABLE IF EXISTS `investment_logic_entry`;
CREATE TABLE `investment_logic_entry` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `technical_content` text COLLATE utf8mb4_unicode_ci COMMENT '技术面内容',
  `fundamental_content` text COLLATE utf8mb4_unicode_ci COMMENT '基本面内容',
  `message_content` text COLLATE utf8mb4_unicode_ci COMMENT '消息面内容',
  `weight_technical` int NOT NULL COMMENT '技术面权重',
  `weight_fundamental` int NOT NULL COMMENT '基本面权重',
  `weight_message` int NOT NULL COMMENT '消息面权重',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `extra_json` json DEFAULT NULL COMMENT '扩展字段',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `fk_investment_logic_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='投资逻辑条目表';

-- ----------------------------
-- Table structure for market_index_daily_quote
-- ----------------------------
DROP TABLE IF EXISTS `market_index_daily_quote`;
CREATE TABLE `market_index_daily_quote` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_code` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trade_date` date NOT NULL,
  `open` decimal(12,4) DEFAULT NULL,
  `high` decimal(12,4) DEFAULT NULL,
  `low` decimal(12,4) DEFAULT NULL,
  `close` decimal(12,4) DEFAULT NULL,
  `vol` decimal(20,4) DEFAULT NULL,
  `amount` decimal(20,4) DEFAULT NULL,
  `source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_market_index_date` (`index_code`,`trade_date`),
  KEY `idx_market_index_trade_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=25145 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for market_temperature_copywriting
-- ----------------------------
DROP TABLE IF EXISTS `market_temperature_copywriting`;
CREATE TABLE `market_temperature_copywriting` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `content_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `level_name` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `formula_version` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for market_temperature_daily
-- ----------------------------
DROP TABLE IF EXISTS `market_temperature_daily`;
CREATE TABLE `market_temperature_daily` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL,
  `temperature_score` decimal(5,2) NOT NULL,
  `temperature_level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trend_flag` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL,
  `delta_score` decimal(5,2) NOT NULL DEFAULT '0.00',
  `strategy_hint` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'normal',
  `formula_version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'v1.0.0',
  `generated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_temp_trade_date_version` (`trade_date`,`formula_version`),
  KEY `idx_temp_trade_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=6287 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for market_temperature_factor_daily
-- ----------------------------
DROP TABLE IF EXISTS `market_temperature_factor_daily`;
CREATE TABLE `market_temperature_factor_daily` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL,
  `trend_score` decimal(5,2) NOT NULL,
  `liquidity_score` decimal(5,2) NOT NULL,
  `risk_score` decimal(5,2) NOT NULL,
  `trend_weight` decimal(4,2) NOT NULL DEFAULT '0.40',
  `liquidity_weight` decimal(4,2) NOT NULL DEFAULT '0.30',
  `risk_weight` decimal(4,2) NOT NULL DEFAULT '0.30',
  `formula_version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'v1.0.0',
  `generated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_factor_trade_date_version` (`trade_date`,`formula_version`)
) ENGINE=InnoDB AUTO_INCREMENT=6287 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for market_temperature_level_rule
-- ----------------------------
DROP TABLE IF EXISTS `market_temperature_level_rule`;
CREATE TABLE `market_temperature_level_rule` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `level_name` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `score_min` decimal(5,2) NOT NULL,
  `score_max` decimal(5,2) NOT NULL,
  `strategy_action` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_hint` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `visual_token` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_level_name` (`level_name`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for paper_trading_order
-- ----------------------------
DROP TABLE IF EXISTS `paper_trading_order`;
CREATE TABLE `paper_trading_order` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) NOT NULL COMMENT '所属会话标识',
  `order_type` varchar(10) NOT NULL COMMENT '交易类型：buy / sell',
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(50) DEFAULT NULL COMMENT '股票名称',
  `trade_date` date NOT NULL COMMENT '交易日期（当前模拟日期）',
  `price` decimal(12,4) NOT NULL COMMENT '成交价格（用户输入）',
  `quantity` int NOT NULL COMMENT '成交数量（股）',
  `amount` decimal(20,2) NOT NULL COMMENT '成交金额（price × quantity）',
  `commission` decimal(12,4) NOT NULL COMMENT '手续费（元）',
  `cash_after` decimal(20,2) NOT NULL COMMENT '交易后账户可用现金（元）',
  `position_id` bigint DEFAULT NULL COMMENT '关联持仓批次 ID（卖出时填写）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pto_session` (`session_id`,`trade_date`),
  KEY `idx_pto_session_stock` (`session_id`,`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=178 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='历史模拟交易记录';

-- ----------------------------
-- Table structure for paper_trading_position
-- ----------------------------
DROP TABLE IF EXISTS `paper_trading_position`;
CREATE TABLE `paper_trading_position` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) NOT NULL COMMENT '所属会话标识',
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(50) DEFAULT NULL COMMENT '股票名称（冗余存储）',
  `buy_date` date NOT NULL COMMENT '买入日期（模拟日期），T+1 判断依据',
  `buy_price` decimal(12,4) NOT NULL COMMENT '买入价格（用户输入）',
  `quantity` int NOT NULL COMMENT '买入数量（股），100 的整数倍',
  `remaining_quantity` int NOT NULL COMMENT '剩余未卖出数量',
  `commission` decimal(12,4) NOT NULL COMMENT '买入手续费（元）',
  `status` varchar(20) NOT NULL DEFAULT 'holding' COMMENT '批次状态：holding / closed',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ptp_session_stock` (`session_id`,`stock_code`,`buy_date`),
  KEY `idx_ptp_session_status` (`session_id`,`status`)
) ENGINE=InnoDB AUTO_INCREMENT=104 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='历史模拟交易持仓批次';

-- ----------------------------
-- Table structure for paper_trading_session
-- ----------------------------
DROP TABLE IF EXISTS `paper_trading_session`;
CREATE TABLE `paper_trading_session` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) NOT NULL COMMENT '业务唯一标识，格式 pt-{uuid8}',
  `name` varchar(100) DEFAULT NULL COMMENT '用户自定义会话名称',
  `start_date` date NOT NULL COMMENT '模拟起始日期',
  `current_date` date NOT NULL COMMENT '当前模拟日期',
  `current_phase` varchar(10) NOT NULL DEFAULT 'open' COMMENT '当前时间节点：open（开盘）/ close（收盘）',
  `initial_cash` decimal(20,2) NOT NULL COMMENT '初始资金（元）',
  `available_cash` decimal(20,2) NOT NULL COMMENT '当前可用现金（元）',
  `status` varchar(20) NOT NULL DEFAULT 'active' COMMENT '会话状态：active / ended',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pts_session_id` (`session_id`),
  KEY `idx_pts_status` (`status`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='历史模拟交易会话';

-- ----------------------------
-- Table structure for portfolio_operation
-- ----------------------------
DROP TABLE IF EXISTS `portfolio_operation`;
CREATE TABLE `portfolio_operation` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `trade_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `op_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'open | add | reduce | close',
  `op_date` date NOT NULL,
  `qty` decimal(20,6) NOT NULL,
  `price` decimal(18,6) NOT NULL,
  `amount` decimal(20,6) DEFAULT NULL,
  `fee` decimal(20,6) DEFAULT '0.000000',
  `operation_rating` varchar(8) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'good | bad',
  `note` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_po_trade` (`trade_id`),
  KEY `idx_po_user` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for portfolio_trade
-- ----------------------------
DROP TABLE IF EXISTS `portfolio_trade`;
CREATE TABLE `portfolio_trade` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'open' COMMENT 'open | closed',
  `opened_at` datetime NOT NULL,
  `closed_at` datetime DEFAULT NULL,
  `avg_cost` decimal(18,6) DEFAULT NULL,
  `total_qty` decimal(20,6) DEFAULT NULL,
  `total_cost_basis` decimal(24,6) DEFAULT NULL COMMENT '持仓成本基数，用于加权',
  `accumulated_realized_pnl` decimal(20,6) NOT NULL DEFAULT '0.000000' COMMENT '未平仓前已实现的卖出盈亏累计',
  `realized_pnl` decimal(20,6) DEFAULT NULL COMMENT '清仓后整笔已实现盈亏',
  `review_text` text COLLATE utf8mb4_unicode_ci,
  `manual_realized_pnl` decimal(20,6) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pt_user_stock_open` (`user_id`,`stock_code`,`status`),
  KEY `idx_pt_user_closed` (`user_id`,`closed_at`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for portfolio_trade_image
-- ----------------------------
DROP TABLE IF EXISTS `portfolio_trade_image`;
CREATE TABLE `portfolio_trade_image` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `trade_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `file_path` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `size_bytes` int NOT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pti_trade` (`trade_id`),
  KEY `idx_pti_user` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for simulation_task
-- ----------------------------
DROP TABLE IF EXISTS `simulation_task`;
CREATE TABLE `simulation_task` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) NOT NULL,
  `strategy_id` varchar(64) NOT NULL,
  `strategy_version` varchar(32) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'running',
  `total_trades` int DEFAULT NULL,
  `win_trades` int DEFAULT NULL,
  `lose_trades` int DEFAULT NULL,
  `win_rate` decimal(8,4) DEFAULT NULL,
  `avg_return` decimal(12,4) DEFAULT NULL,
  `max_win` decimal(12,4) DEFAULT NULL,
  `max_loss` decimal(12,4) DEFAULT NULL,
  `unclosed_count` int NOT NULL DEFAULT '0',
  `skipped_count` int NOT NULL DEFAULT '0',
  `error_message` text,
  `assumptions_json` json DEFAULT NULL,
  `strategy_description` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `task_id` (`task_id`),
  KEY `idx_sim_task_strategy` (`strategy_id`,`created_at`),
  KEY `idx_sim_task_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for simulation_trade
-- ----------------------------
DROP TABLE IF EXISTS `simulation_trade`;
CREATE TABLE `simulation_trade` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) NOT NULL,
  `stock_code` varchar(20) NOT NULL,
  `stock_name` varchar(50) DEFAULT NULL,
  `buy_date` date NOT NULL,
  `buy_price` decimal(12,4) NOT NULL,
  `sell_date` date DEFAULT NULL,
  `sell_price` decimal(12,4) DEFAULT NULL,
  `return_rate` decimal(12,4) DEFAULT NULL,
  `trade_type` varchar(16) NOT NULL DEFAULT 'closed',
  `exchange` varchar(10) DEFAULT NULL,
  `market` varchar(20) DEFAULT NULL,
  `market_temp_score` decimal(5,2) DEFAULT NULL COMMENT '买入日大盘温度分数',
  `market_temp_level` varchar(16) DEFAULT NULL COMMENT '买入日大盘温度级别',
  `extra_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sim_trade_task` (`task_id`),
  KEY `idx_sim_trade_stock` (`stock_code`,`buy_date`),
  KEY `idx_sim_trade_temp` (`task_id`,`market_temp_level`)
) ENGINE=InnoDB AUTO_INCREMENT=265279 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for stock_adj_factor
-- ----------------------------
DROP TABLE IF EXISTS `stock_adj_factor`;
CREATE TABLE `stock_adj_factor` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'ts_code，如 000001.SZ',
  `trade_date` date NOT NULL COMMENT '交易日',
  `adj_factor` decimal(20,6) NOT NULL COMMENT 'Tushare adj_factor 累计复权因子',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_adj_factor_code_date` (`stock_code`,`trade_date`),
  KEY `idx_adj_factor_trade_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=8303182 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for stock_basic
-- ----------------------------
DROP TABLE IF EXISTS `stock_basic`;
CREATE TABLE `stock_basic` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '股票名称',
  `market` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '市场',
  `industry_code` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '行业编码',
  `industry_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '行业名称',
  `region` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '地区',
  `list_date` date DEFAULT NULL COMMENT '上市日期',
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '同步批次',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `exchange` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '交易所：SSE/SZSE/BSE',
  `hist_high` decimal(12,4) DEFAULT NULL COMMENT '历史最高价（日线 high 全历史最大值）',
  `hist_low` decimal(12,4) DEFAULT NULL COMMENT '历史最低价（日线 low 全历史最小值）',
  `hist_extrema_computed_at` datetime DEFAULT NULL COMMENT '历史极值最近计算时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_market` (`market`),
  KEY `idx_industry_code` (`industry_code`),
  KEY `idx_list_date` (`list_date`),
  KEY `idx_stock_basic_exchange` (`exchange`)
) ENGINE=InnoDB AUTO_INCREMENT=5514 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础表';

-- ----------------------------
-- Table structure for stock_daily_bar
-- ----------------------------
DROP TABLE IF EXISTS `stock_daily_bar`;
CREATE TABLE `stock_daily_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `trade_date` date NOT NULL COMMENT '交易日期',
  `open` decimal(12,4) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(12,4) DEFAULT NULL COMMENT '最高价',
  `low` decimal(12,4) DEFAULT NULL COMMENT '最低价',
  `close` decimal(12,4) DEFAULT NULL COMMENT '收盘价',
  `ma5` decimal(16,8) DEFAULT NULL COMMENT 'SMA5(close)',
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `prev_close` decimal(12,4) DEFAULT NULL COMMENT '前收盘价',
  `change_amount` decimal(12,4) DEFAULT NULL COMMENT '涨跌额',
  `pct_change` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅%',
  `volume` decimal(20,2) DEFAULT NULL COMMENT '成交量',
  `amount` decimal(20,2) DEFAULT NULL COMMENT '成交额',
  `amplitude` decimal(10,4) DEFAULT NULL COMMENT '振幅%',
  `turnover_rate` decimal(10,4) DEFAULT NULL COMMENT '换手率%',
  `volume_ratio` decimal(10,4) DEFAULT NULL COMMENT '量比',
  `total_market_cap` decimal(20,2) DEFAULT NULL COMMENT '总市值',
  `float_market_cap` decimal(20,2) DEFAULT NULL COMMENT '流通市值',
  `pe` decimal(12,4) DEFAULT NULL COMMENT '市盈率',
  `pe_ttm` decimal(12,4) DEFAULT NULL COMMENT '市盈率TTM',
  `pb` decimal(12,4) DEFAULT NULL COMMENT '市净率',
  `ps` decimal(12,4) DEFAULT NULL COMMENT '市销率',
  `dv_ratio` decimal(10,4) DEFAULT NULL COMMENT '股息率',
  `dv_ttm` decimal(10,4) DEFAULT NULL COMMENT '股息率TTM',
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '同步批次',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `cum_hist_high` decimal(12,4) DEFAULT NULL COMMENT '截至该交易日(含)日线high扩展最大值',
  `cum_hist_low` decimal(12,4) DEFAULT NULL COMMENT '截至该交易日(含)日线low扩展最小值',
  `pe_percentile` decimal(6,2) DEFAULT NULL COMMENT '当前PE在该股自2019年以来历史PE中的百分位(0-100)，仅使用严格早于当日的数据',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_daily_bar_code_date` (`stock_code`,`trade_date`),
  KEY `idx_daily_trade_stock` (`trade_date`,`stock_code`),
  KEY `idx_daily_trade_pct` (`trade_date`,`pct_change`),
  KEY `idx_daily_trade_pe` (`trade_date`,`pe`),
  KEY `idx_daily_trade_pb` (`trade_date`,`pb`)
) ENGINE=InnoDB AUTO_INCREMENT=8174953 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史日线表';

-- ----------------------------
-- Table structure for stock_financial_report
-- ----------------------------
DROP TABLE IF EXISTS `stock_financial_report`;
CREATE TABLE `stock_financial_report` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `report_date` date NOT NULL COMMENT '报告期',
  `report_type` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '报告类型',
  `ann_date` date DEFAULT NULL COMMENT '公告日期',
  `revenue` decimal(20,2) DEFAULT NULL COMMENT '营收',
  `net_profit` decimal(20,2) DEFAULT NULL COMMENT '净利润',
  `eps` decimal(12,4) DEFAULT NULL COMMENT '每股收益',
  `bps` decimal(12,4) DEFAULT NULL COMMENT '每股净资产',
  `cfps` decimal(20,4) DEFAULT NULL,
  `ebit` decimal(20,2) DEFAULT NULL COMMENT '息税前利润',
  `ocf_to_profit` decimal(20,4) DEFAULT NULL,
  `roe` decimal(20,4) DEFAULT NULL,
  `roe_dt` decimal(20,4) DEFAULT NULL,
  `roe_waa` decimal(20,4) DEFAULT NULL,
  `roa` decimal(20,4) DEFAULT NULL,
  `debt_to_assets` decimal(20,4) DEFAULT NULL,
  `current_ratio` decimal(20,4) DEFAULT NULL,
  `quick_ratio` decimal(20,4) DEFAULT NULL,
  `gross_margin` decimal(20,4) DEFAULT NULL,
  `net_margin` decimal(20,4) DEFAULT NULL,
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '同步批次',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_report` (`stock_code`,`report_date`),
  KEY `idx_stock_report_date` (`stock_code`,`report_date`),
  KEY `idx_report_date` (`report_date`)
) ENGINE=InnoDB AUTO_INCREMENT=148166 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票财报历史表';

-- ----------------------------
-- Table structure for stock_monthly_bar
-- ----------------------------
DROP TABLE IF EXISTS `stock_monthly_bar`;
CREATE TABLE `stock_monthly_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `trade_month_end` date NOT NULL COMMENT '月线结束交易日',
  `open` decimal(12,4) DEFAULT NULL COMMENT '月开盘价',
  `high` decimal(12,4) DEFAULT NULL COMMENT '月最高价',
  `low` decimal(12,4) DEFAULT NULL COMMENT '月最低价',
  `close` decimal(12,4) DEFAULT NULL COMMENT '月收盘价',
  `ma5` decimal(16,8) DEFAULT NULL COMMENT 'SMA5(close)',
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `change_amount` decimal(12,4) DEFAULT NULL COMMENT '月涨跌额',
  `pct_change` decimal(10,4) DEFAULT NULL COMMENT '月涨跌幅%',
  `volume` decimal(20,2) DEFAULT NULL COMMENT '月成交量',
  `amount` decimal(20,2) DEFAULT NULL COMMENT '月成交额',
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '同步批次',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_monthly_bar_code_date` (`stock_code`,`trade_month_end`),
  KEY `idx_monthly_trade_stock` (`trade_month_end`,`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=292509 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史月线表';

-- ----------------------------
-- Table structure for stock_weekly_bar
-- ----------------------------
DROP TABLE IF EXISTS `stock_weekly_bar`;
CREATE TABLE `stock_weekly_bar` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `trade_week_end` date NOT NULL COMMENT '周线结束交易日',
  `open` decimal(12,4) DEFAULT NULL COMMENT '周开盘价',
  `high` decimal(12,4) DEFAULT NULL COMMENT '周最高价',
  `low` decimal(12,4) DEFAULT NULL COMMENT '周最低价',
  `close` decimal(12,4) DEFAULT NULL COMMENT '周收盘价',
  `ma5` decimal(16,8) DEFAULT NULL COMMENT 'SMA5(close)',
  `ma10` decimal(16,8) DEFAULT NULL,
  `ma20` decimal(16,8) DEFAULT NULL,
  `ma60` decimal(16,8) DEFAULT NULL,
  `macd_dif` decimal(16,8) DEFAULT NULL,
  `macd_dea` decimal(16,8) DEFAULT NULL,
  `macd_hist` decimal(16,8) DEFAULT NULL,
  `change_amount` decimal(12,4) DEFAULT NULL COMMENT '周涨跌额',
  `pct_change` decimal(10,4) DEFAULT NULL COMMENT '周涨跌幅%',
  `volume` decimal(20,2) DEFAULT NULL COMMENT '周成交量',
  `amount` decimal(20,2) DEFAULT NULL COMMENT '周成交额',
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  `sync_batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '同步批次',
  `synced_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_weekly_bar_code_date` (`stock_code`,`trade_week_end`),
  KEY `idx_weekly_trade_stock` (`trade_week_end`,`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1641476 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史周线表';

-- ----------------------------
-- Table structure for strategy_execution_snapshot
-- ----------------------------
DROP TABLE IF EXISTS `strategy_execution_snapshot`;
CREATE TABLE `strategy_execution_snapshot` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `execution_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `market` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'A股',
  `as_of_date` date NOT NULL,
  `timeframe` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'daily',
  `params_json` json DEFAULT NULL,
  `assumptions_json` json DEFAULT NULL,
  `data_source` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'tushare',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_strategy_execution_id` (`execution_id`),
  KEY `idx_strategy_exec_strategy_date` (`strategy_id`,`as_of_date`),
  KEY `idx_strategy_exec_as_of_date` (`as_of_date`)
) ENGINE=InnoDB AUTO_INCREMENT=61 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for strategy_selection_item
-- ----------------------------
DROP TABLE IF EXISTS `strategy_selection_item`;
CREATE TABLE `strategy_selection_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `execution_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_date` date NOT NULL,
  `summary_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_strategy_sel_execution_stock` (`execution_id`,`stock_code`),
  KEY `idx_strategy_sel_execution_id` (`execution_id`),
  KEY `idx_strategy_sel_stock_trigger` (`stock_code`,`trigger_date`)
) ENGINE=InnoDB AUTO_INCREMENT=390 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for strategy_signal_event
-- ----------------------------
DROP TABLE IF EXISTS `strategy_signal_event`;
CREATE TABLE `strategy_signal_event` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `execution_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `event_date` date NOT NULL,
  `event_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `event_payload_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_strategy_evt_execution_stock` (`execution_id`,`stock_code`),
  KEY `idx_strategy_evt_stock_date` (`stock_code`,`event_date`),
  KEY `idx_strategy_evt_type_date` (`event_type`,`event_date`)
) ENGINE=InnoDB AUTO_INCREMENT=400 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for sync_job_run
-- ----------------------------
DROP TABLE IF EXISTS `sync_job_run`;
CREATE TABLE `sync_job_run` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `job_name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务名',
  `job_mode` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务模式 incremental/backfill',
  `trade_date` date DEFAULT NULL COMMENT '业务日期',
  `batch_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '批次号',
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'running/success/partial_failed/failed/skipped',
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
  `finished_at` datetime DEFAULT NULL COMMENT '结束时间',
  `stock_total` int DEFAULT NULL COMMENT '计划处理股票数',
  `basic_rows` int NOT NULL DEFAULT '0' COMMENT '基础信息写入数',
  `daily_rows` int NOT NULL DEFAULT '0' COMMENT '日线写入数',
  `weekly_rows` int NOT NULL DEFAULT '0' COMMENT '周线写入数',
  `monthly_rows` int NOT NULL DEFAULT '0' COMMENT '月线写入数',
  `report_rows` int NOT NULL DEFAULT '0' COMMENT '财报写入数',
  `failed_stock_count` int NOT NULL DEFAULT '0' COMMENT '单标失败数',
  `error_message` text COLLATE utf8mb4_unicode_ci COMMENT '错误摘要',
  `extra_json` json DEFAULT NULL COMMENT '扩展字段',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_id` (`batch_id`),
  KEY `idx_job_date` (`job_name`,`trade_date`),
  KEY `idx_job_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步任务运行日志表';

-- ----------------------------
-- Table structure for sync_task
-- ----------------------------
DROP TABLE IF EXISTS `sync_task`;
CREATE TABLE `sync_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `trade_date` date NOT NULL COMMENT '交易日',
  `task_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'basic/daily/weekly/monthly',
  `trigger_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'auto/manual',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/running/success/failed/skipped/cancelled',
  `batch_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '关联 sync_job_run.batch_id',
  `rows_affected` int NOT NULL DEFAULT '0' COMMENT '本任务写入行数',
  `error_message` text COLLATE utf8mb4_unicode_ci COMMENT '失败原因',
  `started_at` datetime DEFAULT NULL COMMENT '开始执行时间',
  `finished_at` datetime DEFAULT NULL COMMENT '结束时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sync_task_trade_type_trigger` (`trade_date`,`task_type`,`trigger_type`),
  KEY `idx_sync_task_status` (`status`),
  KEY `idx_sync_task_batch` (`batch_id`),
  KEY `idx_sync_task_trade` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步子任务状态表';

-- ----------------------------
-- Table structure for user
-- ----------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `username` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录用户名',
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '密码哈希',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------
-- Table structure for user_position
-- ----------------------------
DROP TABLE IF EXISTS `user_position`;
CREATE TABLE `user_position` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '股票名称',
  `quantity` decimal(20,4) NOT NULL COMMENT '持仓数量',
  `cost_price` decimal(12,4) DEFAULT NULL COMMENT '成本价',
  `profit_amount` decimal(16,4) DEFAULT NULL COMMENT '当前收益额(元)',
  `yield_rate` decimal(10,4) DEFAULT NULL COMMENT '当前收益率(%)',
  `memo` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_stock` (`user_id`,`stock_code`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `fk_position_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户持仓表';

-- ----------------------------
-- Table structure for user_trade
-- ----------------------------
DROP TABLE IF EXISTS `user_trade`;
CREATE TABLE `user_trade` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `stock_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '股票代码',
  `trade_type` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '交易类型: buy/sell',
  `quantity` decimal(20,4) NOT NULL COMMENT '成交数量',
  `price` decimal(12,4) NOT NULL COMMENT '成交价格',
  `trade_time` datetime NOT NULL COMMENT '交易时间',
  `amount` decimal(16,2) DEFAULT NULL COMMENT '成交金额',
  `memo` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_stock_type` (`user_id`,`stock_code`,`trade_type`),
  KEY `idx_trade_time` (`trade_time`),
  CONSTRAINT `fk_trade_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户交易明细表';

SET FOREIGN_KEY_CHECKS = 1;
