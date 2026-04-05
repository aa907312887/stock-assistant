<template>
  <div class="simulation-result" v-loading="loadingDetail">
    <!-- 结论横幅 -->
    <el-card v-if="detail?.report" shadow="never" class="conclusion-card" :class="conclusionClass">
      <div class="conclusion-text">{{ detail.report.conclusion }}</div>
    </el-card>

    <!-- 策略逻辑说明 -->
    <el-card v-if="detail?.strategy_description" shadow="never">
      <template #header><div class="section-title">策略逻辑</div></template>
      <pre class="strategy-desc">{{ detail.strategy_description }}</pre>
    </el-card>

    <!-- 核心指标 -->
    <el-card v-if="detail?.report" shadow="never">
      <template #header><div class="section-title">核心指标</div></template>
      <div class="metrics-grid">
        <div class="metric-item">
          <div class="metric-label">总交易数</div>
          <div class="metric-value">{{ detail.report.total_trades }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">盈利笔数</div>
          <div class="metric-value profit">{{ detail.report.win_trades }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">亏损笔数</div>
          <div class="metric-value loss">{{ detail.report.lose_trades }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">胜率</div>
          <div class="metric-value" :class="detail.report.win_rate >= 0.5 ? 'profit' : 'loss'">
            {{ (detail.report.win_rate * 100).toFixed(1) }}%
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">平均收益率</div>
          <div class="metric-value" :class="detail.report.avg_return >= 0 ? 'profit' : 'loss'">
            {{ (detail.report.avg_return * 100).toFixed(2) }}%
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">最大盈利</div>
          <div class="metric-value profit">{{ (detail.report.max_win * 100).toFixed(2) }}%</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">最大亏损</div>
          <div class="metric-value loss">{{ (detail.report.max_loss * 100).toFixed(2) }}%</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">未平仓</div>
          <div class="metric-value">{{ detail.report.unclosed_count }}</div>
        </div>
      </div>
    </el-card>

    <!-- 交易明细 -->
    <el-card v-if="detail?.status === 'completed' || detail?.status === 'incomplete'" shadow="never">
      <template #header>
        <div class="section-header">
          <div class="section-title">交易明细</div>
          <div class="trade-filters">
            <el-select v-model="filterTradeType" placeholder="交易类型" clearable style="width: 130px" size="small">
              <el-option label="已平仓" value="closed" />
              <el-option label="未平仓" value="unclosed" />
            </el-select>
            <el-select
              v-model="filterExchanges"
              multiple collapse-tags collapse-tags-tooltip
              placeholder="交易所" clearable style="width: 160px" size="small"
            >
              <el-option v-for="ex in exchangeOptions" :key="ex" :label="ex" :value="ex" />
            </el-select>
            <el-select
              v-model="filterMarkets"
              multiple collapse-tags collapse-tags-tooltip
              placeholder="板块" clearable style="width: 180px" size="small"
            >
              <el-option v-for="m in marketOptions" :key="m" :label="m" :value="m" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="trades" v-loading="loadingTrades" stripe style="width: 100%">
        <el-table-column width="100">
          <template #header>
            <span>代码</span>
            <el-tooltip content="点击在东方财富打开该股行情（新标签页）" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <a
              v-if="eastMoneyUrl(row)"
              class="code-link"
              :href="eastMoneyUrl(row)!"
              target="_blank"
              rel="noopener noreferrer"
              @click.stop
            >{{ row.stock_code }}</a>
            <span v-else>{{ row.stock_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="stock_name" label="名称" min-width="90" />
        <el-table-column prop="buy_date" label="买入日" width="110" />
        <el-table-column label="买入价" width="90" align="right">
          <template #default="{ row }">{{ row.buy_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="卖出日" width="110">
          <template #default="{ row }">{{ row.sell_date ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="卖出价" width="90" align="right">
          <template #default="{ row }">{{ row.sell_price != null ? row.sell_price.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="收益率" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.return_rate != null" :class="row.return_rate >= 0 ? 'profit' : 'loss'">
              {{ (row.return_rate * 100).toFixed(2) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.trade_type === 'closed' ? 'success' : 'warning'" size="small">
              {{ row.trade_type === 'closed' ? '已平仓' : '未平仓' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="exchange" label="交易所" width="80" />
        <el-table-column prop="market" label="板块" width="90" />
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="tradeTotal"
          layout="total, prev, pager, next"
          @current-change="loadTrades"
        />
      </div>
    </el-card>

    <!-- 运行中 -->
    <el-card v-if="detail?.status === 'running'" shadow="never">
      <div class="running-hint">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>模拟正在后台执行中，请稍候...</span>
      </div>
    </el-card>

    <!-- 失败 -->
    <el-alert
      v-if="detail?.status === 'failed'"
      title="模拟失败"
      type="error"
      show-icon
      :closable="false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, computed } from 'vue'
import { Loading, QuestionFilled } from '@element-plus/icons-vue'
import {
  getSimulationTaskDetail,
  getSimulationTrades,
  type SimulationTaskDetailResponse,
  type SimulationTradeItem,
} from '@/api/simulation'
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const props = defineProps<{ taskId: string }>()

const detail = ref<SimulationTaskDetailResponse | null>(null)
const trades = ref<SimulationTradeItem[]>([])
const loadingDetail = ref(false)
const loadingTrades = ref(false)
const page = ref(1)
const pageSize = 50
const tradeTotal = ref(0)

const filterTradeType = ref<string>('')
const filterExchanges = ref<string[]>([])
const filterMarkets = ref<string[]>([])

let pollTimer: ReturnType<typeof setInterval> | null = null

const conclusionClass = computed(() => {
  if (!detail.value?.report) return ''
  return detail.value.report.avg_return >= 0 ? 'conclusion-positive' : 'conclusion-negative'
})

const exchangeOptions = computed(() => {
  const set = new Set<string>()
  for (const t of trades.value) {
    if (t.exchange) set.add(t.exchange)
  }
  return Array.from(set).sort()
})

const marketOptions = computed(() => {
  const set = new Set<string>()
  for (const t of trades.value) {
    if (t.market) set.add(t.market)
  }
  return Array.from(set).sort()
})

function eastMoneyUrl(row: SimulationTradeItem): string | null {
  return eastMoneyQuoteUrl(row.stock_code, row.exchange)
}

async function loadDetail() {
  loadingDetail.value = true
  try {
    detail.value = await getSimulationTaskDetail(props.taskId)
    if (detail.value.status === 'completed' || detail.value.status === 'incomplete') {
      stopPolling()
      await loadTrades()
    } else if (detail.value.status === 'failed') {
      stopPolling()
    }
  } finally {
    loadingDetail.value = false
  }
}

async function loadTrades() {
  loadingTrades.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize,
    }
    if (filterTradeType.value) params.trade_type = filterTradeType.value
    if (filterExchanges.value.length) params.exchanges = filterExchanges.value.join(',')
    if (filterMarkets.value.length) params.markets = filterMarkets.value.join(',')

    const res = await getSimulationTrades(props.taskId, params as any)
    trades.value = res.items
    tradeTotal.value = res.total
  } finally {
    loadingTrades.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    loadDetail()
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(() => props.taskId, () => {
  page.value = 1
  trades.value = []
  detail.value = null
  loadDetail()
  startPolling()
}, { immediate: true })

watch([filterTradeType, filterExchanges, filterMarkets], () => {
  page.value = 1
  loadTrades()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-result { display: flex; flex-direction: column; gap: 16px; }
.conclusion-card { border-left: 4px solid #909399; }
.conclusion-positive { border-left-color: #f56c6c; }
.conclusion-negative { border-left-color: #67c23a; }
.conclusion-text { font-size: 14px; line-height: 1.6; color: #303133; }
.section-title { font-weight: 600; font-size: 15px; }
.section-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.trade-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.strategy-desc { white-space: pre-wrap; font-family: inherit; font-size: 13px; line-height: 1.7; color: #3b4a5a; margin: 0; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.metric-item { text-align: center; }
.metric-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.metric-value { font-size: 18px; font-weight: 600; color: #303133; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: flex-end; }
.running-hint { display: flex; align-items: center; gap: 8px; color: #909399; font-size: 14px; padding: 20px 0; justify-content: center; }
.code-link { color: var(--el-color-primary); text-decoration: none; }
.code-link:hover { text-decoration: underline; }
.hint-icon-sm { margin-left: 4px; font-size: 12px; color: var(--el-color-info); cursor: help; vertical-align: middle; }
</style>
