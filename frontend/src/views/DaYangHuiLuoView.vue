<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">大阳回落法</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>本页按日线扫描全 A 股，列出当日满足「大阳回落法」大阳线触发条件的股票。</p>
                <p><strong>低位约束</strong>：收盘价 ≤ 历史最高价的 1/2</p>
                <p><strong>近期无大涨</strong>：前 20 天无超过 5% 涨幅</p>
                <p><strong>大阳线</strong>：涨幅 ≥ 8%，成交量 ≥ 前一日 2 倍</p>
                <p>筛出当日首根大阳线信号，次日形态自行判断。</p>
                <p>不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">
          筛选当日出现低位大阳放量信号的股票，次日形态自行观察判断。
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
        <p class="note-section-title">一、策略思路</p>
        <p>
          大阳回落法寻找<strong>长期低位、近期无异动</strong>的股票中，出现<strong>放量大阳线</strong>突破后、
          次日<strong>阴线小幅回落</strong>的形态，在回落收盘价买入，利用大阳线的支撑效应获取短线收益。
        </p>

        <p class="note-section-title">二、完整操作流程</p>
        <ol class="note-ol">
          <li>
            <strong>第一步：大阳线触发（Day T）—— 本页筛选的内容</strong><br/>
            同时满足以下全部条件的股票会被列入候选：
            <ul class="note-ul">
              <li><strong>低位约束</strong>：当日收盘价 &le; 该股截至当日累计历史最高价的 50%</li>
              <li><strong>近期无大涨</strong>：前 20 个交易日内无单日涨幅超过 5% 的交易日</li>
              <li><strong>大阳线</strong>：当日涨幅 &ge; 8%（收盘较前收），且为阳线（收盘 &gt; 开盘）</li>
              <li><strong>放量确认</strong>：当日成交量 &ge; 前一交易日成交量的 2 倍</li>
            </ul>
          </li>
          <li>
            <strong>第二步：回落买入（Day T+1）—— 需自行观察判断</strong><br/>
            大阳线次日，观察是否满足买入条件：
            <ul class="note-ul">
              <li>次日收<strong>阴线</strong>（收盘 &lt; 开盘）</li>
              <li>次日收盘价在大阳线<strong>实体上 2/3 位置之上</strong>（即回落幅度不超过阳线实体的 1/3）</li>
              <li>满足以上条件时，以<strong>次日收盘价买入</strong></li>
            </ul>
          </li>
          <li>
            <strong>第三步：持仓与退出</strong><br/>
            <ul class="note-ul">
              <li><strong>止盈</strong>：持仓期间，盘中最高价触及买入价 &times; 1.10（盈利 10%），以该价格卖出</li>
              <li><strong>止损</strong>：持仓期间，盘中最低价触及大阳线开盘价（Day T 开盘价），以该价格卖出</li>
              <li>同日同时触及止盈止损时，<strong>止损优先</strong></li>
            </ul>
          </li>
        </ol>

        <p class="note-section-title">三、本页说明</p>
        <p>
          本页<strong>仅执行第一步</strong>：扫描全 A 股日线数据（剔除 ST/*ST），列出当日满足大阳线触发条件的候选股票。
          第二步的回落买入确认和第三步的止盈止损操作需要自行在次日及后续交易日中观察执行。
          可手动选择历史日期重新执行选股。
        </p>
        <p class="note-disclaimer">本策略仅供学习研究，不构成投资建议。</p>
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
        <el-table-column prop="trigger_date" label="大阳日" width="120" />
        <el-table-column label="阳线涨幅" width="100" align="right">
          <template #default="{ row }">{{ fmtPct(row.summary?.yang_gain_pct) }}</template>
        </el-table-column>
        <el-table-column label="成交量比" width="100" align="right">
          <template #default="{ row }">{{ fmtRatio(row.summary?.volume_ratio) }}</template>
        </el-table-column>
        <el-table-column label="阳线开盘" width="100" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.yang_open) }}</template>
        </el-table-column>
        <el-table-column label="阳线收盘" width="100" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.yang_close) }}</template>
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

const STRATEGY_ID = 'da_yang_hui_luo'
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

function fmtPct(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${n.toFixed(2)}%`
}

function fmtRatio(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${n.toFixed(2)}倍`
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
  max-width: 360px;
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
  line-height: 1.8;
  font-size: 13.5px;
}
.note p {
  margin: 0 0 8px;
}
.note-section-title {
  font-weight: 600;
  color: #1e3a5f;
  margin-top: 14px !important;
  margin-bottom: 6px !important;
}
.note-section-title:first-child {
  margin-top: 0 !important;
}
.note-ol {
  margin: 6px 0 10px 0;
  padding-left: 20px;
}
.note-ol > li {
  margin-bottom: 10px;
}
.note-ul {
  margin: 4px 0 2px 0;
  padding-left: 18px;
  list-style: disc;
}
.note-ul > li {
  margin-bottom: 3px;
}
.note-disclaimer {
  color: #8a98a8;
  font-size: 12.5px;
  margin-top: 10px !important;
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
.code-link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.code-link:hover {
  text-decoration: underline;
}
.hint-icon-sm {
  margin-left: 4px;
  font-size: 12px;
  color: var(--el-color-info);
  cursor: help;
  vertical-align: middle;
}
</style>
