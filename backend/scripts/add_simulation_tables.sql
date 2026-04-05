-- 历史模拟任务表
CREATE TABLE IF NOT EXISTS simulation_task (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  task_id          VARCHAR(64) NOT NULL UNIQUE,
  strategy_id      VARCHAR(64) NOT NULL,
  strategy_version VARCHAR(32) NOT NULL,
  start_date       DATE NOT NULL,
  end_date         DATE NOT NULL,
  status           VARCHAR(20) NOT NULL DEFAULT 'running',
  total_trades     INT NULL,
  win_trades       INT NULL,
  lose_trades      INT NULL,
  win_rate         DECIMAL(8,4) NULL,
  avg_return       DECIMAL(12,4) NULL,
  max_win          DECIMAL(12,4) NULL,
  max_loss         DECIMAL(12,4) NULL,
  unclosed_count   INT NOT NULL DEFAULT 0,
  skipped_count    INT NOT NULL DEFAULT 0,
  error_message    TEXT NULL,
  assumptions_json JSON NULL,
  strategy_description TEXT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at      DATETIME NULL,
  INDEX idx_sim_task_strategy (strategy_id, created_at),
  INDEX idx_sim_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 历史模拟交易明细表
CREATE TABLE IF NOT EXISTS simulation_trade (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  task_id        VARCHAR(64) NOT NULL,
  stock_code     VARCHAR(20) NOT NULL,
  stock_name     VARCHAR(50) NULL,
  buy_date       DATE NOT NULL,
  buy_price      DECIMAL(12,4) NOT NULL,
  sell_date      DATE NULL,
  sell_price     DECIMAL(12,4) NULL,
  return_rate    DECIMAL(12,4) NULL,
  trade_type     VARCHAR(16) NOT NULL DEFAULT 'closed',
  exchange       VARCHAR(10) NULL,
  market         VARCHAR(20) NULL,
  extra_json     JSON NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_sim_trade_task (task_id),
  INDEX idx_sim_trade_stock (stock_code, buy_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
