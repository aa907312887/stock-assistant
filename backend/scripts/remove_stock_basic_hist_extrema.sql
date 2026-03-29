-- 历史极值已迁至 stock_daily_bar.cum_hist_high / cum_hist_low；从 stock_basic 删除冗余列。
-- 须先完成 add_stock_daily_bar_cum_hist.sql 并执行全量重算后再执行本脚本。

ALTER TABLE stock_basic
  DROP COLUMN hist_high,
  DROP COLUMN hist_low,
  DROP COLUMN hist_extrema_computed_at;
