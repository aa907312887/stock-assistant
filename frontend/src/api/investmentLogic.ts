import http from './http'

export interface InvestmentLogicEntry {
  id: number
  technical_content: string | null
  fundamental_content: string | null
  message_content: string | null
  weight_technical: number
  weight_fundamental: number
  weight_message: number
  created_at: string
  updated_at: string
  extra_json: Record<string, unknown> | null
}

export interface InvestmentLogicPayload {
  technical_content?: string | null
  fundamental_content?: string | null
  message_content?: string | null
  weight_technical: number
  weight_fundamental: number
  weight_message: number
  extra_json?: Record<string, unknown> | null
}

export function fetchInvestmentLogicCurrent() {
  return http.get<{ entry: InvestmentLogicEntry | null }>('/investment-logic/current')
}

export function fetchInvestmentLogicEntries(order: 'created_desc' | 'created_asc' = 'created_desc') {
  return http.get<{ items: InvestmentLogicEntry[] }>('/investment-logic/entries', {
    params: { order },
  })
}

export function createInvestmentLogicEntry(data: InvestmentLogicPayload) {
  return http.post<InvestmentLogicEntry>('/investment-logic/entries', data)
}

export function updateInvestmentLogicEntry(id: number, data: InvestmentLogicPayload) {
  return http.put<InvestmentLogicEntry>(`/investment-logic/entries/${id}`, data)
}

export function deleteInvestmentLogicEntry(id: number) {
  return http.delete(`/investment-logic/entries/${id}`)
}
