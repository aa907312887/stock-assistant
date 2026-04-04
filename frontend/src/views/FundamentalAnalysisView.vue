<template>
  <div class="fundamental-analysis">
    <el-card shadow="never">
      <template #header>
        <div class="card-header-row">
          <div class="card-header-left">
            <span>基本面分析</span>
            <el-popover placement="bottom-start" :width="420" trigger="click">
              <template #reference>
                <el-link type="primary" class="capability-link">数据说明</el-link>
              </template>
              <div class="capability-content">
                <p><strong>数据来源</strong></p>
                <p>财务指标数据来自 Tushare fina_indicator API，展示每只股票最新一期财报的基本面数据。</p>
                <p>ROE 为核心指标，长期 ROE > 15% 通常说明公司具有持续的竞争优势。</p>
                <p>资产负债率反映偿债能力，一般 60% 以下为安全水平（金融业除外）。</p>
              </div>
            </el-popover>
          </div>
        </div>
      </template>

      <el-form :inline="true" class="filters" @submit.prevent="handleSearch">
        <el-form-item label="股票代码">
          <el-input v-model="filters.code" placeholder="模糊匹配" clearable style="width: 130px" />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="filters.name" placeholder="模糊匹配" clearable style="width: 130px" />
        </el-form-item>
        <el-form-item label="ROE范围">
          <el-input-number v-model="filters.min_roe" :precision="2" :controls="false" placeholder="最小" style="width: 80px" />
          <span style="margin: 0 4px">~</span>
          <el-input-number v-model="filters.max_roe" :precision="2" :controls="false" placeholder="最大" style="width: 80px" />
        </el-form-item>
        <el-form-item label="资产负债率">
          <el-input-number v-model="filters.min_debt" :precision="2" :controls="false" placeholder="最小" style="width: 80px" />
          <span style="margin: 0 4px">~</span>
          <el-input-number v-model="filters.max_debt" :precision="2" :controls="false" placeholder="最大" style="width: 80px" />
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="filters.sort_by" style="width: 120px">
            <el-option label="ROE" value="roe" />
            <el-option label="ROA" value="roa" />
            <el-option label="资产负债率" value="debt_to_assets" />
            <el-option label="净利率" value="net_margin" />
            <el-option label="EPS" value="eps" />
            <el-option label="营业收入" value="revenue" />
            <el-option label="净利润" value="net_profit" />
          </el-select>
          <el-radio-group v-model="filters.sort_order" size="small" style="margin-left: 8px">
            <el-radio-button label="desc">降序</el-radio-button>
            <el-radio-button label="asc">升序</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">筛选</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="items" stripe border style="width: 100%">
        <!-- 基本信息 -->
        <el-table-column prop="code" label="代码" width="110" fixed />
        <el-table-column prop="name" label="名称" width="100" fixed />
        <el-table-column prop="report_date" label="财报期" width="110" />
        <el-table-column prop="ann_date" label="公告日" width="110" />

        <!-- 盈利能力 -->
        <el-table-column label="营业收入" width="130" align="right">
          <template #default="{ row }">{{ formatAmount(row.revenue) }}</template>
        </el-table-column>
        <el-table-column label="净利润" width="130" align="right">
          <template #default="{ row }">{{ formatAmount(row.net_profit) }}</template>
        </el-table-column>
        <el-table-column label="EPS" width="80" align="right">
          <template #default="{ row }">{{ formatNum(row.eps) }}</template>
        </el-table-column>
        <el-table-column label="BPS" width="80" align="right">
          <template #default="{ row }">{{ formatNum(row.bps) }}</template>
        </el-table-column>
        <el-table-column label="ROE%" width="90" align="right">
          <template #default="{ row }">
            <span :class="roeClass(row.roe)">{{ formatNum(row.roe) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="ROE扣非%" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.roe_dt) }}</template>
        </el-table-column>
        <el-table-column label="ROA%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.roa) }}</template>
        </el-table-column>
        <el-table-column label="毛利率%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.gross_margin) }}</template>
        </el-table-column>
        <el-table-column label="净利率%" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.net_margin) }}</template>
        </el-table-column>

        <!-- 偿债能力 -->
        <el-table-column label="资产负债率%" width="110" align="right">
          <template #default="{ row }">
            <span :class="debtClass(row.debt_to_assets)">{{ formatNum(row.debt_to_assets) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="流动比率" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.current_ratio) }}</template>
        </el-table-column>
        <el-table-column label="速动比率" width="90" align="right">
          <template #default="{ row }">{{ formatNum(row.quick_ratio) }}</template>
        </el-table-column>

        <!-- 现金流 -->
        <el-table-column label="每股现金流" width="100" align="right">
          <template #default="{ row }">{{ formatNum(row.cfps) }}</template>
        </el-table-column>
        <el-table-column label="EBIT" width="130" align="right">
          <template #default="{ row }">{{ formatAmount(row.ebit) }}</template>
        </el-table-column>
        <el-table-column label="现金流/利润" width="110" align="right">
          <template #default="{ row }">{{ formatNum(row.ocf_to_profit) }}</template>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getFundamentals, type FundamentalItem } from '@/api/fundamental'

const loading = ref(false)
const items = ref<FundamentalItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  code: '',
  name: '',
  min_roe: undefined as number | undefined,
  max_roe: undefined as number | undefined,
  min_debt: undefined as number | undefined,
  max_debt: undefined as number | undefined,
  sort_by: 'roe',
  sort_order: 'desc' as 'asc' | 'desc',
})

function formatNum(v: number | string | null | undefined): string {
  if (v == null) return '-'
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function formatAmount(v: number | string | null | undefined): string {
  if (v == null) return '-'
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n)) return '-'
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function roeClass(v: number | null | undefined): string {
  if (v == null) return ''
  if (v >= 15) return 'val-good'
  if (v >= 10) return 'val-ok'
  if (v < 0) return 'val-bad'
  return ''
}

function debtClass(v: number | null | undefined): string {
  if (v == null) return ''
  if (v > 70) return 'val-bad'
  if (v > 60) return 'val-warn'
  return ''
}

function buildParams() {
  const p: Record<string, unknown> = {
    page: page.value,
    page_size: pageSize.value,
    sort_by: filters.sort_by,
    sort_order: filters.sort_order,
  }
  if (filters.code) p.code = filters.code
  if (filters.name) p.name = filters.name
  if (filters.min_roe !== undefined) p.min_roe = filters.min_roe
  if (filters.max_roe !== undefined) p.max_roe = filters.max_roe
  if (filters.min_debt !== undefined) p.min_debt_to_assets = filters.min_debt
  if (filters.max_debt !== undefined) p.max_debt_to_assets = filters.max_debt
  return p
}

async function fetchList() {
  loading.value = true
  try {
    const res = await getFundamentals(buildParams())
    items.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '数据暂时不可用，请稍后重试'
    ElMessage.error(typeof msg === 'string' ? msg : '加载失败')
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchList()
}

function handleReset() {
  filters.code = ''
  filters.name = ''
  filters.min_roe = undefined
  filters.max_roe = undefined
  filters.min_debt = undefined
  filters.max_debt = undefined
  filters.sort_by = 'roe'
  filters.sort_order = 'desc'
  page.value = 1
  fetchList()
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.fundamental-analysis {
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
.val-good {
  color: #67c23a;
  font-weight: 600;
}
.val-ok {
  color: #e6a23c;
}
.val-warn {
  color: #e6a23c;
}
.val-bad {
  color: #f56c6c;
  font-weight: 600;
}
</style>
