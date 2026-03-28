<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">恐慌回落战法</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>本页按日线扫描全 A 股，列出截止日满足「恐慌回落」触发条件的股票；数据与回测策略同源。交易日每天 17:20（上海时区）与「冲高回落战法」同期自动落选并落库，也可随时手动执行。</p>
                <p>不含分时数据：模拟为触发日<strong>收盘价</strong>买入、下一交易日<strong>收盘价</strong>卖出；默认不计滑点与手续费（与回测一致）。</p>
                <p>不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">
          均线空头、前 5 日至少跌 4 日、低开 ≥3%、当日收跌 ≥7%、放量显著；触发日收盘买入、次日收盘卖出（与回测口径一致）。
        </div>
      </div>
      <div class="actions">
        <el-button :loading="loading" @click="loadLatest">查询最新结果</el-button>
        <el-button :loading="loading" type="primary" @click="handleExecute">手动执行选股</el-button>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">口径说明</div>
      </template>
      <div class="note">
        当前仅有日线：判定与模拟成交均基于日线开高低收量；无 Level-2/分时。若截止日为最近交易日且尚无下一交易日收盘价，则可能仅展示触发信号、不展示模拟收益率。交易日 17:20 自动执行选股（与冲高回落战法同一调度时刻）；非交易日或数据未就绪时跳过，可用手动执行补跑。
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
        <el-table-column prop="stock_code" label="代码" width="110" />
        <el-table-column prop="stock_name" label="名称" min-width="120" />
        <el-table-column prop="exchange" label="交易所" width="88" />
        <el-table-column prop="market" label="板块" width="100" />
        <el-table-column prop="trigger_date" label="触发日" width="120" />
        <el-table-column label="低开" width="100">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.gap_down_pct) }}
          </template>
        </el-table-column>
        <el-table-column label="当日跌" width="100">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.day_drop_pct) }}
          </template>
        </el-table-column>
        <el-table-column label="模拟收益(T+1收)" min-width="140">
          <template #default="{ row }">
            <span v-if="row.summary?.return_rate != null">{{ fmtPct(row.summary.return_rate) }}</span>
            <el-tooltip v-else content="无下一交易日收盘价或未平仓时不展示" placement="top">
              <span class="muted">—</span>
            </el-tooltip>
          </template>
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
import type { ExecuteStrategyResponse, ExecutionSnapshot, StrategySelectionItem } from '@/api/strategies'
import { executeStrategy, getLatestStrategyResult } from '@/api/strategies'

const STRATEGY_ID = 'panic_pullback'
const EMPTY_MARKET = '__EMPTY__'

const loading = ref(false)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])
const filterExchanges = ref<string[]>([])
const filterMarkets = ref<string[]>([])

function fmtPct(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
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

async function handleExecute() {
  loading.value = true
  try {
    const res: ExecuteStrategyResponse = await executeStrategy(STRATEGY_ID)
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
    const res = await getLatestStrategyResult(STRATEGY_ID)
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
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.titleRow {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1e3a5f;
}
.helpIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e8eef5;
  color: #5b6b7c;
  font-size: 12px;
  font-weight: 600;
  cursor: default;
}
.helpIcon:focus-visible {
  outline: 2px solid #409eff;
  outline-offset: 2px;
}
.tipBlock {
  max-width: 320px;
  line-height: 1.5;
  font-size: 13px;
}
.tipBlock p {
  margin: 0 0 8px;
}
.tipBlock p:last-child {
  margin-bottom: 0;
}
.subtitle {
  margin-top: 6px;
  color: #5b6b7c;
  font-size: 13px;
  line-height: 1.5;
}
.cardTitle {
  font-weight: 600;
}
.note {
  color: #3b4a5a;
  line-height: 1.6;
}
.meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.k {
  display: inline-block;
  width: 72px;
  color: #6b7b8c;
}
.v {
  color: #223;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}
.emptyMeta {
  color: #8a98a8;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.filterLabel {
  font-size: 13px;
  color: #6b7b8c;
}
.empty {
  margin-top: 12px;
  color: #8a98a8;
  font-size: 13px;
}
.filterEmpty {
  color: #5b6b7c;
}
.muted {
  color: #b0b8c0;
  cursor: help;
}
</style>
