-- 增量迁移：新增 sync_task 子任务状态表（与 sync_job_run 配合）
-- 执行：mysql -u root -p stock_assistant < backend/scripts/add_sync_task.sql

USE stock_assistant;

CREATE TABLE IF NOT EXISTS sync_task (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  trade_date      DATE         NOT NULL COMMENT '交易日',
  task_type       VARCHAR(32)  NOT NULL COMMENT 'basic/daily/weekly/monthly',
  trigger_type    VARCHAR(16)  NOT NULL COMMENT 'auto/manual',
  status          VARCHAR(32)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/success/failed/skipped/cancelled',
  batch_id        VARCHAR(64)  DEFAULT NULL COMMENT '关联 sync_job_run.batch_id',
  rows_affected   INT          NOT NULL DEFAULT 0 COMMENT '本任务写入行数',
  error_message   TEXT         DEFAULT NULL COMMENT '失败原因',
  started_at      DATETIME     DEFAULT NULL COMMENT '开始执行时间',
  finished_at     DATETIME     DEFAULT NULL COMMENT '结束时间',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_sync_task_trade_type_trigger (trade_date, task_type, trigger_type),
  KEY idx_sync_task_status (status),
  KEY idx_sync_task_batch (batch_id),
  KEY idx_sync_task_trade (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='同步子任务状态表';
