import http from './http'

export type RunBacktestRequest = {
  strategy_id: string
  start_date: string
  end_date: string
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
    market_temp_level?: string
    market?: string
    exchange?: string
    page?: number
    page_size?: number
  },
) {
  const res = await http.get<BacktestTradeListResponse>(`/backtest/tasks/${taskId}/trades`, { params })
  return res.data
}

export async function getDataRange() {
  const res = await http.get<DataRangeResponse>('/backtest/data-range')
  return res.data
}
