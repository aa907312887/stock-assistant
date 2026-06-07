/** 复利模拟模式 */
export type CompoundMode = 'lump_sum' | 'annual_contribution' | 'annual_then_compound'

/** 单年明细行 */
export interface CompoundYearRow {
  year: number
  opening: number
  contribution: number
  gain: number
  closing: number
  cumulativeInvested: number
  cumulativeGain: number
  /** 每年投入再复利模式：投入期 / 纯复利期 */
  phase?: 'contribute' | 'compound'
}

export interface CompoundSimInput {
  mode: CompoundMode
  /** 一次性投入：首笔金额；每年定期 / 投入期：每年期初金额 */
  principal: number
  /** 年化收益率，如 10 表示 10% */
  annualRatePct: number
  /** 模式 1、2：模拟年数 */
  years?: number
  /** 模式 3：每年投入持续年数 N */
  contributeYears?: number
  /** 模式 3：停止投入后继续复利年数 M */
  compoundYears?: number
}

export interface CompoundSimResult {
  rows: CompoundYearRow[]
  finalBalance: number
  totalInvested: number
  totalGain: number
  totalYears: number
}

function pushYearRow(
  rows: CompoundYearRow[],
  params: {
    year: number
    opening: number
    contribution: number
    gain: number
    closing: number
    cumulativeInvested: number
    phase?: CompoundYearRow['phase']
  },
) {
  rows.push({
    ...params,
    cumulativeGain: params.closing - params.cumulativeInvested,
  })
}

/** 单年：期初 + 本年投入后，按年化 rate 计息一整年 */
function simulateOneYearAnnual(
  opening: number,
  contribution: number,
  rate: number,
): { closing: number; gain: number } {
  const base = opening + contribution
  const gain = base * rate
  return { closing: base + gain, gain }
}

/**
 * 计算复利逐年明细。
 * - 一次性投入：第 1 年期初投入 principal，之后不再追加。
 * - 每年定期投入：每年期初追加 principal，再按年化收益率复利一整年。
 * - 每年投入再复利：连续 N 年每年期初投入 principal，之后 M 年不再投入、仅按年化复利。
 */
export function computeCompoundInterest(input: CompoundSimInput): CompoundSimResult {
  const { mode, principal } = input
  const rate = input.annualRatePct / 100
  const rows: CompoundYearRow[] = []
  let closing = 0
  let cumulativeInvested = 0

  if (mode === 'annual_then_compound') {
    const contributeYears = input.contributeYears ?? 0
    const compoundYears = input.compoundYears ?? 0
    const totalYears = contributeYears + compoundYears

    for (let year = 1; year <= totalYears; year += 1) {
      const opening = closing
      const inContrib = year <= contributeYears
      const contribution = inContrib ? principal : 0
      cumulativeInvested += contribution
      const { closing: yearEnd, gain } = simulateOneYearAnnual(opening, contribution, rate)
      closing = yearEnd
      pushYearRow(rows, {
        year,
        opening,
        contribution,
        gain,
        closing,
        cumulativeInvested,
        phase: inContrib ? 'contribute' : 'compound',
      })
    }

    const last = rows[rows.length - 1]
    return {
      rows,
      finalBalance: last?.closing ?? 0,
      totalInvested: last?.cumulativeInvested ?? 0,
      totalGain: last?.cumulativeGain ?? 0,
      totalYears,
    }
  }

  const years = input.years ?? 0
  for (let year = 1; year <= years; year += 1) {
    const opening = closing
    const contribution = mode === 'lump_sum' ? (year === 1 ? principal : 0) : principal
    cumulativeInvested += contribution
    const { closing: yearEnd, gain } = simulateOneYearAnnual(opening, contribution, rate)
    closing = yearEnd
    pushYearRow(rows, {
      year,
      opening,
      contribution,
      gain,
      closing,
      cumulativeInvested,
    })
  }

  const last = rows[rows.length - 1]
  return {
    rows,
    finalBalance: last?.closing ?? 0,
    totalInvested: last?.cumulativeInvested ?? 0,
    totalGain: last?.cumulativeGain ?? 0,
    totalYears: years,
  }
}
