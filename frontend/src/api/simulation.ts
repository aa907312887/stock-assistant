import http from './http'

// ---------- Types ----------

export interface RunSimulationRequest {
  strategy_id: string
  start_date: string
  end_date: string
}

export interface RunSimulationResponse {
  task_id: string
  status: string
  message: string
}

export interface SimulationTaskItem {
  task_id: string
  strategy_id: string
  strategy_name: string
  strategy_version: string
  start_date: string
  end_date: string
  status: string
  total_trades: number | null
  win_trades: number | null
  win_rate: number | null
  avg_return: number | null
  created_at: string
  finished_at: string | null
}

export interface SimulationTaskListResponse {
  total: number
  page: number
  page_size: number
  items: SimulationTaskItem[]
}

export interface SimulationReport {
  total_trades: number
  win_trades: number
  lose_trades: number
  win_rate: number
  avg_return: number
  max_win: number
  max_loss: number
  unclosed_count: number
  skipped_count: number
  conclusion: string
}

export interface SimulationTaskDetailResponse {
  task_id: string
  strategy_id: string
  strategy_name: string
  strategy_version: string
  start_date: string
  end_date: string
  status: string
  report: SimulationReport | null
  assumptions: Record<string, unknown> | null
  created_at: string
  finished_at: string | null
  strategy_description: string | null
}

export interface SimulationTradeItem {
  id: number
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
  extra: Record<string, unknown> | null
}

export interface SimulationTradeListResponse {
  total: number
  page: number
  page_size: number
  items: SimulationTradeItem[]
}

// ---------- API Functions ----------

export async function runSimulation(payload: RunSimulationRequest): Promise<RunSimulationResponse> {
  const { data } = await http.post('/simulation/run', payload)
  return data
}

export async function getSimulationTasks(params?: {
  strategy_id?: string
  page?: number
  page_size?: number
}): Promise<SimulationTaskListResponse> {
  const { data } = await http.get('/simulation/tasks', { params })
  return data
}

export async function getSimulationTaskDetail(taskId: string): Promise<SimulationTaskDetailResponse> {
  const { data } = await http.get(`/simulation/tasks/${taskId}`)
  return data
}

export async function getSimulationTrades(
  taskId: string,
  params?: {
    trade_type?: string
    exchanges?: string
    markets?: string
    page?: number
    page_size?: number
  },
): Promise<SimulationTradeListResponse> {
  const { data } = await http.get(`/simulation/tasks/${taskId}/trades`, { params })
  return data
}
