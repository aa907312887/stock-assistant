import http from './http'

export interface MarketTemperatureLatest {
  trade_date: string
  temperature_score: number
  temperature_level: '极冷' | '偏冷' | '中性' | '偏热' | '过热'
  trend_flag: '升温' | '降温' | '持平'
  strategy_hint: string
  updated_at: string
  data_status: 'normal' | 'stale' | 'failed'
  /** visual_token：后端规则表中的十六进制颜色，如 #1e3a8a */
  level_styles: Array<{ level_name: string; visual_token: string; short_desc: string }>
}

export interface MarketTemperatureTrendPoint {
  trade_date: string
  temperature_score: number
  temperature_level: string
  trend_flag: string
}

export async function getLatestMarketTemperature() {
  const res = await http.get<MarketTemperatureLatest>('/market-temperature/latest')
  return res.data
}

export async function getMarketTemperatureTrend(days = 20) {
  const res = await http.get<{ formula_version: string; points: MarketTemperatureTrendPoint[] }>(
    '/market-temperature/trend',
    { params: { days } },
  )
  return res.data
}

export async function getMarketTemperatureExplain(version?: string) {
  const res = await http.get('/market-temperature/explain', { params: { version } })
  return res.data
}
