import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { paperTradingApi } from '@/api/paperTrading'
import type {
  SessionResponse,
  SessionListItem,
  ChartDataResponse,
  StockQuote,
  ScreenParams,
} from '@/api/paperTrading'

export const usePaperTradingStore = defineStore('paperTrading', () => {
  // ---------- 状态 ----------
  const currentSession = ref<SessionResponse | null>(null)
  const sessionList = ref<SessionListItem[]>([])
  const chartData = ref<ChartDataResponse | null>(null)
  const recommendList = ref<StockQuote[]>([])
  const screenResult = ref<{ total: number; items: StockQuote[] }>({ total: 0, items: [] })
  const loading = ref(false)
  const chartLoading = ref(false)

  // ---------- Getters ----------
  const isOpenPhase = computed(() => currentSession.value?.current_phase === 'open')
  const isClosePhase = computed(() => currentSession.value?.current_phase === 'close')
  const canNextDay = computed(() => currentSession.value?.current_phase === 'close')
  /**
   * 是否可进行买卖、推进等写操作。
   * 仅当服务端明确返回 ended 时视为已结束；status 为空或缺失时按进行中处理（兼容旧数据或未写字段）。
   */
  const isSessionActive = computed(() => {
    const s = (currentSession.value?.status ?? '').toString().trim().toLowerCase()
    return s !== 'ended'
  })

  // ---------- Actions ----------

  async function loadSession(sessionId: string) {
    loading.value = true
    try {
      const res = await paperTradingApi.getSession(sessionId)
      currentSession.value = {
        ...res.data,
        closed_stocks: (res.data.closed_stocks ?? []).map((c) => ({
          ...c,
          realized_profit_loss: c.realized_profit_loss ?? 0,
          realized_profit_loss_pct: c.realized_profit_loss_pct ?? 0,
        })),
      }
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '加载会话失败')
    } finally {
      loading.value = false
    }
  }

  async function loadSessionList(status?: string) {
    const res = await paperTradingApi.listSessions({ status, page_size: 50 })
    sessionList.value = res.data.items
  }

  async function advanceToClose() {
    if (!currentSession.value) return
    loading.value = true
    try {
      const res = await paperTradingApi.advanceToClose(currentSession.value.session_id)
      // 更新会话 phase 和持仓
      currentSession.value = {
        ...currentSession.value,
        current_phase: res.data.current_phase,
        available_cash: res.data.available_cash,
        positions: res.data.positions,
        closed_stocks: (res.data.closed_stocks ?? []).map((c) => ({
          ...c,
          realized_profit_loss: c.realized_profit_loss ?? 0,
          realized_profit_loss_pct: c.realized_profit_loss_pct ?? 0,
        })),
        market_temp_ref_date: res.data.market_temp_ref_date ?? null,
        market_temp_score: res.data.market_temp_score ?? null,
        market_temp_level: res.data.market_temp_level ?? null,
      }
      ElMessage.success('已推进到收盘')
      // 刷新图表（补全当日 K 线）
      if (chartData.value) {
        await loadChartData(chartData.value.stock_code)
      }
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '操作失败')
    } finally {
      loading.value = false
    }
  }

  async function nextDay() {
    if (!currentSession.value) return
    loading.value = true
    try {
      const res = await paperTradingApi.nextDay(currentSession.value.session_id)
      currentSession.value = {
        ...currentSession.value,
        current_date: res.data.current_date,
        current_phase: res.data.current_phase,
        available_cash: res.data.available_cash,
        positions: res.data.positions,
        closed_stocks: (res.data.closed_stocks ?? []).map((c) => ({
          ...c,
          realized_profit_loss: c.realized_profit_loss ?? 0,
          realized_profit_loss_pct: c.realized_profit_loss_pct ?? 0,
        })),
        market_temp_ref_date: res.data.market_temp_ref_date ?? null,
        market_temp_score: res.data.market_temp_score ?? null,
        market_temp_level: res.data.market_temp_level ?? null,
      }
      ElMessage.success(`已进入 ${res.data.current_date} 开盘`)
      // 刷新推荐和图表
      await loadRecommend()
      if (chartData.value) {
        await loadChartData(chartData.value.stock_code)
      }
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '操作失败')
    } finally {
      loading.value = false
    }
  }

  async function buyStock(stockCode: string, price: number, quantity: number) {
    if (!currentSession.value) return
    try {
      await paperTradingApi.buy(currentSession.value.session_id, { stock_code: stockCode, price, quantity })
      ElMessage.success('买入成功')
      await loadSession(currentSession.value.session_id)
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '买入失败')
      throw e
    }
  }

  async function sellStock(stockCode: string, price: number, quantity: number) {
    if (!currentSession.value) return
    try {
      await paperTradingApi.sell(currentSession.value.session_id, { stock_code: stockCode, price, quantity })
      ElMessage.success('卖出成功')
      await loadSession(currentSession.value.session_id)
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '卖出失败')
      throw e
    }
  }

  async function loadChartData(stockCode: string, period = 'daily') {
    if (!currentSession.value) return
    chartLoading.value = true
    try {
      const res = await paperTradingApi.getChartData({
        stock_code: stockCode,
        end_date: currentSession.value.current_date,
        phase: currentSession.value.current_phase,
        period,
        full_history: true,
      })
      chartData.value = res.data
    } catch (e: any) {
      ElMessage.error('图表数据加载失败')
    } finally {
      chartLoading.value = false
    }
  }

  async function loadRecommend() {
    if (!currentSession.value) return
    try {
      const res = await paperTradingApi.recommend({
        trade_date: currentSession.value.current_date,
        phase: currentSession.value.current_phase,
        count: 10,
      })
      recommendList.value = res.data.items
    } catch (e: any) {
      ElMessage.error('推荐股票加载失败')
    }
  }

  async function screenStocks(params: Omit<ScreenParams, 'trade_date'> & { page?: number }) {
    if (!currentSession.value) return
    try {
      const res = await paperTradingApi.screen({
        trade_date: currentSession.value.current_date,
        ...params,
      })
      screenResult.value = { total: res.data.total, items: res.data.items }
    } catch (e: any) {
      ElMessage.error('筛选失败')
    }
  }

  async function endSession() {
    if (!currentSession.value) {
      throw new Error('会话不存在')
    }
    try {
      await paperTradingApi.endSession(currentSession.value.session_id)
      ElMessage.success('会话已结束')
      currentSession.value = null
      await loadSessionList()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail?.message || '结束失败')
      throw e
    }
  }

  return {
    currentSession,
    sessionList,
    chartData,
    recommendList,
    screenResult,
    loading,
    chartLoading,
    isOpenPhase,
    isClosePhase,
    canNextDay,
    isSessionActive,
    loadSession,
    loadSessionList,
    advanceToClose,
    nextDay,
    buyStock,
    sellStock,
    loadChartData,
    loadRecommend,
    screenStocks,
    endSession,
  }
})
