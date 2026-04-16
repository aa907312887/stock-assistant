<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">
          红三兵
          <el-tooltip placement="top" :show-after="200">
            <template #content>
              <div class="tipBox">
                本页按<strong>红三兵</strong>规则（低价区、影线占振幅≤25%、第二三日开盘相对前收高开≤1%、第三日温和放量）扫描全市场，列出当日<strong>实际买入日</strong>等于截止日的候选；
                不替代交易决策，不保证收益。触发日为三连阳最后一日 T，买入为 T+1 开盘价。
              </div>
            </template>
            <el-icon class="titleHint" tabindex="0" aria-label="本页能力说明"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="subtitle">
          三连阳：实体每日1%～5%；上下影线各占振幅≤25%；T−1与T开盘相对前收高开≤1%；收盘逐级抬高；收盘≤历史高50%且低于MA60（若有）；
          第三日量≥前5日均×1.1；T+1开盘买入；止损8%×0.92；涨幅≥15%后从最高回落5%止盈。
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
        <p><strong>形态：</strong>连续三根阳线，实体每日 1%～5%；上、下影线各占当日振幅比例均≤25%；收盘价严格递增；第二、三根开盘价相对前一日收盘高开不超过 1%。</p>
        <p><strong>价位：</strong>完成日收盘不超过累计历史高价的 50%；若存在 MA60，则收盘仍低于 MA60。</p>
        <p><strong>量能：</strong>第三根成交量不低于前 5 个交易日（相对 T 的 T−7…T−3）均量的 1.1 倍。</p>
        <p><strong>买入：</strong>形态完成日次日开盘价；无下一根 K 线则不成交通。</p>
        <p><strong>卖出：</strong>与早晨十字星相同的 8% 止损与 15%+5% 移动止盈。</p>
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
        <el-table-column prop="stock_name" label="名称" min-width="140" />
        <el-table-column prop="exchange_type" label="交易所/板块" width="120" />
        <el-table-column prop="trigger_date" label="触发日(T)" width="120" />
        <el-table-column label="T−2 日" min-width="108">
          <template #default="{ row }">
            {{ row.summary?.pattern_bar_t_minus_2_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="T−1 日" min-width="108">
          <template #default="{ row }">
            {{ row.summary?.pattern_bar_t_minus_1_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="T 日" min-width="108">
          <template #default="{ row }">
            {{ row.summary?.pattern_bar_t_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="量/前5均" min-width="110">
          <template #default="{ row }">
            {{ row.summary?.third_day_volume_vs_prior5d_avg_ratio?.toFixed?.(2) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="收盘/历史高" min-width="120">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.close_to_cum_hist_high_ratio) }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty">
        今日暂无符合条件的股票（也可能是数据未同步或条件较严格）。
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

const loading = ref(false)
const execution = ref<ExecutionSnapshot | null>(null)
const items = ref<StrategySelectionItem[]>([])

function fmtPct(v: any) {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  if (Number.isNaN(n)) return '-'
  return `${(n * 100).toFixed(2)}%`
}

async function handleExecute() {
  loading.value = true
  try {
    const res: ExecuteStrategyResponse = await executeStrategy('di_wei_lian_yang')
    execution.value = res.execution
    items.value = res.items ?? []
    ElMessage.success(`执行成功：候选 ${items.value.length} 只`)
  } catch (e: any) {
    const msg = e?.response?.data?.detail?.message || e?.message || '执行失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function loadLatest() {
  loading.value = true
  try {
    const res = await getLatestStrategyResult('di_wei_lian_yang')
    execution.value = res.execution
    items.value = res.items ?? []
  } catch (e: any) {
    const code = e?.response?.data?.detail?.code
    if (code === 'NOT_FOUND') {
      execution.value = null
      items.value = []
      return
    }
    const msg = e?.response?.data?.detail?.message || e?.message || '加载失败'
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
  max-width: 320px;
  line-height: 1.5;
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
  margin-top: 12px;
  color: #8a98a8;
  font-size: 13px;
}
</style>
