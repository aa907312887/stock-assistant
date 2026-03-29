/**
 * 东方财富个股行情页（全屏 K 线锚点）。
 * 示例：https://quote.eastmoney.com/sz000001.html#fullScreenChart
 */

const HASH = '#fullScreenChart'

function sixDigitFromCode(stockCode: string): string | null {
  const m = stockCode.match(/(\d{6})/)
  return m ? m[1] : null
}

/**
 * @param stockCode 如 000001.SZ、600000.SH
 * @param exchange 可选，StockBasic.exchange：SSE / SZSE / BSE
 */
export function eastMoneyQuoteUrl(stockCode: string, exchange?: string | null): string | null {
  const num = sixDigitFromCode(stockCode)
  if (!num) return null

  const upper = stockCode.toUpperCase()
  let prefix: string | null = null

  if (upper.endsWith('.SZ')) prefix = 'sz'
  else if (upper.endsWith('.SH')) prefix = 'sh'
  else if (upper.endsWith('.BJ')) prefix = 'bj'
  else if (exchange === 'SZSE') prefix = 'sz'
  else if (exchange === 'SSE') prefix = 'sh'
  else if (exchange === 'BSE') prefix = 'bj'
  else {
    if (num.startsWith('688') || num.startsWith('689') || num.startsWith('600') || num.startsWith('601') || num.startsWith('603') || num.startsWith('605')) {
      prefix = 'sh'
    } else if (num.startsWith('000') || num.startsWith('001') || num.startsWith('002') || num.startsWith('003') || num.startsWith('300') || num.startsWith('301')) {
      prefix = 'sz'
    } else if (num.startsWith('8') || num.startsWith('4') || num.startsWith('920')) {
      prefix = 'bj'
    } else {
      prefix = 'sz'
    }
  }

  return `https://quote.eastmoney.com/${prefix}${num}.html${HASH}`
}
