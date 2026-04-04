import http from './http'

export interface FundamentalItem {
  code: string
  name: string | null
  exchange: string | null
  market: string | null
  report_date: string | null
  ann_date: string | null
  revenue: number | null
  net_profit: number | null
  eps: number | null
  bps: number | null
  roe: number | null
  roe_dt: number | null
  roe_waa: number | null
  roa: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_to_assets: number | null
  current_ratio: number | null
  quick_ratio: number | null
  cfps: number | null
  ebit: number | null
  ocf_to_profit: number | null
}

export interface FundamentalResponse {
  items: FundamentalItem[]
  total: number
  page: number
  page_size: number
}

export function getFundamentals(params: {
  page?: number
  page_size?: number
  code?: string
  name?: string
  min_roe?: number
  max_roe?: number
  min_debt_to_assets?: number
  max_debt_to_assets?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}) {
  return http.get<FundamentalResponse>('/fundamental/analysis', { params })
}
