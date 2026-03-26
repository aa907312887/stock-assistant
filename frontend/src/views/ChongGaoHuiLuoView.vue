<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">冲高回落战法</div>
        <div class="subtitle">
          筛选“开盘到最高涨幅 ≥10%、从最高回落 ≥3%、当日成交量 ≥ 前一日成交量 × 4/3、均线多头排列、MACD 红柱、且触发日为阳线”，且最近 10 个交易日无同等大阳线、并且前 10 天不存在单日涨幅超过 6% 的个股。
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
        当前系统暂无分时数据，“开盘买入/卖出”仅作为口径记录；本期页面只展示“今日符合冲高回落”的候选列表。
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
        <el-table-column label="大涨(开盘->最高)" min-width="160">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.big_rise_ratio) }}
          </template>
        </el-table-column>
        <el-table-column label="回落(最高->收盘)" min-width="160">
          <template #default="{ row }">
            {{ fmtPct(row.summary?.pullback_ratio) }}
          </template>
        </el-table-column>
        <el-table-column label="MACD红柱" width="120">
          <template #default="{ row }">
            {{ row.summary?.macd_hist ?? '-' }}
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
    const res: ExecuteStrategyResponse = await executeStrategy('chong_gao_hui_luo')
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
    const res = await getLatestStrategyResult('chong_gao_hui_luo')
    execution.value = res.execution
    items.value = res.items ?? []
  } catch (e: any) {
    // 没有已生成结果时不报错打断，只提示用户可手动执行
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

