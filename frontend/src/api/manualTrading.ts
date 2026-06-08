import http from './http'

export interface CreateSessionRequest {
  asset_name: string
  start_date: string
  name?: string
}

export interface SessionListItem {
  session_id: string
  name: string | null
  asset_name: string
  start_date: string
  current_date: string
  position_value: number
  total_invested: number
  total_pnl: number
  status: string
  awaiting_reval: boolean
  created_at: string
}

export interface SessionListResponse {
  total: number
  page: number
  page_size: number
  items: SessionListItem[]
}

export interface SessionDetail {
  session_id: string
  name: string | null
  asset_name: string
  start_date: string
  current_date: string
  reference_price: number | null
  position_value: number
  total_invested: number
  total_pnl: number
  total_pnl_pct: number | null
  total_trading_days: number | null
  status: string
  awaiting_reval: boolean
  end_date: string | null
  first_operation_date: string | null
  created_at: string
  updated_at: string
}

export interface AdvanceResponse {
  session_id: string
  current_date: string
  awaiting_reval: boolean
  step: string
}

export interface OperationItem {
  id: number
  op_type: string
  op_type_label: string
  op_date: string
  price: number | null
  buy_amount: number | null
  advance_step: string | null
  position_before: number
  position_after: number
  segment_pnl: number | null
  days_since_prev: number | null
}

export interface OperationsResponse {
  session_id: string
  total_pnl: number
  total_trading_days: number | null
  items: OperationItem[]
}

export type AdvanceStep = 'day' | 'week' | 'month' | 'year'

export async function createSession(body: CreateSessionRequest): Promise<SessionDetail> {
  const { data } = await http.post<SessionDetail>('/manual-trading/sessions', body)
  return data
}

export async function listSessions(params?: {
  status?: string
  page?: number
  page_size?: number
}): Promise<SessionListResponse> {
  const { data } = await http.get<SessionListResponse>('/manual-trading/sessions', { params })
  return data
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const { data } = await http.get<SessionDetail>(`/manual-trading/sessions/${sessionId}`)
  return data
}

export async function deleteSession(sessionId: string): Promise<void> {
  await http.delete(`/manual-trading/sessions/${sessionId}`)
}

export async function buySession(
  sessionId: string,
  amount: number,
  price: number,
): Promise<SessionDetail> {
  const { data } = await http.post<SessionDetail>(`/manual-trading/sessions/${sessionId}/buy`, {
    amount,
    price,
  })
  return data
}

export async function advanceSession(
  sessionId: string,
  step: AdvanceStep,
): Promise<AdvanceResponse> {
  const { data } = await http.post<AdvanceResponse>(
    `/manual-trading/sessions/${sessionId}/advance`,
    { step },
  )
  return data
}

export async function revalSession(sessionId: string, closePrice: number): Promise<SessionDetail> {
  const { data } = await http.post<SessionDetail>(`/manual-trading/sessions/${sessionId}/reval`, {
    close_price: closePrice,
  })
  return data
}

export async function endSession(sessionId: string): Promise<SessionDetail> {
  const { data } = await http.post<SessionDetail>(`/manual-trading/sessions/${sessionId}/end`)
  return data
}

export async function listOperations(sessionId: string): Promise<OperationsResponse> {
  const { data } = await http.get<OperationsResponse>(
    `/manual-trading/sessions/${sessionId}/operations`,
  )
  return data
}
