-- =========================================================
-- stock_assistant V3: 清库重建脚本
-- 用途：
-- 1) 删除旧版股票行情/估值相关表
-- 2) 创建新的历史日线、周线、月线与任务监控表
-- 3) 保留用户、持仓、交易与投资逻辑等现有业务表
-- 执行：
--   mysql -u root -p < backend/scripts/reset_and_init_v3.sql
-- =========================================================

CREATE DATABASE IF NOT EXISTS stock_assistant
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stock_assistant;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS sync_task;
DROP TABLE IF EXISTS sync_job_run;
DROP TABLE IF EXISTS stock_monthly_bar;
DROP TABLE IF EXISTS stock_weekly_bar;
DROP TABLE IF EXISTS stock_daily_bar;
DROP TABLE IF EXISTS stock_financial_report;
DROP TABLE IF EXISTS stock_valuation_daily;
DROP TABLE IF EXISTS stock_daily_tech;
DROP TABLE IF EXISTS stock_daily_quote;
DROP TABLE IF EXISTS investment_logic_entry;
DROP TABLE IF EXISTS stock_index_member;
DROP TABLE IF EXISTS stock_style;
DROP TABLE IF EXISTS stock_concept;
DROP TABLE IF EXISTS dict_industry;
DROP TABLE IF EXISTS stock_basic;
DROP TABLE IF EXISTS stock_financial;
DROP TABLE IF EXISTS user_trade;
DROP TABLE IF EXISTS user_position;
DROP TABLE IF EXISTS user;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE user (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  username      VARCHAR(64)  NOT NULL COMMENT '登录用户名',
  password_hash VARCHAR(255) DEFAULT NULL COMMENT '密码哈希',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

CREATE TABLE user_position (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id       BIGINT        NOT NULL COMMENT '用户ID',
  stock_code    VARCHAR(20)   NOT NULL COMMENT '股票代码',
  stock_name    VARCHAR(100)  DEFAULT NULL COMMENT '股票名称',
  quantity      DECIMAL(20,4) NOT NULL COMMENT '持仓数量',
  cost_price    DECIMAL(12,4) DEFAULT NULL COMMENT '成本价',
  profit_amount DECIMAL(16,4) DEFAULT NULL COMMENT '当前收益额(元)',
  yield_rate    DECIMAL(10,4) DEFAULT NULL COMMENT '当前收益率(%)',
  memo          VARCHAR(500)  DEFAULT NULL COMMENT '备注',
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_stock (user_id, stock_code),
  KEY idx_user_id (user_id),
  CONSTRAINT fk_position_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户持仓表';

CREATE TABLE user_trade (
  id         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id    BIGINT        NOT NULL COMMENT '用户ID',
  stock_code VARCHAR(20)   NOT NULL COMMENT '股票代码',
  trade_type VARCHAR(10)   NOT NULL COMMENT '交易类型: buy/sell',
  quantity   DECIMAL(20,4) NOT NULL COMMENT '成交数量',
  price      DECIMAL(12,4) NOT NULL COMMENT '成交价格',
  trade_time DATETIME      NOT NULL COMMENT '交易时间',
  amount     DECIMAL(16,2) DEFAULT NULL COMMENT '成交金额',
  memo       VARCHAR(500)  DEFAULT NULL COMMENT '备注',
  created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_user_stock_type (user_id, stock_code, trade_type),
  KEY idx_trade_time (trade_time),
  CONSTRAINT fk_trade_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户交易明细表';

CREATE TABLE investment_logic_entry (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id BIGINT NOT NULL COMMENT '用户ID',
  technical_content TEXT DEFAULT NULL COMMENT '技术面内容',
  fundamental_content TEXT DEFAULT NULL COMMENT '基本面内容',
  message_content TEXT DEFAULT NULL COMMENT '消息面内容',
  weight_technical INT NOT NULL COMMENT '技术面权重',
  weight_fundamental INT NOT NULL COMMENT '基本面权重',
  weight_message INT NOT NULL COMMENT '消息面权重',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  extra_json JSON DEFAULT NULL COMMENT '扩展字段',
  PRIMARY KEY (id),
  KEY idx_user_id (user_id),
  CONSTRAINT fk_investment_logic_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='投资逻辑条目表';

CREATE TABLE stock_basic (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  code          VARCHAR(20)  NOT NULL COMMENT '股票代码',
  name          VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
  market        VARCHAR(20)  DEFAULT NULL COMMENT '市场',
  industry_code VARCHAR(20)  DEFAULT NULL COMMENT '行业编码',
  industry_name VARCHAR(100) DEFAULT NULL COMMENT '行业名称',
  region        VARCHAR(50)  DEFAULT NULL COMMENT '地区',
  list_date     DATE         DEFAULT NULL COMMENT '上市日期',
  data_source   VARCHAR(32)  NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)  DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code),
  KEY idx_market (market),
  KEY idx_industry_code (industry_code),
  KEY idx_list_date (list_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础表';

CREATE TABLE stock_daily_bar (
  id               BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code       VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_date       DATE           NOT NULL COMMENT '交易日期',
  open             DECIMAL(12,4)  DEFAULT NULL COMMENT '开盘价',
  high             DECIMAL(12,4)  DEFAULT NULL COMMENT '最高价',
  low              DECIMAL(12,4)  DEFAULT NULL COMMENT '最低价',
  close            DECIMAL(12,4)  DEFAULT NULL COMMENT '收盘价',
  prev_close       DECIMAL(12,4)  DEFAULT NULL COMMENT '前收盘价',
  change_amount    DECIMAL(12,4)  DEFAULT NULL COMMENT '涨跌额',
  pct_change       DECIMAL(10,4)  DEFAULT NULL COMMENT '涨跌幅%',
  volume           DECIMAL(20,2)  DEFAULT NULL COMMENT '成交量',
  amount           DECIMAL(20,2)  DEFAULT NULL COMMENT '成交额',
  amplitude        DECIMAL(10,4)  DEFAULT NULL COMMENT '振幅%',
  turnover_rate    DECIMAL(10,4)  DEFAULT NULL COMMENT '换手率%',
  volume_ratio     DECIMAL(10,4)  DEFAULT NULL COMMENT '量比',
  total_market_cap DECIMAL(20,2)  DEFAULT NULL COMMENT '总市值',
  float_market_cap DECIMAL(20,2)  DEFAULT NULL COMMENT '流通市值',
  pe               DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率',
  pe_ttm           DECIMAL(12,4)  DEFAULT NULL COMMENT '市盈率TTM',
  pb               DECIMAL(12,4)  DEFAULT NULL COMMENT '市净率',
  ps               DECIMAL(12,4)  DEFAULT NULL COMMENT '市销率',
  dv_ratio         DECIMAL(10,4)  DEFAULT NULL COMMENT '股息率',
  dv_ttm           DECIMAL(10,4)  DEFAULT NULL COMMENT '股息率TTM',
  data_source      VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id    VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_daily_bar_code_date (stock_code, trade_date),
  KEY idx_daily_trade_stock (trade_date, stock_code),
  KEY idx_daily_trade_pct (trade_date, pct_change),
  KEY idx_daily_trade_pe (trade_date, pe),
  KEY idx_daily_trade_pb (trade_date, pb)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史日线表';

CREATE TABLE stock_weekly_bar (
  id               BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code       VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_week_end   DATE           NOT NULL COMMENT '周线结束交易日',
  open             DECIMAL(12,4)  DEFAULT NULL COMMENT '周开盘价',
  high             DECIMAL(12,4)  DEFAULT NULL COMMENT '周最高价',
  low              DECIMAL(12,4)  DEFAULT NULL COMMENT '周最低价',
  close            DECIMAL(12,4)  DEFAULT NULL COMMENT '周收盘价',
  change_amount    DECIMAL(12,4)  DEFAULT NULL COMMENT '周涨跌额',
  pct_change       DECIMAL(10,4)  DEFAULT NULL COMMENT '周涨跌幅%',
  volume           DECIMAL(20,2)  DEFAULT NULL COMMENT '周成交量',
  amount           DECIMAL(20,2)  DEFAULT NULL COMMENT '周成交额',
  data_source      VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id    VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_weekly_bar_code_date (stock_code, trade_week_end),
  KEY idx_weekly_trade_stock (trade_week_end, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史周线表';

CREATE TABLE stock_monthly_bar (
  id               BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code       VARCHAR(20)    NOT NULL COMMENT '股票代码',
  trade_month_end  DATE           NOT NULL COMMENT '月线结束交易日',
  open             DECIMAL(12,4)  DEFAULT NULL COMMENT '月开盘价',
  high             DECIMAL(12,4)  DEFAULT NULL COMMENT '月最高价',
  low              DECIMAL(12,4)  DEFAULT NULL COMMENT '月最低价',
  close            DECIMAL(12,4)  DEFAULT NULL COMMENT '月收盘价',
  change_amount    DECIMAL(12,4)  DEFAULT NULL COMMENT '月涨跌额',
  pct_change       DECIMAL(10,4)  DEFAULT NULL COMMENT '月涨跌幅%',
  volume           DECIMAL(20,2)  DEFAULT NULL COMMENT '月成交量',
  amount           DECIMAL(20,2)  DEFAULT NULL COMMENT '月成交额',
  data_source      VARCHAR(32)    NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id    VARCHAR(64)    DEFAULT NULL COMMENT '同步批次',
  synced_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_monthly_bar_code_date (stock_code, trade_month_end),
  KEY idx_monthly_trade_stock (trade_month_end, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票历史月线表';

CREATE TABLE stock_financial_report (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  stock_code    VARCHAR(20)   NOT NULL COMMENT '股票代码',
  report_date   DATE          NOT NULL COMMENT '报告期',
  report_type   VARCHAR(16)   DEFAULT NULL COMMENT '报告类型',
  revenue       DECIMAL(20,2) DEFAULT NULL COMMENT '营收',
  net_profit    DECIMAL(20,2) DEFAULT NULL COMMENT '净利润',
  eps           DECIMAL(12,4) DEFAULT NULL COMMENT '每股收益',
  bps           DECIMAL(12,4) DEFAULT NULL COMMENT '每股净资产',
  roe           DECIMAL(10,4) DEFAULT NULL COMMENT 'ROE%',
  gross_margin  DECIMAL(10,4) DEFAULT NULL COMMENT '毛利率%',
  net_margin    DECIMAL(10,4) DEFAULT NULL COMMENT '净利率%',
  data_source   VARCHAR(32)   NOT NULL DEFAULT 'tushare' COMMENT '数据源',
  sync_batch_id VARCHAR(64)   DEFAULT NULL COMMENT '同步批次',
  synced_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stock_report (stock_code, report_date),
  KEY idx_stock_report_date (stock_code, report_date),
  KEY idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票财报历史表';

CREATE TABLE sync_job_run (
  id                 BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  job_name           VARCHAR(64)   NOT NULL COMMENT '任务名',
  job_mode           VARCHAR(16)   NOT NULL COMMENT '任务模式 incremental/backfill',
  trade_date         DATE          DEFAULT NULL COMMENT '业务日期',
  batch_id           VARCHAR(64)   NOT NULL COMMENT '批次号',
  status             VARCHAR(16)   NOT NULL COMMENT 'running/success/partial_failed/failed/skipped',
  started_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
  finished_at        DATETIME      DEFAULT NULL COMMENT '结束时间',
  stock_total        INT           DEFAULT NULL COMMENT '计划处理股票数',
  basic_rows         INT           NOT NULL DEFAULT 0 COMMENT '基础信息写入数',
  daily_rows         INT           NOT NULL DEFAULT 0 COMMENT '日线写入数',
  weekly_rows        INT           NOT NULL DEFAULT 0 COMMENT '周线写入数',
  monthly_rows       INT           NOT NULL DEFAULT 0 COMMENT '月线写入数',
  report_rows        INT           NOT NULL DEFAULT 0 COMMENT '财报写入数',
  failed_stock_count INT           NOT NULL DEFAULT 0 COMMENT '单标失败数',
  error_message      TEXT          DEFAULT NULL COMMENT '错误摘要',
  extra_json         JSON          DEFAULT NULL COMMENT '扩展字段',
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_id (batch_id),
  KEY idx_job_date (job_name, trade_date),
  KEY idx_job_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步任务运行日志表';

CREATE TABLE sync_task (
  id              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  trade_date      DATE          NOT NULL COMMENT '交易日',
  task_type       VARCHAR(32)   NOT NULL COMMENT 'basic/daily/weekly/monthly',
  trigger_type    VARCHAR(16)   NOT NULL COMMENT 'auto/manual',
  status          VARCHAR(32)   NOT NULL DEFAULT 'pending' COMMENT 'pending/running/success/failed/skipped/cancelled',
  batch_id        VARCHAR(64)   DEFAULT NULL COMMENT '关联 sync_job_run.batch_id',
  rows_affected   INT           NOT NULL DEFAULT 0 COMMENT '本任务写入行数',
  error_message   TEXT          DEFAULT NULL COMMENT '失败原因',
  started_at      DATETIME      DEFAULT NULL COMMENT '开始执行时间',
  finished_at     DATETIME      DEFAULT NULL COMMENT '结束时间',
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_sync_task_trade_type_trigger (trade_date, task_type, trigger_type),
  KEY idx_sync_task_status (status),
  KEY idx_sync_task_batch (batch_id),
  KEY idx_sync_task_trade (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步子任务状态表';

INSERT INTO user (username, password_hash)
VALUES ('admin', NULL)
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;
