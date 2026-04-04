<template>
  <div class="stock-screening">
    <el-card shadow="never">
      <template #header>
        <div class="card-header-row">
          <div class="card-header-left">
            <span>综合选股</span>
            <span v-if="dataDate" class="data-date">{{ dataDatePrefix }}：{{ dataDateLabel }}</span>
            <el-popover placement="bottom-start" :width="480" trigger="click">
              <template #reference>
                <el-link type="primary" class="capability-link">查看当前产品能力</el-link>
              </template>
              <div class="capability-content">
                <p><strong>当前能力范围</strong></p>
                <p>1) 右上角可切换日K / 周K / 月K；默认日K。各周期均线与 MACD 均基于该周期收盘序列落库。</p>
                <p>2) 筛选含：代码、名称、多头排列、MACD 红柱、MA5 上穿 MA10、MACD 金叉（DIF 上穿 DEA）。金叉均指<strong>当前这根 K 线相对紧邻上一根同周期 K</strong>刚发生上穿；无上一根或指标为空时「是」不成立。</p>
                <p>3) 周K/月K 行上无日级估值（PE 等）与昨收、振幅等列时显示为「-」；财报仍为不晚于周期结束日的最近一期。</p>
                <p>4) 「历史最高/最低」为截至<strong>本行数据日（含）</strong>的日线累计极值（前复权口径）；日K 即该交易日；周/月 K 取<strong>周期结束日</strong>对应日线上的累计值。未回填 <code>cum_hist_*</code> 时显示「-」。</p>
              </div>
            </el-popover>
          </div>
          <el-radio-group v-model="timeframe" size="small" class="timeframe-switch" @change="onTimeframeChange">
            <el-radio-button label="daily">日K</el-radio-button>
            <el-radio-button label="weekly">周K</el-radio-button>
            <el-radio-button label="monthly">月K</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-form :inline="true" class="filters" @submit.prevent="handleSearch">
        <el-form-item label="股票代码">
          <el-input v-model="filters.code" placeholder="模糊匹配" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="filters.name" placeholder="模糊匹配" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="均线多头排列">
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
            >{{ row.code }}</a>
            <span v-else>{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="trade_date" :label="dateColumnLabel" width="120" />
        <el-table-column prop="open" label="开盘价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.open) }}</template>
        </el-table-column>
        <el-table-column prop="high" label="最高价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.high) }}</template>
        </el-table-column>
        <el-table-column prop="low" label="最低价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.low) }}</template>
        </el-table-column>
        <el-table-column prop="hist_high" width="108" align="right">
          <template #header>
            <span class="col-with-tip">
              历史最高
              <el-tooltip
                placement="top"
                :show-after="200"
                content="截至本行数据日（含）的日线累计最高价（前复权）；日K 即该交易日；周/月 K 为周期结束日对应日线。无数据时显示 -。"
              >
                <span class="tip-icon-inline" aria-label="历史最高价说明">?</span>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">{{ formatNum(row.hist_high) }}</template>
        </el-table-column>
        <el-table-column prop="hist_low" width="108" align="right">
          <template #header>
            <span class="col-with-tip">
              历史最低
              <el-tooltip
                placement="top"
                :show-after="200"
                content="截至本行数据日（含）的日线累计最低价（前复权）；日K 即该交易日；周/月 K 为周期结束日对应日线。无数据时显示 -。"
              >
                <span class="tip-icon-inline" aria-label="历史最低价说明">?</span>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">{{ formatNum(row.hist_low) }}</template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.close) }}</template>
        </el-table-column>
        <el-table-column prop="prev_close" label="昨收" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.prev_close) }}</template>
        </el-table-column>
        <el-table-column prop="change_amount" label="涨跌额" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.change_amount) }}</template>
        </el-table-column>
        <el-table-column prop="pct_change" label="涨跌幅%" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.pct_change) }}</template>
        </el-table-column>
        <el-table-column prop="ma5" label="MA5" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.ma5) }}</template>
        </el-table-column>
        <el-table-column prop="ma10" label="MA10" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.ma10) }}</template>
        </el-table-column>
        <el-table-column prop="ma20" label="MA20" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.ma20) }}</template>
        </el-table-column>
        <el-table-column prop="ma60" label="MA60" width="92" align="right">
          <template #default="{ row }">{{ formatNum(row.ma60) }}</template>
        </el-table-column>
        <el-table-column prop="macd_dif" label="MACD DIF" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.macd_dif) }}</template>
        </el-table-column>
        <el-table-column prop="macd_dea" label="MACD DEA" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.macd_dea) }}</template>
        </el-table-column>
        <el-table-column prop="macd_hist" label="MACD柱" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.macd_hist) }}</template>
        </el-table-column>
        <el-table-column prop="amplitude" label="振幅%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.amplitude) }}</template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.volume) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="pe" label="PE" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.pe) }}</template>
        </el-table-column>
        <el-table-column prop="pe_ttm" label="PE TTM" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.pe_ttm) }}</template>
        </el-table-column>
        <el-table-column prop="pb" label="PB" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.pb) }}</template>
        </el-table-column>
        <el-table-column prop="dv_ratio" label="股息率%" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.dv_ratio) }}</template>
        </el-table-column>
        <el-table-column prop="report_date" label="财报期" width="110" />
        <el-table-column prop="revenue" label="营业收入" width="120" align="right">
          <template #default="{ row }">{{ formatNum(row.revenue) }}</template>
        </el-table-column>
        <el-table-column prop="net_profit" label="净利润" width="120" align="right">
          <template #default="{ row }">{{ formatNum(row.net_profit) }}</template>
        </el-table-column>
        <el-table-column prop="eps" label="EPS" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.eps) }}</template>
        </el-table-column>
        <el-table-column prop="gross_profit_margin" label="毛利率%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.gross_profit_margin) }}</template>
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { getScreening, getLatestDate, type ScreeningItem, type ScreeningTimeframe } from '@/api/stock'
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const loading = ref(false)
const timeframe = ref<ScreeningTimeframe>('daily')
const items = ref<ScreeningItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dataDate = ref<string | null>(null)

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
    const res = await getScreening(buildParams())
    items.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '数据暂时不可用，请稍后重试'
    ElMessage.error(msg)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchLatestDate() {
  try {
    const res = await getLatestDate({ timeframe: timeframe.value })
    if (res.data.date) dataDate.value = res.data.date
  } catch {
    // 可选，不阻塞列表
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

function eastMoneyUrl(row: ScreeningItem): string | null {
  return eastMoneyQuoteUrl(row.code, row.exchange)
}

onMounted(() => {
  fetchLatestDate()
  fetchList()
})
</script>

<style scoped>
.stock-screening {
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
.timeframe-switch {
  flex-shrink: 0;
}
.data-date {
  margin-left: 16px;
  font-size: 0.9rem;
  color: #606266;
}
.capability-link {
  margin-left: 12px;
  font-size: 13px;
}
.capability-content p {
  margin: 6px 0;
  line-height: 1.5;
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
.col-with-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.tip-icon-inline {
  cursor: help;
  color: var(--el-color-info);
  font-size: 11px;
  line-height: 1;
  border: 1px solid var(--el-color-info);
  border-radius: 50%;
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
