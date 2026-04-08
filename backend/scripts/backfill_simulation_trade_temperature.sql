-- 可选：为迁移前已存在的 simulation_trade 行按买入日回填大盘温度。
-- 同一 trade_date 若存在多版本 formula_version，取 id 最大的一行。
-- 执行前请备份。

UPDATE simulation_trade st
INNER JOIN market_temperature_daily mtd
  ON mtd.trade_date = st.buy_date
  AND mtd.id = (
    SELECT MAX(m2.id)
    FROM market_temperature_daily m2
    WHERE m2.trade_date = st.buy_date
  )
SET
  st.market_temp_score = mtd.temperature_score,
  st.market_temp_level = mtd.temperature_level
WHERE st.market_temp_level IS NULL;
