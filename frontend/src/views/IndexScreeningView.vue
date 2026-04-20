<template>
  <div class="index-screening">
    <el-card shadow="never">
      <template #header>
        <div class="card-header-row">
          <div class="card-header-left">
            <span>指数基金</span>
            <span v-if="dataDate" class="data-date">{{ dataDatePrefix }}：{{ dataDateLabel }}</span>
            <el-tooltip
              placement="bottom-start"
              :width="420"
              :show-after="200"
            >
              <template #content>
                <p>本页为指数日/周/月 K 与均线、MACD 的专题浏览，价格与涨跌幅为<strong>指数点位</strong>，非股价，非 ETF 份额价。</p>
                <p>历史模拟/回测以指数代码为标的时，按项目规则使用 <code>index_*_bar</code> 行情，<strong>不</strong>做个股涨跌停校验，T+1 仍保留。成分与指数 PE 百分位在「详情」中展示；PE 百分位为按成分权重的统计推理，非官方发布值。</p>
              </template>
              <el-icon class="header-hint" aria-label="产品能力说明"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-radio-group v-model="timeframe" size="small" class="timeframe-switch" @change="onTimeframeChange">
            <el-radio-button label="daily">日K</el-radio-button>
            <el-radio-button label="weekly">周K</el-radio-button>
            <el-radio-button label="monthly">月K</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-form :inline="true" class="filters" @submit.prevent="handleSearch">
        <el-form-item label="指数代码">
          <el-input v-model="filters.code" placeholder="模糊匹配" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="指数名称">
          <el-input v-model="filters.name" placeholder="模糊匹配" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="均线多头">
          <el-select v-model="filters.ma_bull" clearable placeholder="不限" style="width: 100px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="MACD红柱">
          <el-select v-model="filters.macd_red" clearable placeholder="不限" style="width: 100px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="MA5上穿MA10">
          <el-select v-model="filters.ma_cross" clearable placeholder="不限" style="width: 100px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="MACD金叉">
          <el-select v-model="filters.macd_cross" clearable placeholder="不限" style="width: 100px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">筛选</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      <el-table
        v-loading="loading"
        :data="items"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="trade_date" :label="dateColumnLabel" width="120" />
        <el-table-column prop="open" label="开盘" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.open) }}</template>
        </el-table-column>
        <el-table-column prop="high" label="最高" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.high) }}</template>
        </el-table-column>
        <el-table-column prop="low" label="最低" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.low) }}</template>
        </el-table-column>
        <el-table-column prop="close" label="收盘" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.close) }}</template>
        </el-table-column>
        <el-table-column prop="pct_change" label="涨跌幅%" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.pct_change) }}</template>
        </el-table-column>
        <el-table-column prop="ma5" label="MA5" width="88" align="right">
          <template #default="{ row }">{{ formatNum(row.ma5) }}</template>
        </el-table-column>
        <el-table-column prop="ma10" label="MA10" width="88" align="right">
          <template #default="{ row }">{{ formatNum(row.ma10) }}</template>
        </el-table-column>
        <el-table-column prop="ma20" label="MA20" width="88" align="right">
          <template #default="{ row }">{{ formatNum(row.ma20) }}</template>
        </el-table-column>
        <el-table-column prop="ma60" label="MA60" width="88" align="right">
          <template #default="{ row }">{{ formatNum(row.ma60) }}</template>
        </el-table-column>
        <el-table-column prop="macd_hist" label="MACD柱" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.macd_hist) }}</template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.volume) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.amount) }}</template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && items.length === 0 && total === 0" class="empty-tip">暂无符合条件的数据</div>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="fetchList"
        @size-change="fetchList"
      />
    </el-card>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="520px" destroy-on-close @closed="onDrawerClosed">
      <div v-loading="compositionLoading" class="drawer-body">
        <template v-if="composition">
          <div class="drawer-meta">
            <span>
              指数 PE 百分位（推理）
              <el-tooltip placement="top" :show-after="200">
                <template #content>
                  由成分在快照日的 PE 百分位按披露权重加权；剔除无 PE 百分位样本后重新归一，非交易所官方指标。
                </template>
                <el-icon class="inline-icon"><QuestionFilled /></el-icon>
              </el-tooltip>
              ：
              <strong>{{ composition.index_pe_percentile != null ? `${composition.index_pe_percentile}%` : '—' }}</strong>
            </span>
          </div>
          <div v-if="composition.pe_percentile_meta" class="drawer-meta muted">
            权重表日期：{{ composition.weight_table_date || '—' }}；
            快照日：{{ composition.snapshot_trade_date || '—' }}；
            覆盖权重占比：{{
              composition.pe_percentile_meta.participating_weight_ratio != null
                ? `${(composition.pe_percentile_meta.participating_weight_ratio * 100).toFixed(2)}%`
                : '—'
            }}；
            成分数 {{ composition.pe_percentile_meta.constituents_total }}，
            含 PE 百分位 {{ composition.pe_percentile_meta.constituents_with_pe }}
          </div>
          <div v-if="composition.message" class="drawer-msg">{{ composition.message }}</div>
          <el-table :data="composition.items" stripe border max-height="420" size="small">
            <el-table-column prop="con_code" label="成分代码" width="120" />
            <el-table-column prop="weight" label="权重" width="100" align="right">
              <template #default="{ row }">
                {{ row.weight != null ? `${(row.weight * 100).toFixed(4)}%` : '—' }}
              </template>
            </el-table-column>
            <el-table-column prop="pe_percentile" label="PE百分位" width="100" align="right">
              <template #default="{ row }">
                {{ row.pe_percentile != null ? `${row.pe_percentile}%` : '—' }}
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getIndexComposition,
  getIndexLatestDate,
  getIndexScreening,
  type CompositionResponse,
  type IndexScreeningItem,
  type ScreeningTimeframe,
} from '@/api/indexFund'

const loading = ref(false)
const timeframe = ref<ScreeningTimeframe>('daily')
const items = ref<IndexScreeningItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dataDate = ref<string | null>(null)

const drawerVisible = ref(false)
const compositionLoading = ref(false)
const composition = ref<CompositionResponse | null>(null)
const selectedRow = ref<IndexScreeningItem | null>(null)

const filters = reactive({
  code: '',
  name: '',
  ma_bull: undefined as boolean | undefined,
  macd_red: undefined as boolean | undefined,
  ma_cross: undefined as boolean | undefined,
  macd_cross: undefined as boolean | undefined,
})

const dataDateLabel = computed(() => {
  if (!dataDate.value) return ''
  const today = new Date().toISOString().slice(0, 10)
  if (dataDate.value === today) return '今天'
  const yesterday = new Date(Date.now() - 864e5).toISOString().slice(0, 10)
  if (dataDate.value === yesterday) return '昨天'
  return dataDate.value
})

const dataDatePrefix = computed(() => {
  if (timeframe.value === 'weekly' || timeframe.value === 'monthly') return '快照日期'
  return '数据日期'
})

const dateColumnLabel = computed(() => {
  if (timeframe.value === 'weekly') return '周结束日'
  if (timeframe.value === 'monthly') return '月结束日'
  return '交易日'
})

const drawerTitle = computed(() => {
  if (!selectedRow.value) return '指数详情'
  return `${selectedRow.value.name || ''}（${selectedRow.value.code}）`
})

function formatNum(v: number | string | null | undefined): string {
  if (v == null) return '-'
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function buildParams() {
  const p: Record<string, unknown> = {
    page: page.value,
    page_size: pageSize.value,
    timeframe: timeframe.value,
  }
  if (filters.code) p.code = filters.code
  if (filters.name) p.name = filters.name
  if (filters.ma_bull === true || filters.ma_bull === false) p.ma_bull = filters.ma_bull
  if (filters.macd_red === true || filters.macd_red === false) p.macd_red = filters.macd_red
  if (filters.ma_cross === true || filters.ma_cross === false) p.ma_cross = filters.ma_cross
  if (filters.macd_cross === true || filters.macd_cross === false) p.macd_cross = filters.macd_cross
  return p
}

async function fetchList() {
  loading.value = true
  try {
    const res = await getIndexScreening(buildParams())
    items.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      '数据暂时不可用，请稍后重试'
    ElMessage.error(msg)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchLatestDate() {
  try {
    const res = await getIndexLatestDate({ timeframe: timeframe.value })
    if (res.data.date) dataDate.value = res.data.date
  } catch {
    /* 忽略 */
  }
}

async function onTimeframeChange() {
  page.value = 1
  await fetchLatestDate()
  await fetchList()
}

function handleSearch() {
  page.value = 1
  fetchList()
}

function handleReset() {
  filters.code = ''
  filters.name = ''
  filters.ma_bull = undefined
  filters.macd_red = undefined
  filters.ma_cross = undefined
  filters.macd_cross = undefined
  page.value = 1
  fetchList()
}

async function openDetail(row: IndexScreeningItem) {
  selectedRow.value = row
  drawerVisible.value = true
  compositionLoading.value = true
  composition.value = null
  try {
    const res = await getIndexComposition(row.code)
    composition.value = res.data
  } catch {
    ElMessage.error('加载成分失败')
  } finally {
    compositionLoading.value = false
  }
}

function onDrawerClosed() {
  selectedRow.value = null
  composition.value = null
}

onMounted(() => {
  fetchLatestDate()
  fetchList()
})
</script>

<style scoped>
.index-screening {
  min-height: 400px;
}
.card-header-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-header-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.header-hint {
  cursor: help;
  color: var(--el-color-info);
  font-size: 18px;
}
.timeframe-switch {
  flex-shrink: 0;
}
.data-date {
  margin-left: 16px;
  font-size: 0.9rem;
  color: #606266;
}
.filters {
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.empty-tip {
  padding: 24px;
  text-align: center;
  color: #909399;
}
.drawer-body {
  min-height: 120px;
}
.drawer-meta {
  margin-bottom: 12px;
  line-height: 1.6;
}
.drawer-meta.muted {
  font-size: 13px;
  color: #606266;
}
.drawer-msg {
  margin-bottom: 8px;
  color: #e6a23c;
  font-size: 13px;
}
.inline-icon {
  vertical-align: middle;
  cursor: help;
}
</style>
