<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">月 MACD 翻红</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>
                  本页筛选<strong>截止日</strong>下<strong>月线 MACD 绿转红</strong>的主板股票：对齐最近月柱
                  <strong>前一月绿（hist≤0）、当月红（hist&gt;0）</strong>，且截止日处于<strong>首个红柱月</strong>
                  （红柱月 bar 已落盘、截止日自然月不晚于红柱月）。
                </p>
                <p>不含 ±20% 止盈止损或月末卖出演算；区间回测/模拟请用「历史模拟」或「历史回测」同名策略。</p>
                <p>月线 bar 未落盘或 MACD 未计算时不入选。不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">
          与历史模拟/回测策略「月 MACD 翻红」买入信号口径一致（首红柱月）；可手动执行或查询最新落库结果。
        </div>
      </div>
      <div class="actions">
        <el-button :loading="loading" @click="loadLatest">查询最新结果</el-button>
        <el-button :loading="loading" type="primary" @click="handleExecute">手动执行筛选</el-button>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">口径说明</div>
      </template>
      <div class="note">
        <p>
          <strong>入选</strong>：截止日对齐最近月线 <code>trade_month_end ≤ 截止日</code>，且前一月
          <code>macd_hist ≤ 0</code>、当月 <code>macd_hist &gt; 0</code>。
          <strong>不入选</strong>：前月仍红柱、当月绿柱、非主板或 ST。
        </p>
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
        <div class="cardTitle">筛选结果（月 MACD 绿转红）</div>
      </template>

      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column width="118">
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
        <el-table-column prop="stock_name" label="名称" min-width="120" />
        <el-table-column prop="exchange" label="交易所" width="88" />
        <el-table-column prop="trigger_date" label="截止日" width="120" />
        <el-table-column label="前月柱" min-width="88" align="right">
          <template #default="{ row }">
            {{ fmtHist(row.summary?.macd_hist_prev_month) }}
          </template>
        </el-table-column>
        <el-table-column label="当月柱" min-width="88" align="right">
          <template #default="{ row }">
            {{ fmtHist(row.summary?.macd_hist_buy_month) }}
          </template>
        </el-table-column>
        <el-table-column label="红柱月" min-width="112">
          <template #default="{ row }">
            {{ row.summary?.buy_month_end ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column label="收盘" min-width="100" align="right">
          <template #default="{ row }">
            {{ fmtNum(row.summary?.close) }}
          </template>
        </el-table-column>
        <el-table-column label="信号" min-width="120">
          <template #default>
            <el-tag size="small" type="danger">月MACD绿转红</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty">
        截止日下暂无「月线 MACD 绿转红」的主板股票，或月线数据尚未同步。
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
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const STRATEGY_ID = 'yue_macd_fan_hong'

const loading = ref(false)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])

function fmtNum(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(4)
}

function fmtHist(v: unknown) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(4)
}

function eastMoneyUrl(row: StrategySelectionItem): string | null {
  return eastMoneyQuoteUrl(row.stock_code, row.exchange)
}

async function handleExecute() {
  loading.value = true
  try {
    const res: ExecuteStrategyResponse = await executeStrategy(STRATEGY_ID)
    execution.value = res.execution
    items.value = res.items ?? []
    ElMessage.success(`执行成功：候选 ${items.value.length} 只`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { message?: string } } }; message?: string }
    const msg = err?.response?.data?.detail?.message || err?.message || '执行失败'
    ElMessage.error(msg)
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
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { code?: string; message?: string } } }; message?: string }
    if (err?.response?.data?.detail?.code === 'NOT_FOUND') {
      execution.value = null
      items.value = []
      return
    }
    const msg = err?.response?.data?.detail?.message || err?.message || '加载失败'
    ElMessage.error(msg)
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
  gap: 6px;
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
  color: #1e3a5f;
  font-size: 12px;
  line-height: 1;
  cursor: default;
}
.tipBlock {
  max-width: 420px;
  line-height: 1.55;
  font-size: 13px;
}
.tipBlock p {
  margin: 0 0 6px;
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
.note p {
  margin: 6px 0;
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
  margin-top: 10px;
  color: #8a98a8;
  text-align: center;
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
