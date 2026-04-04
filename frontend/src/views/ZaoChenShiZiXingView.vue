<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">早晨十字星</div>
        <div class="subtitle">
          跌势末期三根K线：T-2大阴(跌>=2%) + T-1锤头(相对T-2涨跌<=1%) + T阳线(实体>=3%)；
          前期T-9至T-3至少5阴且累计跌>=10%；T日跌势MA+收盘<=历史高50%（不强制放量）；
          站上MA5买入；止损8%固定x0.92；涨幅>=15%后从最高回落5%止盈。
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
        <p><strong>形态特征：</strong>连续三根K线组合（大阴线-锤头-阳线），信号触发日为第三根阳线日T。</p>
        <p><strong>跌势统计：</strong>T-9至T-3七日中至少五日阴线，且T-3相对T-9收盘累计跌幅至少10%。</p>
        <p><strong>买入规则：</strong>自T日起首次收盘价站上MA5时以收盘价买入。</p>
        <p><strong>止损规则：</strong>收盘<=买入价x0.92则固定按买入价x0.92卖出（亏损8%）。</p>
        <p><strong>止盈规则：</strong>涨幅达15%后启动移动止盈追踪，从最高价回落5%时按收盘价卖出。</p>
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
        <el-table-column prop="trigger_date" label="触发日" width="120" />
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
        <el-table-column label="前期累计跌幅" min-width="120">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.prior_t3_to_t9_close_to_close_return_pct / 100) }}
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
    const res: ExecuteStrategyResponse = await executeStrategy('zao_chen_shi_zi_xing')
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
    const res = await getLatestStrategyResult('zao_chen_shi_zi_xing')
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
