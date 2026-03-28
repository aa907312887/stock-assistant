<template>
  <div class="page-wrap">
    <div class="page-head">
      <h1 class="page-title">
        大盘温度
        <el-tooltip placement="top" :show-after="200">
          <template #content>
            <div class="tip-block">
              展示最新温度、默认近 20 个交易日走势，以及按自然日区间查询的历史序列；用于感知市场情绪与仓位节奏参考，非确定性买卖信号。
            </div>
          </template>
          <el-icon class="tip-icon" :size="18"><QuestionFilled /></el-icon>
        </el-tooltip>
      </h1>
    </div>

    <el-card class="toolbar" shadow="never">
      <span class="toolbar-label">历史区间</span>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        :disabled-date="disabledFuture"
      />
      <el-button type="primary" :loading="rangeLoading" @click="applyRange">查询</el-button>
      <el-button @click="resetDefault">恢复默认</el-button>
    </el-card>

    <MarketTemperatureCard
      class="temp-card-wrap"
      :loading="loading"
      :error="cardError"
      :latest="displayLatest"
      :trend="displayTrend"
      :trend-title="trendTitle"
      :explain="explain"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import {
  getLatestMarketTemperature,
  getMarketTemperatureExplain,
  getMarketTemperatureRange,
  getMarketTemperatureTrend,
  rangeSnapshotToLatest,
  type MarketTemperatureLatest,
  type MarketTemperatureTrendPoint,
} from '@/api/marketTemperature'
import MarketTemperatureCard from '@/components/MarketTemperatureCard.vue'

const userStore = useUserStore()

const loading = ref(true)
const rangeLoading = ref(false)
const error = ref('')
const mode = ref<'default' | 'range'>('default')

const baselineLatest = ref<MarketTemperatureLatest | null>(null)
const baselineTrend = ref<MarketTemperatureTrendPoint[]>([])
const rangeLatest = ref<MarketTemperatureLatest | null>(null)
const rangeTrend = ref<MarketTemperatureTrendPoint[]>([])

const trendTitle = ref('近 20 个交易日')
const explain = ref<unknown>(null)
const dateRange = ref<[string, string] | null>(null)

const displayLatest = computed(() => (mode.value === 'range' ? rangeLatest.value : baselineLatest.value))
const displayTrend = computed(() => (mode.value === 'range' ? rangeTrend.value : baselineTrend.value))

/** 仅展示初始加载失败；区间查询失败仅用消息提示，不覆盖已有展示 */
const cardError = computed(() => (mode.value === 'range' ? '' : error.value))

function disabledFuture(d: Date) {
  const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const today = new Date()
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  return t > end
}

function fmtDate(v: string | unknown) {
  if (typeof v === 'string') return v
  if (v && typeof v === 'object' && 'toString' in v) return String(v)
  return String(v ?? '')
}

async function loadDefault() {
  loading.value = true
  error.value = ''
  try {
    const [lat, tr, exp] = await Promise.all([
      getLatestMarketTemperature(),
      getMarketTemperatureTrend(20),
      getMarketTemperatureExplain(),
    ])
    baselineLatest.value = lat
    baselineTrend.value = tr.points
    explain.value = exp
    trendTitle.value = '近 20 个交易日'
    mode.value = 'default'
    rangeLatest.value = null
    rangeTrend.value = []
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (e as Error)?.message ||
      '大盘温度加载失败'
    error.value = typeof msg === 'string' ? msg : '大盘温度加载失败'
    baselineLatest.value = null
    baselineTrend.value = []
  } finally {
    loading.value = false
  }
}

async function applyRange() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择开始与结束日期')
    return
  }
  const [start, end] = dateRange.value
  rangeLoading.value = true
  error.value = ''
  try {
    const data = await getMarketTemperatureRange(start, end)
    rangeLatest.value = rangeSnapshotToLatest(data)
    rangeTrend.value = data.points
    const sd = fmtDate(data.start_date)
    const ed = fmtDate(data.end_date)
    trendTitle.value = `区间 ${sd} ~ ${ed}（共 ${data.trade_day_count} 个交易日）`
    mode.value = 'range'
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (e as Error)?.message ||
      '查询失败'
    const text = typeof msg === 'string' ? msg : '查询失败'
    ElMessage.error(text)
  } finally {
    rangeLoading.value = false
  }
}

async function resetDefault() {
  dateRange.value = null
  await loadDefault()
}

onMounted(() => {
  userStore.loadUserFromStorage()
  loadDefault()
})
</script>

<style scoped>
.page-wrap {
  max-width: 960px;
}
.page-head {
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 1.35rem;
  font-weight: 600;
  color: #1e3a5f;
}
.tip-icon {
  cursor: help;
  color: #909399;
}
.tip-block {
  max-width: 320px;
  line-height: 1.5;
  font-size: 13px;
}
.toolbar {
  margin-bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.toolbar-label {
  font-size: 14px;
  color: #606266;
}
.temp-card-wrap {
  max-width: 100%;
}
</style>
