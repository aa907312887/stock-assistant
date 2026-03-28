-- stock_basic：历史最高价/最低价（来自 stock_daily_bar 全历史聚合，见 specs/013-历史高低价）
ALTER TABLE stock_basic
  ADD COLUMN hist_high DECIMAL(12,4) NULL COMMENT '历史最高价（日线 high 全历史最大值）';

ALTER TABLE stock_basic
  ADD COLUMN hist_low DECIMAL(12,4) NULL COMMENT '历史最低价（日线 low 全历史最小值）';

ALTER TABLE stock_basic
  ADD COLUMN hist_extrema_computed_at DATETIME NULL COMMENT '历史极值最近计算时间';
