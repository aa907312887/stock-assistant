import http from './http'

// ---------- Types ----------

export interface CreateSessionRequest {
  start_date: string
  initial_cash: number
  name?: string
}

export interface PositionSummary {
  stock_code: string
  stock_name: string | null
  total_quantity: number
  avg_cost_price: number
  current_price: number | null
  market_value: number | null
  profit_loss: number | null
  profit_loss_pct: number | null
  can_sell_quantity: number
}

/** 已清仓：当前对该股已无 holding 批次，曾产生过 closed 批次 */
export interface ClosedStockSummary {
  stock_code: string
  stock_name: string | null
  closed_batch_count: number
  /** 本会话该代码已实现盈亏（元），卖出净入 − 买入净出（含手续费） */
  realized_profit_loss: number
  /** 相对买入总成本的比例，如 0.052 表示 5.2% */
  realized_profit_loss_pct: number
}

export interface SessionResponse {
  session_id: string
  name: string | null
  start_date: string
  current_date: string
  current_phase: 'open' | 'close'
  initial_cash: number
  available_cash: number
  status: string
  positions: PositionSummary[]
  closed_stocks: ClosedStockSummary[]
  total_asset: number
  total_profit_loss: number
  total_profit_loss_pct: number
  created_at: string
  /** 大盘温度对应的交易日：当前模拟日的上一交易日（非模拟当日） */
  market_temp_ref_date: string | null
  market_temp_score: number | null
  market_temp_level: string | null
}

export interface SessionListItem {
  session_id: string
  name: string | null
  start_date: string
  current_date: string
  current_phase: 'open' | 'close'
  initial_cash: number
  available_cash: number
  total_asset: number
  status: string
  created_at: string
}

export interface SessionListResponse {
  total: number
  page: number
  page_size: number
  items: SessionListItem[]
}

export interface PhaseResponse {
  current_date: string
  current_phase: 'open' | 'close'
  available_cash: number
  positions: PositionSummary[]
  closed_stocks: ClosedStockSummary[]
  market_temp_ref_date: string | null
  market_temp_score: number | null
  market_temp_level: string | null
}

export interface NextDayResponse {
  previous_date: string
  current_date: string
  current_phase: 'open' | 'close'
  available_cash: number
  positions: PositionSummary[]
  closed_stocks: ClosedStockSummary[]
  market_temp_ref_date: string | null
  market_temp_score: number | null
  market_temp_level: string | null
}

export interface OrderResponse {
  order_id: number
  order_type: 'buy' | 'sell'
  stock_code: string
  stock_name: string | null
  trade_date: string
  price: number
  quantity: number
  amount: number
  commission: number
  cash_after: number
  /** 订单落库时间（ISO），同一天多笔时区分先后 */
  created_at?: string
}

export interface OrderListResponse {
  total: number
  page: number
  page_size: number
  items: OrderResponse[]
}

export interface ChartBar {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  prev_close: number | null
  pct_change: number | null
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  macd_dif: number | null
  macd_dea: number | null
  macd_hist: number | null
}

export interface ChartDataResponse {
  stock_code: string
  stock_name: string | null
  period: string
  open_price: number | null
  close_price: number | null
  limit_up: number | null
  limit_down: number | null
  data: ChartBar[]
}

export interface StockQuote {
  stock_code: string
  stock_name: string | null
  open: number | null
  close: number | null
  pct_change: number | null
  volume: number | null
  limit_up: number | null
  limit_down: number | null
}

export interface RecommendResponse {
  trade_date: string
  phase: string
  items: StockQuote[]
}

export interface ScreenResponse {
  trade_date: string
  total: number
  page: number
  page_size: number
  items: StockQuote[]
}

export interface TradingDatesResponse {
  dates: string[]
  min_date: string
  max_date: string
}

export interface StockResolveItem {
  stock_code: string
  stock_name: string | null
  /** 后端：stock=个股，index=指数点位标的 */
  instrument_kind?: 'stock' | 'index'
}

export interface StockResolveResponse {
  items: StockResolveItem[]
}

export interface StockInfoBasicBlock {
  stock_code: string
  stock_name: string | null
  exchange: string | null
  market: string | null
  industry_name: string | null
  region: string | null
  list_date: string | null
}

export interface StockInfoDailyBlock {
  trade_date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  prev_close: number | null
  pct_change: number | null
  volume: number | null
  amount: number | null
  amplitude: number | null
  turnover_rate: number | null
  pe_ttm: number | null
  pb: number | null
  total_market_cap: number | null
  float_market_cap: number | null
}

export interface StockInfoFinancialBlock {
  report_date: string
  report_type: string | null
  roe: number | null
  roe_dt: number | null
  debt_to_assets: number | null
  roa: number | null
  gross_margin: number | null
  net_margin: number | null
  revenue: number | null
  net_profit: number | null
  eps: number | null
  bps: number | null
}

export interface PaperStockInfoResponse {
  stock_code: string
  end_date: string
  phase: string
  basic: StockInfoBasicBlock
  daily: StockInfoDailyBlock | null
  financial: StockInfoFinancialBlock | null
}

export interface ScreenParams {
  trade_date: string
  pct_change_min?: number
  pct_change_max?: number
  volume_min?: number
  volume_max?: number
  ma_golden_cross?: string
  macd_golden_cross?: boolean
  page?: number
  page_size?: number
}

// ---------- API ----------

export const paperTradingApi = {
  createSession: (data: CreateSessionRequest) =>
    http.post<SessionResponse>('/paper-trading/sessions', data),

  listSessions: (params?: { status?: string; page?: number; page_size?: number }) =>
    http.get<SessionListResponse>('/paper-trading/sessions', { params }),

  getSession: (sessionId: string) =>
    http.get<SessionResponse>(`/paper-trading/sessions/${sessionId}`),

  advanceToClose: (sessionId: string) =>
    http.post<PhaseResponse>(`/paper-trading/sessions/${sessionId}/advance-to-close`),

  nextDay: (sessionId: string) =>
    http.post<NextDayResponse>(`/paper-trading/sessions/${sessionId}/next-day`),

  endSession: (sessionId: string) =>
    http.post(`/paper-trading/sessions/${sessionId}/end`),

  buy: (sessionId: string, data: { stock_code: string; price: number; quantity: number }) =>
    http.post<OrderResponse>(`/paper-trading/sessions/${sessionId}/buy`, data),

  sell: (sessionId: string, data: { stock_code: string; price: number; quantity: number }) =>
    http.post<OrderResponse>(`/paper-trading/sessions/${sessionId}/sell`, data),

  listOrders: (
    sessionId: string,
    params?: {
      order_type?: string
      stock_code?: string
      page?: number
      page_size?: number
      sort?: 'asc' | 'desc'
    }
  ) => http.get<OrderListResponse>(`/paper-trading/sessions/${sessionId}/orders`, { params }),

  getChartData: (params: {
    stock_code: string
    end_date: string
    phase: string
    period?: string
    /** false 时配合 limit 仅取最近 N 根；默认 true 从库中最早一根取至 end_date */
    full_history?: boolean
    limit?: number
  }) => http.get<ChartDataResponse>('/paper-trading/chart-data', { params }),

  resolveStock: (params: { q: string; limit?: number }) =>
    http.get<StockResolveResponse>('/paper-trading/resolve-stock', { params }),

  getStockInfo: (params: { stock_code: string; end_date: string; phase: string }) =>
    http.get<PaperStockInfoResponse>('/paper-trading/stock-info', { params }),

  recommend: (params: { trade_date: string; phase: string; count?: number }) =>
    http.get<RecommendResponse>('/paper-trading/recommend', { params }),

  screen: (params: ScreenParams) =>
    http.get<ScreenResponse>('/paper-trading/screen', { params }),

  getTradingDates: (params: { start: string; end: string }) =>
    http.get<TradingDatesResponse>('/paper-trading/trading-dates', { params }),
}
