import http from './http'

export interface OpenTradeItem {
  trade_id: number
  stock_code: string
  stock_name: string | null
  total_qty: number | null
  avg_cost: number | null
  ref_close: number | null
  ref_close_date: string | null
  ref_market_value: number | null
  ref_pnl: number | null
  ref_pnl_pct: number | null
  has_ref_price: boolean
}

export interface ClosedTradeItem {
  trade_id: number
  stock_code: string
  stock_name: string | null
  closed_at: string | null
  realized_pnl: number | null
  realized_pnl_rate: number | null
  review_text: string | null
  image_count: number
}

export interface OperationOut {
  id: number
  op_type: string
  op_date: string
  qty: number
  price: number
  operation_rating: string | null
  note: string | null
}

export interface TradeDetail {
  trade: {
    id: number
    stock_code: string
    stock_name: string | null
    status: string
    opened_at: string | null
    closed_at: string | null
    avg_cost: number | null
    total_qty: number | null
    realized_pnl: number | null
    realized_pnl_rate: number | null
    review_text: string | null
  }
  operations: OperationOut[]
  images: { id: number; url: string }[]
}

export interface StatsResponse {
  stock_win_rate: {
    won: number
    lost: number
    breakeven: number
    total: number
    rate: number | null
  }
  operation_win_rate: {
    good: number
    bad: number
    unrated: number
    rated_total: number
    rate: number | null
  }
  overall_pnl: {
    total_profit: number
    total_loss: number
    net_pnl: number
    net_pnl_rate: number | null
  }
}

export function getOpenTrades() {
  return http.get<{ items: OpenTradeItem[] }>('/portfolio/open-trades')
}

export function openTrade(data: {
  stock_code: string
  op_date: string
  qty: number
  price: number
  fee?: number
}) {
  return http.post<{ trade_id: number; operation_id: number }>('/portfolio/trades/open', data)
}

export function addOperation(
  tradeId: number,
  data: {
    op_type: 'add' | 'reduce'
    op_date: string
    qty: number
    price: number
    fee?: number
    operation_rating?: string | null
    note?: string | null
  }
) {
  return http.post<{ operation_id: number }>(`/portfolio/trades/${tradeId}/operations`, data)
}

export function closeTrade(
  tradeId: number,
  data: {
    op_date: string
    qty: number
    price: number
    fee?: number
    operation_rating?: string | null
    note?: string | null
  }
) {
  return http.post<{ trade_id: number; realized_pnl: number | null }>(
    `/portfolio/trades/${tradeId}/close`,
    data
  )
}

export function deleteOpenTrade(tradeId: number) {
  return http.delete(`/portfolio/trades/${tradeId}`)
}

export function getClosedTrades(params?: { page?: number; page_size?: number; stock_code?: string }) {
  return http.get<{ total: number; items: ClosedTradeItem[] }>('/portfolio/closed-trades', { params })
}

export function getTradeDetail(tradeId: number) {
  return http.get<TradeDetail>(`/portfolio/trades/${tradeId}`)
}

export function patchReview(tradeId: number, review_text: string | null) {
  return http.patch(`/portfolio/trades/${tradeId}/review`, { review_text })
}

export function uploadReviewImage(tradeId: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post<{ image_id: number; url: string }>(`/portfolio/trades/${tradeId}/images`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteReviewImage(imageId: number) {
  return http.delete(`/portfolio/images/${imageId}`)
}

export function patchOperationRating(operationId: number, operation_rating: 'good' | 'bad' | null) {
  return http.patch(`/portfolio/operations/${operationId}/rating`, { operation_rating })
}

export function getStats(params?: { from_date?: string; to_date?: string }) {
  return http.get<StatsResponse>('/portfolio/stats', { params })
}

/** 拉取图片为 blob，用于需 Authorization 的预览 */
export async function fetchImageBlob(imageId: number): Promise<string> {
  const res = await http.get(`/portfolio/images/${imageId}/file`, { responseType: 'blob' })
  return URL.createObjectURL(res.data as Blob)
}
