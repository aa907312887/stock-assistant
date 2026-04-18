<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">
          60 日均线买入法
          <el-tooltip placement="top" :show-after="200">
            <template #content>
              <div class="tipBox">
                本页按<strong>MA60 斜率 + 短期均线多头</strong>扫描全 A 股，列出<strong>买入日（信号日次日）</strong>等于截止日的候选：
                信号日须满足 MA60 斜率<strong>前 3 日为负、当日为正</strong>，且当日 <strong>MA5&gt;MA10&gt;MA20</strong>；于次日<strong>开盘价</strong>买入。
                持仓后按收盘价 <strong>−8% 止损</strong>、<strong>+15% 止盈</strong>（先判止损）。数据不足或字段缺失则无信号。不构成投资建议。
              </div>
            </template>
            <el-icon class="titleHint" tabindex="0" aria-label="本页能力说明"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="subtitle">
          三负一正 + 当日均线多头；次日开盘买；止盈止损按收盘价监测。
        </div>
      </div>
      <div class="actions">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="截止日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="width: 150px; margin-right: 12px"
        />
        <el-button :loading="loading" @click="loadLatest">查询最新结果</el-button>
        <el-button :loading="loading" type="primary" @click="handleExecute">手动执行筛选</el-button>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">口径说明</div>
      </template>
      <div class="note">
        <p><strong>信号日：</strong>MA60 斜率 s(i−3)、s(i−2)、s(i−1) 均 &lt;0；s(i)&gt;0；且 MA5&gt;MA10&gt;MA20（0 不算正负）。</p>
        <p><strong>买入价：</strong>信号日<strong>下一交易日开盘价</strong>；表格「信号日」为 trigger_date。</p>
        <p><strong>卖出：</strong>自买入次日起逐日看收盘价；先止损（≤买入×0.92）再止盈（≥买入×1.15）。</p>
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
      <div v-else class="emptyMeta">尚未执行</div>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">今日候选列表</div>
      </template>

      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="stock_code" label="代码" width="110" />
        <el-table-column prop="stock_name" label="名称" min-width="120" />
        <el-table-column prop="exchange_type" label="交易所/板块" width="120" />
        <el-table-column prop="trigger_date" label="信号日" width="120" />
        <el-table-column label="买入日(次日)" width="130">
          <template #default="{ row }">{{ row.summary?.buy_date ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="买入价(开盘)" width="120" align="right">
          <template #default="{ row }">{{ fmtNum(row.summary?.buy_price) }}</template>
        </el-table-column>
        <el-table-column label="MA60斜率(前3+信号)" min-width="200">
          <template #default="{ row }">
            <span class="monoSm">{{ fmtFourSlopes(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="信号日MA5/10/20" min-width="140">
          <template #default="{ row }">
            {{ fmtNum(row.summary?.signal_day_ma5) }} /
            {{ fmtNum(row.summary?.signal_day_ma10) }} /
            {{ fmtNum(row.summary?.signal_day_ma20) }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty">
        截止日暂无符合条件的股票（也可能是数据未同步或 ma60 未回填）。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import type { ExecuteStrategyResponse, ExecutionSnapshot, StrategySelectionItem } from '@/api/strategies'
import { executeStrategy, getLatestStrategyResult } from '@/api/strategies'

const STRATEGY_ID = 'ma60_slope_buy'

const loading = ref(false)
const selectedDate = ref<string | null>(null)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])

function fmtNum(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(4)
}

function fmtFourSlopes(row: StrategySelectionItem) {
  const s = row.summary
  if (!s) return '-'
  const a = [s.slope_ma60_day_minus_3, s.slope_ma60_day_minus_2, s.slope_ma60_day_minus_1, s.slope_ma60_signal_day]
  if (a.every((x) => x === undefined || x === null)) return '-'
  return a.map((x) => (x === undefined || x === null ? '-' : Number(x).toFixed(4))).join(', ')
}

async function handleExecute() {
  loading.value = true
  try {
    const payload = selectedDate.value ? { as_of_date: selectedDate.value } : undefined
    const res: ExecuteStrategyResponse = await executeStrategy(STRATEGY_ID, payload)
    execution.value = res.execution
    items.value = res.items ?? []
    ElMessage.success(`执行成功：候选 ${items.value.length} 只`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { message?: string } | string } }; message?: string }
    const d = err?.response?.data?.detail
    const msg =
      typeof d === 'object' && d && 'message' in d ? (d as { message: string }).message : typeof d === 'string' ? d : err?.message
    ElMessage.error(msg || '执行失败')
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
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { code?: string } } } }
    if (err?.response?.data?.detail?.code === 'NOT_FOUND') {
      execution.value = null
      items.value = []
      return
    }
    const err2 = e as { response?: { data?: { detail?: { message?: string } } }; message?: string }
    ElMessage.error(err2?.response?.data?.detail?.message || err2?.message || '加载失败')
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
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1e3a5f;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.titleHint {
  cursor: help;
  color: #909399;
  font-size: 16px;
}
.tipBox {
  max-width: 380px;
  line-height: 1.55;
  font-size: 13px;
}
.subtitle {
  margin-top: 6px;
  color: #5b6b7c;
  font-size: 13px;
}
.cardTitle {
  font-weight: 600;
}
.note p {
  margin: 0 0 8px;
  line-height: 1.55;
  color: #3b4a5a;
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
.empty {
  margin-top: 12px;
  color: #8a98a8;
  font-size: 13px;
}
.monoSm {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
}
</style>
