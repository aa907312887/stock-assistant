import http from './http'

export interface StockBasicItem {
  code: string
  name: string | null
  market: string | null
  industry_name: string | null
  region: string | null
  list_date: string | null
  synced_at: string | null
  data_source: string | null
}

export interface StockBasicListResponse {
  items: StockBasicItem[]
  total: number
  page: number
  page_size: number
  last_synced_at: string | null
}

export function getStockBasicList(params: {
  page?: number
  page_size?: number
  code?: string
  name?: string
  market?: string
  industry?: string
}) {
  return http.get<StockBasicListResponse>('/stock/basic', { params })
}

/** 全市场列表同步可能较慢，单独放宽超时（毫秒）。 */
const SYNC_TIMEOUT_MS = 600_000

export function postStockBasicSync() {
  return http.post<{ status: string; message: string; stock_basic: number }>(
    '/stock/basic/sync',
    {},
    { timeout: SYNC_TIMEOUT_MS }
  )
}
