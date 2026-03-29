-- 【已废弃 2026-03-29】极值已迁至 stock_daily_bar.cum_hist_high / cum_hist_low（见 add_stock_daily_bar_cum_hist.sql）。
-- 已有库在迁走后执行 remove_stock_basic_hist_extrema.sql；新库勿执行本文件。
--
-- 以下为历史脚本留存：
-- stock_basic：历史最高价/最低价（旧方案）
ALTER TABLE stock_basic
  ADD COLUMN hist_high DECIMAL(12,4) NULL COMMENT '历史最高价（日线 high 全历史最大值）';

ALTER TABLE stock_basic
  ADD COLUMN hist_low DECIMAL(12,4) NULL COMMENT '历史最低价（日线 low 全历史最小值）';

ALTER TABLE stock_basic
  ADD COLUMN hist_extrema_computed_at DATETIME NULL COMMENT '历史极值最近计算时间';
