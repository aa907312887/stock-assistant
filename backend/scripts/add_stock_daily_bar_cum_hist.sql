-- 日线表增加「截至该交易日（含）」累计最高/最低，供回测按日读取，避免全表终态泄露未来信息。
-- 执行后请跑：cd backend && python -m app.scripts.recompute_hist_extrema_full

ALTER TABLE stock_daily_bar
  ADD COLUMN cum_hist_high DECIMAL(12,4) NULL COMMENT '截至该交易日(含)日线high扩展最大值',
  ADD COLUMN cum_hist_low DECIMAL(12,4) NULL COMMENT '截至该交易日(含)日线low扩展最小值';
