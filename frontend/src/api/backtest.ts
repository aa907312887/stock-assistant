import http from './http'

export type RunBacktestRequest = {
  strategy_id: string
  start_date: string
  end_date: string
  /** 持仓金额（元），默认 10 万 */
  position_amount?: number
  /** 补仓金额 / 预备池（元），默认 10 万；可为 0 表示不补仓 */
  reserve_amount?: number
}

export type RunBacktestResponse = {
  task_id: string
  status: string
  message: string
}

export type BacktestTaskItem = {
  task_id: string
  strategy_id: string
  strategy_name: string
  strategy_version: string
  start_date: string
  end_date: string
  status: string
  total_trades: number | null
  win_rate: number | null
  total_return: number | null
  created_at: string
  finished_at: string | null
}

export type BacktestTaskListResponse = {
  total: number
  page: number
  page_size: number
  items: BacktestTaskItem[]
}

export type TempLevelStat = {
  level: string
  total: number
  wins: number
  win_rate: number
  avg_return: number
}

export type PortfolioCapitalOut = {
  position_size: number
  initial_principal: number
  initial_reserve: number
  final_principal: number
  final_reserve: number
  total_wealth_end: number
  total_profit: number
  total_return_on_initial_total: number
  strategy_raw_closed_count: number
  executed_closed_count: number
  skipped_closed_count: number
  same_day_not_traded_count?: number
  before_previous_sell_not_traded_count?: number
  insufficient_funds_not_traded_count?: number
  /** false 表示非恐慌策略：卖出当日不得换股 */
  allow_rebuy_same_day_as_prior_sell?: boolean
  description: string
}

export type BacktestReport = {
  total_trades: number
  win_trades: number
  lose_trades: number
  win_rate: number
  total_return: number
  avg_return: number
  max_win: number
  max_loss: number
  unclosed_count: number
  skipped_count: number
  conclusion: string
  temp_level_stats: TempLevelStat[]
  exchange_stats: { name: string; total: number; wins: number; win_rate: number; avg_return: number }[]
  market_stats: { name: string; total: number; wins: number; win_rate: number; avg_return: number }[]
  portfolio_capital?: PortfolioCapitalOut | null
}

export type BacktestTaskDetailResponse = {
  task_id: string
  strategy_id: string
  strategy_name: string
  strategy_version: string
  start_date: string
  end_date: string
  status: string
  report: BacktestReport | null
  assumptions: Record<string, any> | null
  created_at: string
  finished_at: string | null
}

export type BacktestTradeItem = {
  stock_code: string
  stock_name: string | null
  buy_date: string
  buy_price: number
  sell_date: string | null
  sell_price: number | null
  return_rate: number | null
  trade_type: string
  exchange: string | null
  market: string | null
  market_temp_score: number | null
  market_temp_level: string | null
  extra: Record<string, any> | null
}

export type BacktestTradeListResponse = {
  total: number
  page: number
  page_size: number
  items: BacktestTradeItem[]
}

export type BacktestFilteredMetrics = {
  total_trades: number
  win_trades: number
  lose_trades: number
  win_rate: number
  total_return: number
  avg_return: number
  max_win: number
  max_loss: number
  unclosed_count: number
  matched_count: number
}

export type BacktestFilteredReportResponse = {
  task_id: string
  filters: {
    market_temp_levels: string[]
    markets: string[]
    exchanges: string[]
    year?: number | null
  }
  metrics: BacktestFilteredMetrics
}

export type BacktestBestOptionItem = {
  filters: {
    market_temp_levels: string[]
    markets: string[]
    exchanges: string[]
  }
  metrics: BacktestFilteredMetrics
}

export type BacktestBestOptionsResponse = {
  task_id: string
  best_win_rate: BacktestBestOptionItem
  best_total_return: BacktestBestOptionItem
}

export type BacktestYearlyStatItem = {
  year: number
  matched_count: number
  total_trades: number
  win_trades: number
  lose_trades: number
  win_rate: number
  total_return: number
  avg_return: number
}

export type BacktestYearlyAnalysisResponse = {
  task_id: string
  filters: {
    market_temp_levels: string[]
    markets: string[]
    exchanges: string[]
    year?: number | null
  }
  items: BacktestYearlyStatItem[]
}

export type DataRangeResponse = {
  min_date: string | null
  max_date: string | null
}

export async function runBacktest(payload: RunBacktestRequest) {
  const res = await http.post<RunBacktestResponse>('/backtest/run', payload)
  return res.data
}

export async function getBacktestTasks(params?: {
  strategy_id?: string
  page?: number
  page_size?: number
}) {
  const res = await http.get<BacktestTaskListResponse>('/backtest/tasks', { params })
  return res.data
}

export async function getBacktestTaskDetail(taskId: string) {
  const res = await http.get<BacktestTaskDetailResponse>(`/backtest/tasks/${taskId}`)
  return res.data
}

export async function getBacktestTrades(
  taskId: string,
  params?: {
    trade_type?: string
    market_temp_levels?: string[]
    markets?: string[]
    exchanges?: string[]
    year?: number
    page?: number
    page_size?: number
  },
) {
  const query = {
    ...params,
    market_temp_levels: params?.market_temp_levels?.join(','),
    markets: params?.markets?.join(','),
    exchanges: params?.exchanges?.join(','),
  }
  const res = await http.get<BacktestTradeListResponse>(`/backtest/tasks/${taskId}/trades`, { params: query })
  return res.data
}

export async function getBacktestFilteredReport(
  taskId: string,
  params?: {
    market_temp_levels?: string[]
    markets?: string[]
    exchanges?: string[]
    year?: number
  },
) {
  const query = {
    market_temp_levels: params?.market_temp_levels?.join(','),
    markets: params?.markets?.join(','),
    exchanges: params?.exchanges?.join(','),
    year: params?.year,
  }
  const res = await http.get<BacktestFilteredReportResponse>(
    `/backtest/tasks/${taskId}/filtered-report`,
    { params: query },
  )
  return res.data
}

export async function getBacktestYearlyAnalysis(
  taskId: string,
  params?: {
    market_temp_levels?: string[]
    markets?: string[]
    exchanges?: string[]
    year?: number
  },
) {
  const query = {
    market_temp_levels: params?.market_temp_levels?.join(','),
    markets: params?.markets?.join(','),
    exchanges: params?.exchanges?.join(','),
    year: params?.year,
  }
  const res = await http.get<BacktestYearlyAnalysisResponse>(
    `/backtest/tasks/${taskId}/yearly-analysis`,
    { params: query },
  )
  return res.data
}

export async function getBacktestBestOptions(taskId: string) {
  const res = await http.get<BacktestBestOptionsResponse>(`/backtest/tasks/${taskId}/best-options`)
  return res.data
}

export async function getDataRange() {
  const res = await http.get<DataRangeResponse>('/backtest/data-range')
  return res.data
}
