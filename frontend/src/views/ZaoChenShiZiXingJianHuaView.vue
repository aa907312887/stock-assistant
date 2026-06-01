<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">
          早晨十字星（简化版）
          <el-tooltip placement="top" :show-after="200">
            <template #content>
              <div class="tipBox">
                本页按<strong>早晨十字星三日K线数值口径</strong>扫描，<strong>不包含</strong>主策略的跌势结构（均线空头、T−9…T−3 阴线统计等）；信号日收盘≤累计历史高<strong>80%</strong>；列表为<strong>当日开盘价买入</strong>的候选（多为形态完成日 T 的次日）。
                卖出：收盘监测<strong>−8% 止损</strong>与<strong>+10% 止盈</strong>，触发日均为<strong>收盘价</strong>成交（非主策略移动止盈）。不替代交易决策。
              </div>
            </template>
            <el-icon class="titleHint" tabindex="0" aria-label="本页能力说明"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="subtitle">
          三日形态数值同早晨十字星，无跌势结构过滤；收盘≤历史高80%；T+1开盘价买入；收盘≤买×0.92止损、收盘≥买×1.10止盈，触发日均按当日收盘价卖出。
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
        <p><strong>形态：</strong>T−2 大阴、T−1 锤头、T 阳线实体≥3%（与「早晨十字星」相同数值判定）；<strong>不要求</strong>T 日均线空头、不要求 T−9…T−3 阴线与累计跌幅。</p>
        <p><strong>价位：</strong>信号日收盘≤截至当日累计历史高价的 <strong>80%</strong>（主策略为 50%）。</p>
        <p><strong>买入：</strong>形态完成日次日<strong>开盘价</strong>；停牌则顺延至下一根有效日线。</p>
        <p><strong>止损：</strong>收盘价≤买入×0.92 → 按<strong>当日收盘价</strong>卖出（监测阈值 −8%）。</p>
        <p><strong>止盈：</strong>收盘价≥买入×1.10 → 按<strong>当日收盘价</strong>卖出（监测阈值 +10%）。</p>
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
        <el-table-column label="大阴日" min-width="100">
          <template #default="{ row }">
            {{ row.summary?.pattern_yin_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="锤头日" min-width="100">
          <template #default="{ row }">
            {{ row.summary?.pattern_hammer_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="阳线日" min-width="100">
          <template #default="{ row }">
            {{ row.summary?.pattern_yang_date ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="阳线实体涨幅" min-width="120">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.yang_body_gain_pct / 100) }}
          </template>
        </el-table-column>
        <el-table-column label="首日阴线跌幅" min-width="120">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.first_yin_drop_pct / 100) }}
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
    const res: ExecuteStrategyResponse = await executeStrategy('zao_chen_shi_zi_xing_jian_hua')
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
    const res = await getLatestStrategyResult('zao_chen_shi_zi_xing_jian_hua')
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
  max-width: 340px;
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
