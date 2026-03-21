import http from './http'

export interface ScreeningItem {
  code: string
  name: string | null
  exchange: string | null
  trade_date: string | null
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  price: number | null
  prev_close: number | null
  change_amount: number | null
  pct_change: number | null
  volume: number | null
  amount: number | null
  amplitude: number | null
  turnover_rate: number | null
  report_date: string | null
  revenue: number | null
  net_profit: number | null
  eps: number | null
  gross_profit_margin: number | null
  updated_at: string | null
}

export interface ScreeningResponse {
  items: ScreeningItem[]
  total: number
  page: number
  page_size: number
  data_date: string | null
}

export interface LatestDateResponse {
  date: string | null
}

export function getScreening(params: {
  page?: number
  page_size?: number
  code?: string
  pct_min?: number
  pct_max?: number
  price_min?: number
  price_max?: number
  gpm_min?: number
  gpm_max?: number
  revenue_min?: number
  revenue_max?: number
  net_profit_min?: number
  net_profit_max?: number
  data_date?: string
}) {
  return http.get<ScreeningResponse>('/stock/screening', { params })
}

export function getLatestDate() {
  return http.get<LatestDateResponse>('/stock/screening/latest-date')
}
