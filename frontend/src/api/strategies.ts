import axios from 'axios'

export type StrategySummary = {
  strategy_id: string
  name: string
  version: string
  short_description: string
  route_path: string
}

export type ListStrategiesResponse = {
  items: StrategySummary[]
}

export type GetStrategyResponse = {
  strategy_id: string
  name: string
  version: string
  description: string
  assumptions: string[]
  risks: string[]
}

export type ExecuteStrategyRequest = {
  as_of_date?: string
}

export type ExecutionSnapshot = {
  execution_id: string
  strategy_id: string
  strategy_version: string
  market: 'A股'
  as_of_date: string
  timeframe: 'daily'
  assumptions: Record<string, any>
}

export type StrategySelectionItem = {
  stock_code: string
  stock_name?: string | null
  /** 交易所 SSE/SZSE/BSE */
  exchange?: string | null
  /** 板块：主板/创业板等；空为 null 或 '' */
  market?: string | null
  /** 兼容旧页展示 */
  exchange_type?: string | null
  trigger_date: string
  summary: Record<string, any>
}

export type SignalEvent = {
  stock_code: string
  event_date: string
  event_type: 'trigger' | 'entry' | 'exit' | 'filter' | 'note'
  payload: Record<string, any>
}

export type ExecuteStrategyResponse = {
  execution: ExecutionSnapshot
  items: StrategySelectionItem[]
  signals: SignalEvent[]
}

export async function listStrategies() {
  const res = await axios.get<ListStrategiesResponse>('/api/strategies')
  return res.data
}

export async function getStrategy(strategyId: string) {
  const res = await axios.get<GetStrategyResponse>(`/api/strategies/${strategyId}`)
  return res.data
}

export async function executeStrategy(strategyId: string, payload?: ExecuteStrategyRequest) {
  const res = await axios.post<ExecuteStrategyResponse>(`/api/strategies/${strategyId}/execute`, payload ?? {})
  return res.data
}

export async function getLatestStrategyResult(strategyId: string, params?: { as_of_date?: string }) {
  const res = await axios.get<ExecuteStrategyResponse>(`/api/strategies/${strategyId}/latest`, { params })
  return res.data
}

