<template>
  <div class="simulation-result" v-loading="loadingDetail">
    <el-card v-if="detail?.report" shadow="never" class="conclusion-card" :class="conclusionClass">
      <template #header>
        <div class="card-header-row">
          <span class="section-title">模拟结论</span>
          <el-tooltip placement="top">
            <template #content>
              <div style="max-width: 340px">
                历史模拟<strong>不进行资金/仓位仿真</strong>，凡符合策略的已平仓样本均统计；笔数通常多于同区间历史回测的「实际成交」笔数（回测含同日仅一笔、资金不足跳过等规则）。筛选与分年口径与历史回测分析一致。
              </div>
            </template>
            <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
      </template>
      <div class="conclusion-text">{{ detail.report.conclusion }}</div>
    </el-card>

    <el-card v-if="detail?.strategy_description" shadow="never">
      <template #header><div class="section-title">策略逻辑</div></template>
      <pre class="strategy-desc">{{ detail.strategy_description }}</pre>
    </el-card>

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

    <template v-if="detail?.report && (detail.report.temp_level_stats?.length || detail.report.exchange_stats?.length || detail.report.market_stats?.length)">
      <el-card v-if="(detail.report.temp_level_stats?.length ?? 0) > 0" shadow="never">
        <template #header>
          <div class="section-title">
            大盘温度分组统计
            <el-tooltip content="展示策略在不同大盘温度级别下的表现差异" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-table :data="detail.report.temp_level_stats" stripe size="small">
          <el-table-column prop="level" label="温度级别" width="100" />
          <el-table-column prop="total" label="交易数" width="80" align="right" />
          <el-table-column label="胜率" width="90" align="right">
            <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="平均收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="(detail.report.exchange_stats?.length ?? 0) > 0" shadow="never">
        <template #header>
          <div class="section-title">
            交易所分组统计
            <el-tooltip content="按 SSE/SZSE/BSE 分组，展示交易次数、胜率与平均收益" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-table :data="detail.report.exchange_stats" stripe size="small">
          <el-table-column prop="name" label="交易所" width="120" />
          <el-table-column prop="total" label="交易数" width="80" align="right" />
          <el-table-column label="胜率" width="90" align="right">
            <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="平均收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="(detail.report.market_stats?.length ?? 0) > 0" shadow="never">
        <template #header>
          <div class="section-title">
            板块分组统计
            <el-tooltip content="按主板/创业板/科创板等板块分组，展示交易次数、胜率与平均收益" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-table :data="detail.report.market_stats" stripe size="small">
          <el-table-column prop="name" label="板块" width="120" />
          <el-table-column prop="total" label="交易数" width="80" align="right" />
          <el-table-column label="胜率" width="90" align="right">
            <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="平均收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-card v-if="detail?.status === 'completed' || detail?.status === 'incomplete'" shadow="never">
      <template #header>
        <div class="section-header">
          <div class="section-title">交易明细</div>
          <div class="trade-filters">
            <el-select
              v-model="tradeFilters.tradeStatus"
              clearable
              placeholder="交易类型"
              style="width: 130px"
              size="small"
            >
              <el-option label="已平仓" value="closed" />
              <el-option label="未平仓" value="unclosed" />
            </el-select>
            <el-select
              v-model="tradeFilters.exchanges"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="交易所"
              clearable
              style="width: 160px"
              size="small"
            >
              <el-option v-for="ex in exchangeFilterOptions" :key="ex.value" :label="ex.label" :value="ex.value" />
            </el-select>
            <el-select
              v-model="tradeFilters.market_temp_levels"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="大盘温度"
              clearable
              style="width: 160px"
              size="small"
            >
              <el-option v-for="lvl in tempLevelOptions" :key="lvl" :label="lvl" :value="lvl" />
            </el-select>
            <el-select
              v-model="tradeFilters.markets"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="板块"
              clearable
              style="width: 180px"
              size="small"
            >
              <el-option
                v-for="m in marketFilterOptions"
                :key="m"
                :label="m === '__EMPTY__' ? '空板块（北交所等）' : m"
                :value="m"
              />
            </el-select>
            <el-select
              v-model="tradeFilters.tradeYear"
              clearable
              placeholder="买入年份"
              style="width: 120px"
              size="small"
            >
              <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
            </el-select>
            <el-button size="small" type="primary" @click="handleTradeFilterSearch">筛选</el-button>
            <el-button size="small" @click="handleTradeFilterReset">重置</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="filteredMetrics"
        type="info"
        :closable="false"
        class="filtered-summary"
        show-icon
      >
        <template #title>
          条件交叉验证：匹配 {{ filteredMetrics.matched_count }} 笔（已平仓 {{ filteredMetrics.total_trades }} 笔），
          胜率 {{ (filteredMetrics.win_rate * 100).toFixed(1) }}%，
          总收益 {{ filteredMetrics.total_return >= 0 ? '+' : '' }}{{ (filteredMetrics.total_return * 100).toFixed(2) }}%，
          平均收益 {{ filteredMetrics.avg_return >= 0 ? '+' : '' }}{{ (filteredMetrics.avg_return * 100).toFixed(2) }}%
        </template>
      </el-alert>

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
        <el-table-column label="温度" width="72">
          <template #default="{ row }">{{ row.market_temp_level ?? '-' }}</template>
        </el-table-column>
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

      <div class="yearly-section">
        <h4 class="section-title">
          分年度分析
          <el-tooltip placement="top">
            <template #content>
              <div style="max-width: 320px">
                按买入日自然年汇总；与上方筛选条件一致（AND）。胜率与总收益仅基于已平仓；匹配笔数含未平仓。
              </div>
            </template>
            <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
          </el-tooltip>
        </h4>
        <el-table :data="yearlyItems" stripe size="small" v-loading="yearlyLoading" empty-text="当前筛选下无数据">
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column prop="matched_count" label="匹配笔数" width="90" align="right" />
          <el-table-column prop="total_trades" label="已平仓" width="80" align="right" />
          <el-table-column label="胜率" width="90" align="right">
            <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="总收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.total_return >= 0 ? 'profit' : 'loss'">
                {{ row.total_return >= 0 ? '+' : '' }}{{ (row.total_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="平均收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-card v-if="detail?.status === 'running'" shadow="never">
      <div class="running-hint">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>模拟正在后台执行中，请稍候...</span>
      </div>
    </el-card>

    <el-alert
      v-if="detail?.status === 'failed'"
      title="模拟失败"
      type="error"
      show-icon
      :closable="false"
    />

    <div v-if="detail?.assumptions && Object.keys(detail.assumptions).length" class="assumptions-block">
      <h4 class="section-title">口径与假设</h4>
      <div class="assumption-tags">
        <el-tag
          v-for="(val, key) in detail.assumptions"
          :key="String(key)"
          type="info"
          size="small"
          class="assumption-tag"
        >
          {{ key }}: {{ val }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, computed } from 'vue'
import { Loading, QuestionFilled } from '@element-plus/icons-vue'
import {
  getSimulationTaskDetail,
  getSimulationTrades,
  getSimulationFilteredReport,
  getSimulationYearlyAnalysis,
  type SimulationTaskDetailResponse,
  type SimulationTradeItem,
  type BacktestFilteredMetrics,
  type BacktestYearlyStatItem,
} from '@/api/simulation'
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const props = defineProps<{ taskId: string }>()

const detail = ref<SimulationTaskDetailResponse | null>(null)
const trades = ref<SimulationTradeItem[]>([])
const loadingDetail = ref(false)
const loadingTrades = ref(false)
const yearlyLoading = ref(false)
const page = ref(1)
const pageSize = 50
const tradeTotal = ref(0)
const filteredMetrics = ref<BacktestFilteredMetrics | null>(null)
const yearlyItems = ref<BacktestYearlyStatItem[]>([])

const tradeFilters = ref<{
  tradeStatus: string | undefined
  exchanges: string[]
  market_temp_levels: string[]
  markets: string[]
  tradeYear: number | undefined
}>({
  tradeStatus: undefined,
  exchanges: [],
  market_temp_levels: [],
  markets: [],
  tradeYear: undefined,
})

let pollTimer: ReturnType<typeof setInterval> | null = null

const conclusionClass = computed(() => {
  if (!detail.value?.report) return ''
  return detail.value.report.avg_return >= 0 ? 'conclusion-positive' : 'conclusion-negative'
})

const tempLevelOptions = computed(() => {
  const levels = detail.value?.report?.temp_level_stats?.map((x) => x.level) ?? []
  return levels.filter(Boolean)
})

const marketFilterOptions = computed(() => {
  const markets = detail.value?.report?.market_stats?.map((x) => x.name).filter(Boolean) ?? []
  return ['__EMPTY__', ...markets]
})

const exchangeFilterOptions = computed(() => {
  const exchanges = detail.value?.report?.exchange_stats?.map((x) => x.name).filter(Boolean) ?? []
  return exchanges.map((v) => ({
    value: v,
    label: v === 'SSE' ? '上交所(SSE)' : v === 'SZSE' ? '深交所(SZSE)' : v === 'BSE' ? '北交所(BSE)' : v,
  }))
})

const yearOptions = computed(() => {
  const d = detail.value
  if (!d) return []
  const y0 = parseInt(d.start_date.slice(0, 4), 10)
  const y1 = parseInt(d.end_date.slice(0, 4), 10)
  if (Number.isNaN(y0) || Number.isNaN(y1)) return []
  const list: number[] = []
  for (let y = y0; y <= y1; y += 1) list.push(y)
  return list
})

function eastMoneyUrl(row: SimulationTradeItem): string | null {
  return eastMoneyQuoteUrl(row.stock_code, row.exchange)
}

function tradeTypeQueryParam(): { trade_type?: string } {
  const t = tradeFilters.value.tradeStatus
  return t ? { trade_type: t } : {}
}

async function loadDetail() {
  loadingDetail.value = true
  try {
    detail.value = await getSimulationTaskDetail(props.taskId)
    if (detail.value.status === 'completed' || detail.value.status === 'incomplete') {
      stopPolling()
      page.value = 1
      await loadTrades()
      await loadFilteredMetrics()
      await loadYearlyAnalysis()
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
    const res = await getSimulationTrades(props.taskId, {
      ...tradeTypeQueryParam(),
      market_temp_levels: tradeFilters.value.market_temp_levels.join(','),
      markets: tradeFilters.value.markets.join(','),
      exchanges: tradeFilters.value.exchanges.join(','),
      year: tradeFilters.value.tradeYear,
      page: page.value,
      page_size: pageSize,
    })
    trades.value = res.items
    tradeTotal.value = res.total
  } finally {
    loadingTrades.value = false
  }
}

async function loadFilteredMetrics() {
  const res = await getSimulationFilteredReport(props.taskId, {
    ...tradeTypeQueryParam(),
    market_temp_levels: tradeFilters.value.market_temp_levels,
    markets: tradeFilters.value.markets,
    exchanges: tradeFilters.value.exchanges,
    year: tradeFilters.value.tradeYear,
  })
  filteredMetrics.value = res.metrics
}

async function loadYearlyAnalysis() {
  yearlyLoading.value = true
  try {
    const res = await getSimulationYearlyAnalysis(props.taskId, {
      ...tradeTypeQueryParam(),
      market_temp_levels: tradeFilters.value.market_temp_levels,
      markets: tradeFilters.value.markets,
      exchanges: tradeFilters.value.exchanges,
      year: tradeFilters.value.tradeYear,
    })
    yearlyItems.value = res.items
  } finally {
    yearlyLoading.value = false
  }
}

function handleTradeFilterSearch() {
  page.value = 1
  void loadTrades()
  void loadFilteredMetrics()
  void loadYearlyAnalysis()
}

function handleTradeFilterReset() {
  tradeFilters.value = {
    tradeStatus: undefined,
    exchanges: [],
    market_temp_levels: [],
    markets: [],
    tradeYear: undefined,
  }
  page.value = 1
  void loadTrades()
  void loadFilteredMetrics()
  void loadYearlyAnalysis()
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    void loadDetail()
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
  filteredMetrics.value = null
  yearlyItems.value = []
  void loadDetail()
  startPolling()
}, { immediate: true })

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-result { display: flex; flex-direction: column; gap: 16px; }
.card-header-row { display: flex; align-items: center; gap: 8px; }
.conclusion-card { border-left: 4px solid #909399; }
.conclusion-positive { border-left-color: #f56c6c; }
.conclusion-negative { border-left-color: #67c23a; }
.conclusion-text { font-size: 14px; line-height: 1.6; color: #303133; }
.section-title { font-weight: 600; font-size: 15px; }
.section-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.trade-filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.strategy-desc { white-space: pre-wrap; font-family: inherit; font-size: 13px; line-height: 1.7; color: #3b4a5a; margin: 0; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.metric-item { text-align: center; }
.metric-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.metric-value { font-size: 18px; font-weight: 600; color: #303133; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: flex-end; }
.filtered-summary { margin-bottom: 12px; }
.yearly-section { margin-top: 20px; }
.running-hint { display: flex; align-items: center; gap: 8px; color: #909399; font-size: 14px; padding: 20px 0; justify-content: center; }
.code-link { color: var(--el-color-primary); text-decoration: none; }
.code-link:hover { text-decoration: underline; }
.hint-icon-sm { margin-left: 4px; font-size: 12px; color: var(--el-color-info); cursor: help; vertical-align: middle; }
.assumptions-block { padding: 0 4px; }
.assumption-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.assumption-tag { max-width: 100%; }
</style>
