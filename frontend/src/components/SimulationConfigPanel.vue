<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">模拟配置</span>
        <el-tooltip
          content="选择策略与时间范围，发起历史模拟。系统将在后台执行，完成后可查看收益率与成功率统计。历史模拟不进行资金/仓位仿真，统计全部符合条件的闭仓样本；与历史回测的仓位仿真相比，笔数可能更多。"
          placement="top"
        >
          <el-icon class="hint-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>
    <el-form :inline="true" :model="form" class="config-form">
      <el-form-item label="策略">
        <el-select v-model="form.strategy_id" placeholder="请选择策略" style="width: 200px">
          <el-option
            v-for="s in strategies"
            :key="s.strategy_id"
            :label="s.name"
            :value="s.strategy_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="开始日期">
        <el-date-picker
          v-model="form.start_date"
          type="date"
          placeholder="选择开始日期"
          :disabled-date="disabledStartDate"
          value-format="YYYY-MM-DD"
          style="width: 160px"
        />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker
          v-model="form.end_date"
          type="date"
          placeholder="选择结束日期"
          :disabled-date="disabledEndDate"
          value-format="YYYY-MM-DD"
          style="width: 160px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleStart">
          开始模拟
        </el-button>
      </el-form-item>
    </el-form>
    <div v-if="dataRange.min_date" class="data-range-hint">
      可用数据范围：{{ dataRange.min_date }} ~ {{ dataRange.max_date }}
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listStrategies, type StrategySummary } from '@/api/strategies'
import { getDataRange } from '@/api/backtest'
import { runSimulation } from '@/api/simulation'

const emit = defineEmits<{
  'simulation-started': []
}>()

const strategies = ref<StrategySummary[]>([])
const dataRange = reactive({ min_date: '', max_date: '' })
const form = reactive({
  strategy_id: '',
  start_date: '',
  end_date: '',
})
const loading = ref(false)

onMounted(async () => {
  try {
    const [strategyRes, rangeRes] = await Promise.all([listStrategies(), getDataRange()])
    strategies.value = strategyRes.items
    if (strategies.value.length > 0) {
      form.strategy_id = strategies.value[0].strategy_id
    }
    dataRange.min_date = rangeRes.min_date || ''
    dataRange.max_date = rangeRes.max_date || ''
  } catch (e) {
    ElMessage.error('加载配置数据失败')
  }
})

function disabledStartDate(time: Date) {
  if (!dataRange.min_date || !dataRange.max_date) return false
  const d = time.getTime()
  const min = new Date(dataRange.min_date).getTime()
  const max = new Date(dataRange.max_date).getTime()
  if (d < min || d > max) return true
  if (form.end_date) {
    return d >= new Date(form.end_date).getTime()
  }
  return false
}

function disabledEndDate(time: Date) {
  if (!dataRange.min_date || !dataRange.max_date) return false
  const d = time.getTime()
  const min = new Date(dataRange.min_date).getTime()
  const max = new Date(dataRange.max_date).getTime()
  if (d < min || d > max) return true
  if (form.start_date) {
    return d <= new Date(form.start_date).getTime()
  }
  return false
}

async function handleStart() {
  if (!form.strategy_id) {
    ElMessage.warning('请选择策略')
    return
  }
  if (!form.start_date || !form.end_date) {
    ElMessage.warning('请选择完整的时间范围')
    return
  }

  loading.value = true
  try {
    await runSimulation({
      strategy_id: form.strategy_id,
      start_date: form.start_date,
      end_date: form.end_date,
    })
    ElMessage.success('模拟任务已创建，后台执行中')
    emit('simulation-started')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    ElMessage.error(detail?.message || '发起模拟失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; }
.title { font-weight: 600; font-size: 16px; }
.hint-icon { color: #909399; cursor: pointer; }
.config-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px; }
.data-range-hint { margin-top: 8px; font-size: 12px; color: #909399; }
</style>
