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

/** 区间查询接口返回的快照（与 latest 字段对齐，便于卡片展示） */
export interface MarketTemperatureRangeSnapshot {
  trade_date: string
  temperature_score: number
  temperature_level: MarketTemperatureLatest['temperature_level']
  trend_flag: MarketTemperatureLatest['trend_flag']
  strategy_hint: string
  updated_at: string
  data_status: MarketTemperatureLatest['data_status']
}

export interface MarketTemperatureRangeResponse {
  formula_version: string
  start_date: string
  end_date: string
  trade_day_count: number
  level_styles: MarketTemperatureLatest['level_styles']
  snapshot: MarketTemperatureRangeSnapshot
  points: MarketTemperatureTrendPoint[]
}

export function rangeSnapshotToLatest(resp: MarketTemperatureRangeResponse): MarketTemperatureLatest {
  const s = resp.snapshot
  const td = typeof s.trade_date === 'string' ? s.trade_date : String(s.trade_date)
  const ua = typeof s.updated_at === 'string' ? s.updated_at : String(s.updated_at)
  return {
    trade_date: td,
    temperature_score: s.temperature_score,
    temperature_level: s.temperature_level,
    trend_flag: s.trend_flag,
    strategy_hint: s.strategy_hint,
    updated_at: ua,
    data_status: s.data_status,
    level_styles: resp.level_styles,
  }
}

export async function getMarketTemperatureRange(startDate: string, endDate: string) {
  const res = await http.get<MarketTemperatureRangeResponse>('/market-temperature/range', {
    params: { start_date: startDate, end_date: endDate },
  })
  return res.data
}
