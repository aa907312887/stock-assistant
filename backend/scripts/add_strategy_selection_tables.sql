-- 策略选股：执行快照 / 候选明细 / 信号事件

CREATE TABLE IF NOT EXISTS strategy_execution_snapshot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  execution_id VARCHAR(64) NOT NULL,
  strategy_id VARCHAR(64) NOT NULL,
  strategy_version VARCHAR(32) NOT NULL,
  market VARCHAR(16) NOT NULL DEFAULT 'A股',
  as_of_date DATE NOT NULL,
  timeframe VARCHAR(16) NOT NULL DEFAULT 'daily',
  params_json JSON NULL,
  assumptions_json JSON NULL,
  data_source VARCHAR(32) NOT NULL DEFAULT 'tushare',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_strategy_execution_id (execution_id),
  KEY idx_strategy_exec_strategy_date (strategy_id, as_of_date),
  KEY idx_strategy_exec_as_of_date (as_of_date)
);

CREATE TABLE IF NOT EXISTS strategy_selection_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  execution_id VARCHAR(64) NOT NULL,
  stock_code VARCHAR(20) NOT NULL,
  trigger_date DATE NOT NULL,
  summary_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_strategy_sel_execution_stock (execution_id, stock_code),
  KEY idx_strategy_sel_execution_id (execution_id),
  KEY idx_strategy_sel_stock_trigger (stock_code, trigger_date)
);

CREATE TABLE IF NOT EXISTS strategy_signal_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  execution_id VARCHAR(64) NOT NULL,
  stock_code VARCHAR(20) NOT NULL,
  event_date DATE NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  event_payload_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_strategy_evt_execution_stock (execution_id, stock_code),
  KEY idx_strategy_evt_stock_date (stock_code, event_date),
  KEY idx_strategy_evt_type_date (event_type, event_date)
);

