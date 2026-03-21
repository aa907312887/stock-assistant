<template>
  <div class="stock-screening">
    <el-card shadow="never">
      <template #header>
        <span>综合选股</span>
        <span v-if="dataDate" class="data-date">数据日期：{{ dataDateLabel }}</span>
        <el-popover placement="bottom-start" :width="460" trigger="click">
          <template #reference>
            <el-link type="primary" class="capability-link">查看当前产品能力</el-link>
          </template>
          <div class="capability-content">
            <p><strong>当前能力范围</strong></p>
            <p>1) 每日收盘后同步 A 股全市场列表，并补齐当日价格信息。</p>
            <p>2) 价格字段：开盘/最高/最低/收盘/昨收、涨跌额、涨跌幅、成交量、成交额、振幅。</p>
            <p>3) 基本面字段：利润表口径（营业收入、净利润、EPS、毛利率）。</p>
            <p>4) 本期不提供 ROE；个别股票在停牌或上游缺字段时会显示为空。</p>
          </div>
        </el-popover>
      </template>
      <el-form :inline="true" class="filters" @submit.prevent="handleSearch">
        <el-form-item label="代码">
          <el-input v-model="filters.code" placeholder="股票代码" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item label="涨跌幅%">
          <el-input-number v-model="filters.pct_min" :precision="2" placeholder="最小" controls-position="right" style="width: 100px" />
          <span class="sep">-</span>
          <el-input-number v-model="filters.pct_max" :precision="2" placeholder="最大" controls-position="right" style="width: 100px" />
        </el-form-item>
        <el-form-item label="股价">
          <el-input-number v-model="filters.price_min" :precision="2" placeholder="最小" controls-position="right" style="width: 100px" />
          <span class="sep">-</span>
          <el-input-number v-model="filters.price_max" :precision="2" placeholder="最大" controls-position="right" style="width: 100px" />
        </el-form-item>
        <el-form-item label="毛利率%">
          <el-input-number v-model="filters.gpm_min" :precision="2" placeholder="最小" controls-position="right" style="width: 100px" />
          <span class="sep">-</span>
          <el-input-number v-model="filters.gpm_max" :precision="2" placeholder="最大" controls-position="right" style="width: 100px" />
        </el-form-item>
        <el-form-item label="营收(元)">
          <el-input-number v-model="filters.revenue_min" :precision="2" placeholder="最小" controls-position="right" style="width: 130px" />
          <span class="sep">-</span>
          <el-input-number v-model="filters.revenue_max" :precision="2" placeholder="最大" controls-position="right" style="width: 130px" />
        </el-form-item>
        <el-form-item label="净利润(元)">
          <el-input-number v-model="filters.net_profit_min" :precision="2" placeholder="最小" controls-position="right" style="width: 130px" />
          <span class="sep">-</span>
          <el-input-number v-model="filters.net_profit_max" :precision="2" placeholder="最大" controls-position="right" style="width: 130px" />
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
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="trade_date" label="日期" width="110" />
        <el-table-column prop="open" label="开盘价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.open) }}</template>
        </el-table-column>
        <el-table-column prop="high" label="最高价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.high) }}</template>
        </el-table-column>
        <el-table-column prop="low" label="最低价" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.low) }}</template>
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
        <el-table-column prop="amplitude" label="振幅%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.amplitude) }}</template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.volume) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.amount) }}</template>
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
import { getScreening, getLatestDate, type ScreeningItem } from '@/api/stock'

const loading = ref(false)
const items = ref<ScreeningItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dataDate = ref<string | null>(null)

const filters = reactive({
  code: '',
  pct_min: undefined as number | undefined,
  pct_max: undefined as number | undefined,
  price_min: undefined as number | undefined,
  price_max: undefined as number | undefined,
  gpm_min: undefined as number | undefined,
  gpm_max: undefined as number | undefined,
  revenue_min: undefined as number | undefined,
  revenue_max: undefined as number | undefined,
  net_profit_min: undefined as number | undefined,
  net_profit_max: undefined as number | undefined,
})

const dataDateLabel = computed(() => {
  if (!dataDate.value) return ''
  const today = new Date().toISOString().slice(0, 10)
  if (dataDate.value === today) return '今天'
  const yesterday = new Date(Date.now() - 864e5).toISOString().slice(0, 10)
  if (dataDate.value === yesterday) return '昨天'
  return dataDate.value
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
  }
  if (filters.code) p.code = filters.code
  if (filters.pct_min != null) p.pct_min = filters.pct_min
  if (filters.pct_max != null) p.pct_max = filters.pct_max
  if (filters.price_min != null) p.price_min = filters.price_min
  if (filters.price_max != null) p.price_max = filters.price_max
  if (filters.gpm_min != null) p.gpm_min = filters.gpm_min
  if (filters.gpm_max != null) p.gpm_max = filters.gpm_max
  if (filters.revenue_min != null) p.revenue_min = filters.revenue_min
  if (filters.revenue_max != null) p.revenue_max = filters.revenue_max
  if (filters.net_profit_min != null) p.net_profit_min = filters.net_profit_min
  if (filters.net_profit_max != null) p.net_profit_max = filters.net_profit_max
  return p
}

async function fetchList() {
  loading.value = true
  try {
    const res = await getScreening(buildParams())
    items.value = res.data.items
    total.value = res.data.total
    if (res.data.data_date) dataDate.value = res.data.data_date
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
    const res = await getLatestDate()
    if (res.data.date) dataDate.value = res.data.date
  } catch {
    // 可选，不阻塞列表
  }
}

function handleSearch() {
  page.value = 1
  fetchList()
}

function handleReset() {
  filters.code = ''
  filters.pct_min = filters.pct_max = undefined
  filters.price_min = filters.price_max = undefined
  filters.gpm_min = filters.gpm_max = undefined
  filters.revenue_min = filters.revenue_max = undefined
  filters.net_profit_min = filters.net_profit_max = undefined
  page.value = 1
  fetchList()
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
.sep {
  margin: 0 4px;
  color: #909399;
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
</style>
