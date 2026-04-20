<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">回测配置</span>
        <el-tooltip
          content="选择策略与时间范围，发起历史回测。系统将在后台执行，完成后可查看绩效报告与交易明细。"
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
      <el-form-item>
        <template #label>
          <span>持仓金额(元)</span>
          <el-tooltip placement="top">
            <template #content>
              <div style="max-width: 280px">
                每笔目标名义本金（全仓一只）。<strong>所有策略</strong>回测均按此金额参与单仓位资金仿真；亏损后下次开仓前由补仓池补足至该金额（用尽则可能跳过）。
              </div>
            </template>
            <el-icon class="hint-icon label-hint"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <el-input-number
          v-model="form.position_amount"
          :min="1"
          :max="1000000000"
          :step="10000"
          :controls="true"
          style="width: 160px"
        />
      </el-form-item>
      <el-form-item>
        <template #label>
          <span>补仓金额(元)</span>
          <el-tooltip placement="top">
            <template #content>
              <div style="max-width: 280px">
                补仓池初始额度；开仓前现金不足时划入，盈利可回流池中。<strong>仅恐慌回落法</strong>在日历上允许「卖出当日再买入他股」；其它策略须卖出日次日及以后才能再开仓。
              </div>
            </template>
            <el-icon class="hint-icon label-hint"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <el-input-number
          v-model="form.reserve_amount"
          :min="0"
          :max="1000000000"
          :step="10000"
          :controls="true"
          style="width: 160px"
        />
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
        <template #label>
          <span>标的（可选）</span>
          <el-tooltip placement="top">
            <template #content>
              <div style="max-width: 320px; line-height: 1.6">
                仅在选择<strong>均线金叉</strong>策略时生效；可填一个或多个 ts_code（逗号/空格分隔），回测将只扫描这些标的。<br />
                支持<strong>指数</strong>（如 399300.SZ）或<strong>个股</strong>；<strong>不可在同一任务中混填个股与指数</strong>。指数行情来自指数日线表，与全市场个股回测数据源不同。<br />
                其它策略请留空，仍按全市场回测。
              </div>
            </template>
            <el-icon class="hint-icon label-hint"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <el-input
          v-model="form.symbols_text"
          placeholder="例：399300.SZ 或 000001.SZ,600000.SH"
          clearable
          style="width: 280px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleStart">
          开始回测
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
import { runBacktest, getDataRange, type RunBacktestRequest } from '@/api/backtest'

const emit = defineEmits<{
  'backtest-started': []
}>()

const strategies = ref<StrategySummary[]>([])
const dataRange = reactive({ min_date: '', max_date: '' })
const form = reactive({
  strategy_id: '',
  start_date: '',
  end_date: '',
  position_amount: 100_000,
  reserve_amount: 100_000,
  /** 逗号/空格分隔，解析为 symbols 数组提交 */
  symbols_text: '',
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
  if (form.position_amount == null || form.position_amount < 1) {
    ElMessage.warning('持仓金额须大于 0')
    return
  }
  if (form.reserve_amount == null || form.reserve_amount < 0) {
    ElMessage.warning('补仓金额不能为负')
    return
  }

  loading.value = true
  try {
    const parts = form.symbols_text
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    const payload: RunBacktestRequest = {
      strategy_id: form.strategy_id,
      start_date: form.start_date,
      end_date: form.end_date,
      position_amount: form.position_amount,
      reserve_amount: form.reserve_amount,
    }
    if (parts.length) payload.symbols = parts
    await runBacktest(payload)
    ElMessage.success('回测任务已创建，后台执行中')
    emit('backtest-started')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    ElMessage.error(detail?.message || '发起回测失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.hint-icon {
  color: #909399;
  cursor: pointer;
}
.label-hint {
  margin-left: 4px;
  vertical-align: middle;
}
.config-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
}
.data-range-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
