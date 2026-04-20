import http from './http'
import type { LatestDateResponse, ScreeningItem, ScreeningTimeframe } from './stock'

/** 与综合选股列表字段一致；instrument_type 由后端设为 index */
export type IndexScreeningItem = ScreeningItem & { instrument_type?: 'index' }

export type { ScreeningTimeframe }

export interface IndexScreeningResponse {
  items: IndexScreeningItem[]
  total: number
  page: number
  page_size: number
  timeframe: ScreeningTimeframe
  data_date: string | null
}

export function getIndexScreening(params: {
  page?: number
  page_size?: number
  code?: string
  name?: string
  ma_bull?: boolean
  macd_red?: boolean
  ma_cross?: boolean
  macd_cross?: boolean
  timeframe?: ScreeningTimeframe
  data_date?: string
}) {
  return http.get<IndexScreeningResponse>('/index/screening', { params })
}

export function getIndexLatestDate(params?: { timeframe?: ScreeningTimeframe }) {
  return http.get<LatestDateResponse>('/index/screening/latest-date', { params })
}

export interface CompositionPeMeta {
  formula: string
  participating_weight_ratio: number | null
  constituents_total: number
  constituents_with_pe: number
}

export interface CompositionConstituentItem {
  con_code: string
  weight: number | null
  pe_percentile: number | null
}

export interface CompositionResponse {
  ts_code: string
  weight_table_date: string | null
  snapshot_trade_date: string | null
  index_pe_percentile: number | null
  pe_percentile_meta: CompositionPeMeta | null
  items: CompositionConstituentItem[]
  message: string | null
}

export function getIndexComposition(tsCode: string, params?: { trade_date?: string; weight_as_of?: string }) {
  return http.get<CompositionResponse>(`/index/${encodeURIComponent(tsCode)}/composition`, { params })
}
