<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">复利模拟</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>按<strong>固定年化收益率</strong>估算资产逐年变化；结果<strong>不落库</strong>，仅本次演算展示。</p>
                <p>一次性投入 / 每年定期投入 / 每年投入 N 年后再纯复利 M 年（第 N 年末起不再追加）。</p>
                <p>均按年化收益率在每年末计息；不考虑税费与波动，不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">输入参数后计算，弹窗展示各年资金明细（不保存历史记录）。</div>
      </div>
    </div>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="cardTitle">模拟参数</div>
      </template>
      <el-form :model="form" label-width="140px" class="form" @submit.prevent>
        <el-form-item label="投入方式">
          <el-radio-group v-model="form.mode" class="modeGroup">
            <el-radio value="lump_sum">一次性投入</el-radio>
            <el-radio value="annual_contribution">每年定期投入</el-radio>
            <el-radio value="annual_then_compound">每年投入 N 年再复利 M 年</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="amountLabel">
          <el-input-number
            v-model="form.principal"
            :min="0.01"
            :step="10000"
            :precision="2"
            controls-position="right"
            style="width: 240px"
          />
          <span class="unit">元</span>
        </el-form-item>
        <el-form-item label="年化收益率">
          <el-input-number
            v-model="form.annualRatePct"
            :min="0"
            :max="100"
            :step="0.5"
            :precision="2"
            controls-position="right"
            style="width: 240px"
          />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item v-if="form.mode !== 'annual_then_compound'" label="模拟年数">
          <el-input-number
            v-model="form.years"
            :min="1"
            :max="100"
            :step="1"
            controls-position="right"
            style="width: 240px"
          />
          <span class="unit">年</span>
        </el-form-item>
        <template v-else>
          <el-form-item label="投入年数 N">
            <el-input-number
              v-model="form.contributeYears"
              :min="1"
              :max="100"
              :step="1"
              controls-position="right"
              style="width: 240px"
            />
            <span class="unit">年（每年投入）</span>
          </el-form-item>
          <el-form-item label="复利年数 M">
            <el-input-number
              v-model="form.compoundYears"
              :min="1"
              :max="100"
              :step="1"
              controls-position="right"
              style="width: 240px"
            />
            <span class="unit">年（不再投入）</span>
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" @click="handleCalculate">开始计算</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="960px"
      destroy-on-close
      align-center
    >
      <div v-if="result" class="summary">
        <div class="summaryItem">
          <span class="k">累计投入</span>
          <span class="v">{{ fmtMoney(result.totalInvested) }}</span>
        </div>
        <div class="summaryItem">
          <span class="k">累计收益</span>
          <span class="v" :class="result.totalGain >= 0 ? 'profit' : 'loss'">
            {{ fmtMoney(result.totalGain) }}
          </span>
        </div>
        <div class="summaryItem">
          <span class="k">{{ result.totalYears }} 年后资产</span>
          <span class="v highlight">{{ fmtMoney(result.finalBalance) }}</span>
        </div>
      </div>

      <el-table :data="result?.rows ?? []" stripe max-height="480" style="width: 100%">
        <el-table-column prop="year" label="年份" width="72" align="center" />
        <el-table-column
          v-if="form.mode === 'annual_then_compound'"
          label="阶段"
          width="88"
          align="center"
        >
          <template #default="{ row }">
            <el-tag v-if="row.phase === 'contribute'" size="small" type="warning">投入期</el-tag>
            <el-tag v-else-if="row.phase === 'compound'" size="small" type="info">复利期</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="期初资产" min-width="120" align="right">
          <template #default="{ row }">{{ fmtMoney(row.opening) }}</template>
        </el-table-column>
        <el-table-column label="本年投入" min-width="120" align="right">
          <template #default="{ row }">{{ fmtMoney(row.contribution) }}</template>
        </el-table-column>
        <el-table-column label="本年收益" min-width="120" align="right">
          <template #default="{ row }">
            <span :class="row.gain >= 0 ? 'profit' : 'loss'">{{ fmtMoney(row.gain) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="期末资产" min-width="130" align="right">
          <template #default="{ row }">{{ fmtMoney(row.closing) }}</template>
        </el-table-column>
        <el-table-column label="累计投入" min-width="120" align="right">
          <template #default="{ row }">{{ fmtMoney(row.cumulativeInvested) }}</template>
        </el-table-column>
        <el-table-column label="累计收益" min-width="120" align="right">
          <template #default="{ row }">
            <span :class="row.cumulativeGain >= 0 ? 'profit' : 'loss'">
              {{ fmtMoney(row.cumulativeGain) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  computeCompoundInterest,
  type CompoundMode,
  type CompoundSimResult,
} from '@/utils/compoundInterest'

const DEFAULT_FORM = {
  mode: 'lump_sum' as CompoundMode,
  principal: 1_000_000,
  annualRatePct: 10,
  years: 30,
  contributeYears: 10,
  compoundYears: 30,
}

const form = reactive({ ...DEFAULT_FORM })
const dialogVisible = ref(false)
const result = ref<CompoundSimResult | null>(null)

const amountLabel = computed(() => {
  if (form.mode === 'lump_sum') return '初始金额'
  return '每年投入金额'
})

const dialogTitle = computed(() => {
  if (form.mode === 'lump_sum') {
    return `复利模拟结果 · 一次性投入 · ${form.years} 年 · 年化 ${form.annualRatePct}%`
  }
  if (form.mode === 'annual_contribution') {
    return `复利模拟结果 · 每年定期投入 · ${form.years} 年 · 年化 ${form.annualRatePct}%`
  }
  return (
    `复利模拟结果 · 每年投入 ${form.contributeYears} 年 + 复利 ${form.compoundYears} 年` +
    ` · 年化 ${form.annualRatePct}%`
  )
})

function fmtMoney(v: number) {
  return v.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function handleCalculate() {
  if (form.principal <= 0) {
    ElMessage.warning('投入金额须大于 0')
    return
  }
  if (form.annualRatePct < 0) {
    ElMessage.warning('年化收益率不能为负')
    return
  }

  if (form.mode === 'annual_then_compound') {
    if (form.contributeYears < 1 || !Number.isInteger(form.contributeYears)) {
      ElMessage.warning('投入年数 N 须为不小于 1 的整数')
      return
    }
    if (form.compoundYears < 1 || !Number.isInteger(form.compoundYears)) {
      ElMessage.warning('复利年数 M 须为不小于 1 的整数')
      return
    }
    if (form.contributeYears + form.compoundYears > 100) {
      ElMessage.warning('N + M 合计不超过 100 年')
      return
    }
    result.value = computeCompoundInterest({
      mode: form.mode,
      principal: form.principal,
      annualRatePct: form.annualRatePct,
      contributeYears: form.contributeYears,
      compoundYears: form.compoundYears,
    })
  } else {
    if (form.years < 1 || !Number.isInteger(form.years)) {
      ElMessage.warning('模拟年数须为不小于 1 的整数')
      return
    }
    result.value = computeCompoundInterest({
      mode: form.mode,
      principal: form.principal,
      annualRatePct: form.annualRatePct,
      years: form.years,
    })
  }
  dialogVisible.value = true
}

function handleReset() {
  Object.assign(form, DEFAULT_FORM)
  result.value = null
  dialogVisible.value = false
}
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
}
.cardTitle {
  font-weight: 600;
}
.form {
  max-width: 560px;
}
.modeGroup {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.unit {
  margin-left: 8px;
  color: #6b7b8c;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f5f8fc;
  border-radius: 8px;
}
.summaryItem {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.summaryItem .k {
  font-size: 12px;
  color: #6b7b8c;
}
.summaryItem .v {
  font-size: 18px;
  font-weight: 600;
  color: #1e3a5f;
}
.summaryItem .v.highlight {
  color: var(--el-color-primary);
}
.profit {
  color: #c45656;
}
.loss {
  color: #3d8b40;
}
</style>
