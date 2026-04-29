<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">破60日均线买入法</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>
                  本页为<strong>形态筛选</strong>，不是回测、不计算模拟盈亏：在<strong>截止日</strong>这根日线上判断「前
                  5 个交易日（有 K 的 5 根）收盘均低于当日 MA60，且截止日收盘高于当日 MA60」。
                </p>
                <p>
                  与 <code>ma60_five_day_break</code> 选股接口一致。交易日
                  <strong>17:22</strong>（上海时区）日线落库后自动落库，也可手动执行。
                </p>
                <p>若某日前 5 天中收在 MA60 之上，则该日不视为本策略的「五日在下」条件。不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">剔 ST。时间轴为库中连续日线，不补停牌行。买卖规则以「智能回测」中同策略为准。</div>
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
          列表中<strong>突破日</strong>与<strong>截止日期</strong>一致，表示<strong>该日已收盘站上年线（MA60）</strong>，且前
          5 根 K 的收盘均低于各自当日的 MA60。下一交易日若开盘买入、±8% 监测等，仅见于历史回测，不在本页演算。
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
        <div class="cardTitle">筛选结果</div>
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
        <el-table-column width="100">
          <template #header>
            <span>板块</span>
            <el-tooltip
              content="与股票基本信息一致：取 market 字段（如主板、创业板、科创板、北交所等）"
              placement="top"
            >
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            {{ row.market || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="trigger_date" label="突破日" width="120" />
        <el-table-column label="当日收盘" min-width="100">
          <template #default="{ row }">
            {{ fmtNum(row.summary?.signal_close) }}
          </template>
        </el-table-column>
        <el-table-column label="当日MA60" min-width="100">
          <template #default="{ row }">
            {{ fmtNum(row.summary?.signal_ma60) }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty">截止日下暂无符合「五日在下且当日突破」的股票，或数据尚未同步。</div>
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

const STRATEGY_ID = 'ma60_five_day_break'
const loading = ref(false)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])

function fmtNum(v: unknown) {
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
