import http from './http'

export interface ScreeningItem {
  code: string
  name: string | null
  exchange: string | null
  trade_date: string | null
  open: number | null
  high: number | null
  low: number | null
  /** 截至本行数据日（含）的日线累计历史高/低价；周月 K 取周期结束日对应日线 */
  hist_high: number | null
  hist_low: number | null
  close: number | null
  price: number | null
  prev_close: number | null
  change_amount: number | null
  pct_change: number | null
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  macd_dif: number | null
  macd_dea: number | null
  macd_hist: number | null
  volume: number | null
  amount: number | null
  amplitude: number | null
  turnover_rate: number | null
  pe: number | null
  pe_ttm: number | null
  pe_percentile: number | null
  pb: number | null
  dv_ratio: number | null
  report_date: string | null
  revenue: number | null
  net_profit: number | null
  eps: number | null
  gross_profit_margin: number | null
  roe: number | null
  bps: number | null
  net_margin: number | null
  debt_to_assets: number | null
  updated_at: string | null
}

export type ScreeningTimeframe = 'daily' | 'weekly' | 'monthly'

export interface ScreeningResponse {
  items: ScreeningItem[]
  total: number
  page: number
  page_size: number
  timeframe: ScreeningTimeframe
  data_date: string | null
}

export interface LatestDateResponse {
  date: string | null
  timeframe: ScreeningTimeframe
}

export function getScreening(params: {
  page?: number
  page_size?: number
  code?: string
  name?: string
  /** 是否均线多头排列 */
  ma_bull?: boolean
  /** 是否 MACD 红柱（柱>0） */
  macd_red?: boolean
  /** 是否 MA5 上穿 MA10（相对上一根同周期 K） */
  ma_cross?: boolean
  /** 是否 MACD 金叉（DIF 上穿 DEA） */
  macd_cross?: boolean
  /** 日K / 周K / 月K，默认 daily */
  timeframe?: ScreeningTimeframe
  data_date?: string
}) {
  return http.get<ScreeningResponse>('/stock/screening', { params })
}

export function getLatestDate(params?: { timeframe?: ScreeningTimeframe }) {
  return http.get<LatestDateResponse>('/stock/screening/latest-date', { params })
}
