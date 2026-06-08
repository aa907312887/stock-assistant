<template>
  <div class="page" v-loading="pageLoading">
    <div class="header">
      <div>
        <div class="titleRow">
          <el-button link type="primary" @click="router.push('/backtest/manual-trading')">
            ← 返回列表
          </el-button>
          <span class="title">{{ session?.asset_name || '手动模拟' }}</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>买入仅增加<strong>名义金额</strong>；推进时间后须录入<strong>收盘价</strong>，持仓按价格比例涨跌。</p>
                <p>推进录价后，买入区可点「用收盘价」一键填入成交价，无需重复输入。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
          <el-tag v-if="session" size="small" :type="session.status === 'ended' ? 'info' : 'success'">
            {{ session.status === 'ended' ? '已结束' : session.awaiting_reval ? '待录价' : '进行中' }}
          </el-tag>
        </div>
      </div>
    </div>

    <template v-if="session">
      <el-row :gutter="16" class="summaryRow">
        <el-col :span="6">
          <el-card shadow="never"><div class="label">当前模拟日</div><div class="value">{{ session.current_date }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never"><div class="label">持仓名义金额</div><div class="value">¥{{ fmt(session.position_value) }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never"><div class="label">累计买入</div><div class="value">¥{{ fmt(session.total_invested) }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="label">总盈亏</div>
            <div class="value" :class="pnlClass(session.total_pnl)">
              {{ session.total_pnl >= 0 ? '+' : '' }}¥{{ fmt(session.total_pnl) }}
              <span v-if="session.total_pnl_pct != null" class="pct">
                ({{ (session.total_pnl_pct * 100).toFixed(2) }}%)
              </span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row v-if="isActive" :gutter="16">
        <el-col :span="12">
          <el-card shadow="never" header="买入">
            <el-form label-width="90px">
              <el-form-item label="买入金额">
                <el-input-number v-model="buyForm.amount" :min="0.01" :step="10000" :precision="2" style="width: 100%" />
              </el-form-item>
              <el-form-item label="成交价">
                <div class="priceRow">
                  <el-input-number
                    v-model="buyForm.price"
                    :min="0.0001"
                    :step="1"
                    :precision="4"
                    class="priceInput"
                    controls-position="right"
                  />
                  <el-tooltip content="将最近一次录入的收盘价填入成交价" :show-after="200">
                    <el-button
                      :disabled="session.reference_price == null || session.awaiting_reval"
                      @click="fillBuyPriceFromReference"
                    >
                      用收盘价
                    </el-button>
                  </el-tooltip>
                </div>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="acting" :disabled="session.awaiting_reval" @click="handleBuy">
                  确认买入
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="never" header="推进时间">
            <div class="advanceBtns">
              <el-button :disabled="session.awaiting_reval" @click="handleAdvance('day')">+1 天</el-button>
              <el-button :disabled="session.awaiting_reval" @click="handleAdvance('week')">+1 周</el-button>
              <el-button :disabled="session.awaiting_reval" @click="handleAdvance('month')">+1 月</el-button>
              <el-button :disabled="session.awaiting_reval" @click="handleAdvance('year')">+1 年</el-button>
            </div>
            <el-alert
              v-if="session.awaiting_reval"
              type="warning"
              :closable="false"
              show-icon
              title="已推进至新日期，请录入收盘价以更新持仓"
              class="revalAlert"
            />
            <el-form v-if="session.awaiting_reval" label-width="90px" class="revalForm">
              <el-form-item label="收盘价">
                <el-input-number v-model="revalPrice" :min="0.0001" :step="1" :precision="4" style="width: 100%" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="acting" @click="handleReval">确认录价</el-button>
              </el-form-item>
            </el-form>
            <div v-if="!session.awaiting_reval" class="endRow">
              <el-button type="danger" plain :loading="acting" @click="handleEnd">结束交易</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="opsCard">
        <template #header>
          <div class="opsHeader">
            <span>操作流水</span>
            <span v-if="operations" class="opsMeta">
              总交易时间：{{ formatTotalTradingTime() }}
            </span>
          </div>
        </template>
        <el-table :data="operations?.items || []" stripe size="small">
          <el-table-column prop="op_date" label="日期" width="110" />
          <el-table-column prop="op_type_label" label="类型" width="100" />
          <el-table-column label="价格" width="100" align="right">
            <template #default="{ row }">{{ row.price != null ? row.price : '—' }}</template>
          </el-table-column>
          <el-table-column label="买入金额" width="110" align="right">
            <template #default="{ row }">
              {{ row.buy_amount != null ? fmt(row.buy_amount) : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="推进" width="80">
            <template #default="{ row }">{{ stepLabel(row.advance_step) }}</template>
          </el-table-column>
          <el-table-column label="持仓变化" min-width="160">
            <template #default="{ row }">
              ¥{{ fmt(row.position_before) }} → ¥{{ fmt(row.position_after) }}
            </template>
          </el-table-column>
          <el-table-column label="本段盈亏" width="110" align="right">
            <template #default="{ row }">
              <span v-if="row.segment_pnl == null">—</span>
              <span v-else :class="pnlClass(row.segment_pnl)">
                {{ row.segment_pnl >= 0 ? '+' : '' }}{{ fmt(row.segment_pnl) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="距上步(天)" width="100" align="right">
            <template #default="{ row }">{{ row.days_since_prev ?? '—' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  advanceSession,
  buySession,
  endSession,
  getSession,
  listOperations,
  revalSession,
  type AdvanceStep,
  type OperationsResponse,
  type SessionDetail,
} from '@/api/manualTrading'

const route = useRoute()
const router = useRouter()
const sessionId = computed(() => route.params.sessionId as string)

const pageLoading = ref(false)
const acting = ref(false)
const session = ref<SessionDetail | null>(null)
const operations = ref<OperationsResponse | null>(null)
const revalPrice = ref<number | undefined>(undefined)

const buyForm = ref({ amount: 100000, price: 2000 })
const isActive = computed(() => session.value?.status === 'active')

function fmt(v: number) {
  return v.toFixed(2)
}

function pnlClass(v: number) {
  return v >= 0 ? 'profit' : 'loss'
}

function stepLabel(step: string | null) {
  const map: Record<string, string> = {
    day: '+1天',
    week: '+1周',
    month: '+1月',
    year: '+1年',
  }
  return step ? map[step] || step : '—'
}

/** 日历日字符串 → 本地 Date（避免时区偏移） */
function parseDateOnly(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** 两日期之间的年、月、天（日历差，与后端 total_trading_days 口径一致） */
function calendarDiffParts(start: string, end: string) {
  const s = parseDateOnly(start)
  const e = parseDateOnly(end)
  let years = e.getFullYear() - s.getFullYear()
  let months = e.getMonth() - s.getMonth()
  let days = e.getDate() - s.getDate()
  if (days < 0) {
    months -= 1
    days += new Date(e.getFullYear(), e.getMonth(), 0).getDate()
  }
  if (months < 0) {
    years -= 1
    months += 12
  }
  return { years, months, days }
}

function formatTotalTradingTime(): string {
  const days = operations.value?.total_trading_days
  if (days == null) return '—'
  let text = `${days} 天`
  const start = session.value?.first_operation_date
  const end =
    session.value?.status === 'ended' && session.value.end_date
      ? session.value.end_date
      : session.value?.current_date
  if (days > 365 && start && end) {
    const { years, months, days: d } = calendarDiffParts(start, end)
    text += `（${years} 年 ${months} 月 ${d} 天）`
  }
  return text
}

function fillBuyPriceFromReference() {
  if (session.value?.reference_price != null) {
    buyForm.value.price = session.value.reference_price
  }
}

async function refresh() {
  const [s, ops] = await Promise.all([
    getSession(sessionId.value),
    listOperations(sessionId.value),
  ])
  session.value = s
  operations.value = ops
  if (s.reference_price != null && revalPrice.value == null) {
    revalPrice.value = s.reference_price
  }
}

async function loadPage() {
  pageLoading.value = true
  try {
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '加载失败'))
  } finally {
    pageLoading.value = false
  }
}

async function handleBuy() {
  acting.value = true
  try {
    session.value = await buySession(sessionId.value, buyForm.value.amount, buyForm.value.price)
    operations.value = await listOperations(sessionId.value)
    ElMessage.success('买入成功')
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '买入失败'))
  } finally {
    acting.value = false
  }
}

async function handleAdvance(step: AdvanceStep) {
  acting.value = true
  try {
    await advanceSession(sessionId.value, step)
    await refresh()
    ElMessage.success('已推进，请录入收盘价')
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '推进失败'))
  } finally {
    acting.value = false
  }
}

async function handleReval() {
  if (!revalPrice.value || revalPrice.value <= 0) {
    ElMessage.warning('请输入有效收盘价')
    return
  }
  acting.value = true
  try {
    session.value = await revalSession(sessionId.value, revalPrice.value)
    operations.value = await listOperations(sessionId.value)
    if (session.value.reference_price != null) {
      buyForm.value.price = session.value.reference_price
    }
    ElMessage.success('录价完成')
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '录价失败'))
  } finally {
    acting.value = false
  }
}

async function handleEnd() {
  try {
    await ElMessageBox.confirm('结束后不可再买入或推进，确定结束？', '结束交易', {
      type: 'warning',
    })
  } catch {
    return
  }
  acting.value = true
  try {
    session.value = await endSession(sessionId.value)
    operations.value = await listOperations(sessionId.value)
    ElMessage.success('已结束')
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '结束失败'))
  } finally {
    acting.value = false
  }
}

function getErrMsg(e: unknown, fallback: string) {
  const err = e as { response?: { data?: { detail?: { message?: string } | string } } }
  const detail = err.response?.data?.detail
  if (typeof detail === 'object' && detail?.message) return detail.message
  if (typeof detail === 'string') return detail
  return fallback
}

onMounted(loadPage)
</script>

<style scoped>
.page {
  padding: 8px 4px 24px;
}
.header {
  margin-bottom: 16px;
}
.titleRow {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.helpIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--el-border-color);
  font-size: 12px;
  cursor: help;
}
.tipBlock p {
  margin: 0 0 6px;
  max-width: 260px;
  line-height: 1.5;
}
.summaryRow {
  margin-bottom: 16px;
}
.label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.value {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 600;
}
.pct {
  font-size: 13px;
  font-weight: normal;
}
.advanceBtns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.priceRow {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.priceInput {
  flex: 1;
  min-width: 0;
}
.revalAlert {
  margin-bottom: 12px;
}
.revalForm {
  margin-top: 8px;
}
.endRow {
  margin-top: 12px;
}
.opsCard {
  margin-top: 16px;
}
.opsHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.opsMeta {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.profit {
  color: #f56c6c;
}
.loss {
  color: #67c23a;
}
</style>
