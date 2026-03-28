<template>
  <div class="stock-basic">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>股票基本信息</span>
          <span v-if="lastSyncedAtLabel" class="meta">最近同步：{{ lastSyncedAtLabel }}</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tip-body">
                <p><strong>本页能力</strong></p>
                <p>查看与查询 A 股上市证券的<strong>基础维度</strong>数据（代码、名称、交易所、板块、行业、地域、上市日期等），以及基于<strong>已入库日线</strong>汇总的<strong>历史最高价/最低价</strong>（非当日盘中价，由定时任务更新）。</p>
                <p>数据来源于 <strong>Tushare Pro 接口 stock_basic</strong>，与「综合选股」共用同一份股票主数据；不包含 K 线、实时行情与财务利润表等（请在综合选股查看）。</p>
              </div>
            </template>
            <span class="tip-icon" aria-label="本页能力说明">?</span>
          </el-tooltip>
        </div>
      </template>
      <el-form :inline="true" class="filters" @submit.prevent="handleSearch">
        <el-form-item label="代码">
          <el-input v-model="filters.code" placeholder="模糊" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="filters.name" placeholder="模糊" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="交易所">
          <el-select v-model="filters.exchange" placeholder="全部" clearable style="width: 120px">
            <el-option label="上交所(SSE)" value="SSE" />
            <el-option label="深交所(SZSE)" value="SZSE" />
            <el-option label="北交所(BSE)" value="BSE" />
          </el-select>
        </el-form-item>
        <el-form-item label="板块">
          <el-input v-model="filters.market" placeholder="主板/创业板/科创板" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="filters.industry" placeholder="模糊" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button :loading="syncing" @click="handleSync">手动同步</el-button>
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
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="exchange" label="交易所" width="110" />
        <el-table-column prop="market" label="板块" width="110" />
        <el-table-column prop="industry_name" label="行业" min-width="120" show-overflow-tooltip />
        <el-table-column prop="region" label="地域" width="100" show-overflow-tooltip />
        <el-table-column prop="list_date" label="上市日期" width="120" />
        <el-table-column label="历史最高价" width="110" align="right">
          <template #header>
            <span class="col-with-tip">
              历史最高价
              <el-tooltip placement="top" :show-after="200" content="已入库日线的历史最高价（全历史），非实时行情；无数据时显示 —。">
                <span class="tip-icon-inline" aria-label="历史最高价说明">?</span>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">{{ formatPriceOrDash(row.hist_high) }}</template>
        </el-table-column>
        <el-table-column label="历史最低价" width="110" align="right">
          <template #header>
            <span class="col-with-tip">
              历史最低价
              <el-tooltip placement="top" :show-after="200" content="已入库日线的历史最低价（全历史），非实时行情；无数据时显示 —。">
                <span class="tip-icon-inline" aria-label="历史最低价说明">?</span>
              </el-tooltip>
            </span>
          </template>
          <template #default="{ row }">{{ formatPriceOrDash(row.hist_low) }}</template>
        </el-table-column>
        <el-table-column prop="synced_at" label="记录同步时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.synced_at) }}</template>
        </el-table-column>
        <el-table-column prop="data_source" label="数据来源" width="100" />
      </el-table>
      <div v-if="!loading && items.length === 0 && total === 0" class="empty-tip">
        暂无数据。可先点击「手动同步」从 Tushare 拉取股票列表写入本地表，或确认后端已执行过同步任务。
      </div>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="fetchList"
        @size-change="onPageSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getStockBasicList, postStockBasicSync, type StockBasicItem } from '@/api/stockBasic'

const loading = ref(false)
const syncing = ref(false)
const items = ref<StockBasicItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const lastSyncedAt = ref<string | null>(null)

const filters = reactive({
  code: '',
  name: '',
  exchange: '',
  market: '',
  industry: '',
})

const lastSyncedAtLabel = computed(() => {
  const s = lastSyncedAt.value
  if (!s) return ''
  try {
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return s
    return d.toLocaleString()
  } catch {
    return s
  }
})

function formatDateTime(s: string | null | undefined): string {
  if (!s) return '-'
  try {
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return s
    return d.toLocaleString()
  } catch {
    return s
  }
}

function formatPriceOrDash(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(4)
}

function buildParams() {
  const p: Record<string, unknown> = {
    page: page.value,
    page_size: pageSize.value,
  }
  if (filters.code.trim()) p.code = filters.code.trim()
  if (filters.name.trim()) p.name = filters.name.trim()
  if (filters.exchange.trim()) p.exchange = filters.exchange.trim()
  if (filters.market.trim()) p.market = filters.market.trim()
  if (filters.industry.trim()) p.industry = filters.industry.trim()
  return p
}

async function fetchList() {
  loading.value = true
  try {
    const res = await getStockBasicList(buildParams())
    items.value = res.data.items
    total.value = res.data.total
    lastSyncedAt.value = res.data.last_synced_at
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      '数据暂时不可用，请稍后重试'
    ElMessage.error(String(msg))
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
  filters.exchange = ''
  filters.market = ''
  filters.industry = ''
  page.value = 1
  fetchList()
}

function onPageSizeChange() {
  page.value = 1
  fetchList()
}

async function handleSync() {
  syncing.value = true
  try {
    const res = await postStockBasicSync()
    const text =
      res.data.message ||
      `同步完成，共处理 ${res.data.stock_basic ?? 0} 条股票基本信息。`
    await ElMessageBox.alert(text, '同步完成', {
      confirmButtonText: '确定',
      type: 'success',
    })
    await fetchList()
  } catch (e: unknown) {
    const raw = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    const msg = Array.isArray(raw) ? raw.map((x) => String(x)).join('；') : String(raw ?? '同步失败')
    ElMessage.error(msg)
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.stock-basic {
  min-height: 400px;
}
.card-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.meta {
  margin-left: 8px;
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}
.tip-icon {
  cursor: help;
  color: var(--el-color-info);
  vertical-align: middle;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--el-color-info);
  font-size: 12px;
  line-height: 1;
}
.tip-body {
  max-width: 360px;
  line-height: 1.5;
  font-size: 13px;
}
.tip-body p {
  margin: 0 0 8px;
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
</style>
