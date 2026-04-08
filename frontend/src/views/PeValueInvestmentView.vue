<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">市盈率长线价值投资</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>本页按日线扫描全 A 股（排除 ST 和北交所），列出满足长线价值投资买入条件的股票。</p>
                <p><strong>PE 百分位 &lt; 5%</strong>：该股当前 PE 处于自 2019 年以来历史最低 5% 区间。</p>
                <p><strong>ROE &gt; 15%</strong>：最近一期财报净资产收益率超过 15%。</p>
                <p><strong>资产负债率 &lt; 80%</strong>：最近一期财报资产负债率低于 80%。</p>
                <p>只要满足条件即选出，不要求首次跌入。</p>
                <p>不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">
          PE 极度低估（百分位 &lt; 5%）+ 基本面健康（ROE &gt; 15%、负债 &lt; 80%）的股票。
        </div>
      </div>
      <div class="actions">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="width: 150px; margin-right: 12px"
        />
        <el-button :loading="loading" @click="loadLatest">查询最新结果</el-button>
        <el-button :loading="loading" type="primary" @click="handleExecute">手动执行选股</el-button>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">口径说明</div>
      </template>
      <div class="note">
        筛选 PE 历史百分位低于 5% 且最近一期财报 ROE &gt; 15%、资产负债率 &lt; 80% 的股票。排除 ST/*ST 和北交所股票。可手动选择日期执行选股。
      </div>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">本次执行信息</div>
      </template>
      <div v-if="execution" class="meta">
        <div><span class="k">截止日期</span><span class="v">{{ execution.as_of_date }}</span></div>
        <div><span class="k">策略版本</span><span class="v">{{ execution.strategy_version }}</span></div>
        <div><span class="k">执行ID</span><span class="v mono">{{ execution.execution_id }}</span></div>
      </div>
      <div v-else class="emptyMeta">尚未加载结果</div>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">筛选与列表</div>
      </template>
      <div class="filters">
        <span class="filterLabel">交易所</span>
        <el-select
          v-model="filterExchanges"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="不限"
          clearable
          style="width: 220px"
        >
          <el-option v-for="ex in exchangeOptions" :key="ex" :label="ex" :value="ex" />
        </el-select>
        <span class="filterLabel">板块</span>
        <el-select
          v-model="filterMarkets"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="不限"
          clearable
          style="width: 240px"
        >
          <el-option
            v-if="hasEmptyMarketInItems"
            label="空板块"
            :value="EMPTY_MARKET"
          />
          <el-option v-for="m in marketOptions" :key="m" :label="m" :value="m" />
        </el-select>
        <el-button v-if="filterActive" link type="primary" @click="clearFilters">清空筛选</el-button>
      </div>

      <el-table :data="filteredItems" v-loading="loading" stripe style="width: 100%; margin-top: 12px">
        <el-table-column width="110">
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
        <el-table-column prop="stock_name" label="名称" min-width="100" />
        <el-table-column prop="exchange" label="交易所" width="88" />
        <el-table-column prop="market" label="板块" width="100" />
        <el-table-column prop="trigger_date" label="触发日" width="120" />
        <el-table-column label="PE百分位" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ color: peColor(row.summary?.pe_percentile) }">
              {{ fmtNum(row.summary?.pe_percentile) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="ROE(%)" width="90" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.roe) }}</template>
        </el-table-column>
        <el-table-column label="负债率(%)" width="100" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.debt_to_assets) }}</template>
        </el-table-column>
        <el-table-column label="报告期" width="110">
          <template #default="{ row }">{{ row.summary?.report_date ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="收盘价" width="90" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.close) }}</template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0 && execution" class="empty">
        截止日暂无符合条件的股票（也可能数据未同步或条件较严）。
      </div>
      <div v-if="!loading && items.length > 0 && filteredItems.length === 0 && filterActive" class="empty filterEmpty">
        当前筛选条件下无结果，请放宽条件或
        <el-button link type="primary" @click="clearFilters">清空筛选</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import type { ExecuteStrategyResponse, ExecutionSnapshot, StrategySelectionItem } from '@/api/strategies'
import { executeStrategy, getLatestStrategyResult } from '@/api/strategies'
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const STRATEGY_ID = 'pe_value_investment'
const EMPTY_MARKET = '__EMPTY__'

const loading = ref(false)
const selectedDate = ref<string | null>(null)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])
const filterExchanges = ref<string[]>([])
const filterMarkets = ref<string[]>([])

function fmtNum(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(2)
}

function peColor(v: unknown): string {
  if (v === null || v === undefined) return ''
  const n = Number(v)
  if (Number.isNaN(n)) return ''
  if (n <= 10) return '#16a34a'
  if (n <= 20) return '#65a30d'
  if (n <= 40) return '#6b7280'
  return '#ea580c'
}

function detailMessage(e: unknown): string {
  const err = e as { response?: { data?: { detail?: unknown } }; message?: string }
  const d = err?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d && typeof (d as { message: string }).message === 'string') {
    return (d as { message: string }).message
  }
  return err?.message || '请求失败'
}

const exchangeOptions = computed(() => {
  const set = new Set<string>()
  for (const row of items.value) {
    const ex = (row.exchange ?? '').trim()
    if (ex) set.add(ex)
  }
  return Array.from(set).sort()
})

const marketOptions = computed(() => {
  const set = new Set<string>()
  for (const row of items.value) {
    const m = (row.market ?? '').trim()
    if (m) set.add(m)
  }
  return Array.from(set).sort()
})

const hasEmptyMarketInItems = computed(() =>
  items.value.some((row) => !(row.market ?? '').trim()),
)

const filterActive = computed(
  () => filterExchanges.value.length > 0 || filterMarkets.value.length > 0,
)

function exchangeMatches(row: StrategySelectionItem, selected: string[]): boolean {
  if (!selected.length) return true
  const ex = (row.exchange ?? '').trim()
  return selected.some((s) => ex === s)
}

function marketMatches(row: StrategySelectionItem, selected: string[]): boolean {
  if (!selected.length) return true
  const m = (row.market ?? '').trim()
  const hasEmpty = selected.includes(EMPTY_MARKET)
  const nonEmpty = selected.filter((s) => s !== EMPTY_MARKET)
  const emptyMatch = hasEmpty && !m
  const valMatch = nonEmpty.some((s) => m === s)
  return emptyMatch || valMatch
}

const filteredItems = computed(() => {
  const ex = filterExchanges.value
  const mk = filterMarkets.value
  return items.value.filter((row) => exchangeMatches(row, ex) && marketMatches(row, mk))
})

function clearFilters() {
  filterExchanges.value = []
  filterMarkets.value = []
}

function eastMoneyUrl(row: StrategySelectionItem): string | null {
  return eastMoneyQuoteUrl(row.stock_code, row.exchange)
}

async function handleExecute() {
  loading.value = true
  try {
    const payload = selectedDate.value ? { as_of_date: selectedDate.value } : undefined
    const res: ExecuteStrategyResponse = await executeStrategy(STRATEGY_ID, payload)
    execution.value = res.execution
    items.value = res.items ?? []
    clearFilters()
    ElMessage.success(`执行成功：候选 ${items.value.length} 只`)
  } catch (e: unknown) {
    ElMessage.error(detailMessage(e))
  } finally {
    loading.value = false
  }
}

async function loadLatest() {
  loading.value = true
  try {
    const params = selectedDate.value ? { as_of_date: selectedDate.value } : undefined
    const res = await getLatestStrategyResult(STRATEGY_ID, params)
    execution.value = res.execution
    items.value = res.items ?? []
    clearFilters()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { code?: string } } } }
    const code = err?.response?.data?.detail?.code
    if (code === 'NOT_FOUND') {
      execution.value = null
      items.value = []
      clearFilters()
      return
    }
    ElMessage.error(detailMessage(e))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLatest()
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 16px; }
.header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.titleRow { display: flex; align-items: center; gap: 8px; }
.title { font-size: 18px; font-weight: 700; color: #1e3a5f; }
.helpIcon { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: #e8eef5; color: #5b6b7c; font-size: 12px; font-weight: 600; cursor: default; }
.helpIcon:focus-visible { outline: 2px solid #409eff; outline-offset: 2px; }
.tipBlock { max-width: 360px; line-height: 1.5; font-size: 13px; }
.tipBlock p { margin: 0 0 8px; }
.tipBlock p:last-child { margin-bottom: 0; }
.subtitle { margin-top: 6px; color: #5b6b7c; font-size: 13px; line-height: 1.5; }
.cardTitle { font-weight: 600; }
.note { color: #3b4a5a; line-height: 1.6; }
.meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.k { display: inline-block; width: 72px; color: #6b7b8c; }
.v { color: #223; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
.emptyMeta { color: #8a98a8; }
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.filterLabel { font-size: 13px; color: #6b7b8c; }
.empty { margin-top: 12px; color: #8a98a8; font-size: 13px; }
.filterEmpty { color: #5b6b7c; }
.code-link { color: var(--el-color-primary); text-decoration: none; }
.code-link:hover { text-decoration: underline; }
.hint-icon-sm { margin-left: 4px; font-size: 12px; color: var(--el-color-info); cursor: help; vertical-align: middle; }
</style>
