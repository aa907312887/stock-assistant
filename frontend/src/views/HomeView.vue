<template>
  <div class="home">
    <header class="welcome">
      <h1 class="title">欢迎，{{ displayName }}</h1>
    </header>

    <div class="home-grid">
    <el-card class="hero" shadow="never">
      <template #header>
        <div class="hero-header">
          <div class="hero-title-row">
            <span class="hero-title">我的投资逻辑</span>
            <el-tooltip
              placement="top"
              :show-after="200"
            >
              <template #content>
                <div class="tip-block">
                  按技术面、基本面、消息面记录原则；权重表示侧重点。可在下方填写「重要感悟」（第1点、第2点…，存于扩展字段）。历史从侧栏查看。本页为自我警示，不构成投资建议。
                </div>
              </template>
              <el-icon class="tip-icon" :size="18"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </div>
      </template>

      <div v-if="loading" class="state-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <template v-else-if="!current">
        <el-empty description="">
          <template #image>
            <span />
          </template>
          <div class="empty-copy">
            <p class="empty-title">还没有记录投资逻辑</p>
            <p class="empty-desc">
              请填写技术面、基本面、消息面及权重；也可填写「重要感悟」第1点、第2点…。保存后会在下方显著展示。
            </p>
          </div>
          <el-button type="primary" @click="openFirstDialog">填写投资逻辑</el-button>
        </el-empty>
      </template>

      <template v-else>
        <p class="warn-line">勿忘初衷 · 勿因短期波动轻易改动原则</p>
        <div class="weights">
          <span>技术面 {{ current.weight_technical }}%</span>
          <span>基本面 {{ current.weight_fundamental }}%</span>
          <span>消息面 {{ current.weight_message }}%</span>
        </div>
        <div class="faces">
          <div class="face">
            <h3>技术面</h3>
            <p class="face-body">{{ current.technical_content || '—' }}</p>
          </div>
          <div class="face">
            <h3>基本面</h3>
            <p class="face-body">{{ current.fundamental_content || '—' }}</p>
          </div>
          <div class="face">
            <h3>消息面</h3>
            <p class="face-body">{{ current.message_content || '—' }}</p>
          </div>
        </div>
        <section class="insights-block" :class="{ 'is-empty': !insightsDisplay(current).length }">
          <h3 class="insights-title">重要感悟</h3>
          <ol v-if="insightsDisplay(current).length" class="insights-list">
            <li v-for="(line, idx) in insightsDisplay(current)" :key="idx" class="insights-item">
              {{ line }}
            </li>
          </ol>
          <p v-else class="insights-empty">
            暂无内容。点击下方「编辑」，在表单中填写「重要感悟」第1点、第2点…（保存时使用「保存为新版本」，会记为新的一条历史）。
          </p>
        </section>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="openNewVersionDialog(current)">编辑</el-button>
          <el-button size="large" text type="primary" @click="openHistoryDrawer">查看历史</el-button>
        </div>
      </template>
    </el-card>
    <MarketTemperatureCard class="temp-side" />
    </div>

    <el-drawer
      v-model="historyDrawerVisible"
      title="投资逻辑历史"
      direction="rtl"
      size="min(1200px, 96vw)"
      destroy-on-close
      @opened="onHistoryDrawerOpened"
    >
      <p class="drawer-hint">按新增时间倒序，仅浏览；含技术面、基本面、消息面与重要感悟全文，可横向滚动。</p>
      <div v-if="historyLoading" class="drawer-loading">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else class="history-table-wrap">
        <el-table :data="history" stripe class="history-table">
          <el-table-column prop="id" label="ID" width="56" fixed />
          <el-table-column label="新增时间" width="158" fixed>
            <template #default="{ row }">
              {{ formatDt(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="权重" width="108" fixed>
            <template #default="{ row }">
              {{ row.weight_technical }}/{{ row.weight_fundamental }}/{{ row.weight_message }}
            </template>
          </el-table-column>
          <el-table-column label="技术面" min-width="220">
            <template #default="{ row }">
              <div class="history-cell">{{ row.technical_content || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="基本面" min-width="220">
            <template #default="{ row }">
              <div class="history-cell">{{ row.fundamental_content || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="消息面" min-width="200">
            <template #default="{ row }">
              <div class="history-cell">{{ row.message_content || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="重要感悟" min-width="200">
            <template #default="{ row }">
              <div class="history-cell history-cell-insights">{{ insightsCellText(row) }}</div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="680px"
      destroy-on-close
      @closed="resetForm"
    >
      <p v-if="!isFirstSaveDialog" class="dialog-version-hint">
        每次保存都会<strong>新增一条记录</strong>（新版本），不会覆盖历史；首页始终展示「最后保存」的那一版。
      </p>
      <el-form label-width="100px">
        <el-form-item label="技术面">
          <el-input v-model="form.technical_content" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="基本面">
          <el-input v-model="form.fundamental_content" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="消息面">
          <el-input v-model="form.message_content" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="重要感悟">
          <div class="insights-form">
            <p class="insights-form-hint">
              选填。每一条为「第1点、第2点…」，保存进扩展字段；与三面、权重一起作为<strong>同一新版本</strong>落库。
            </p>
            <div v-for="(_, idx) in form.insights" :key="idx" class="insight-row">
              <span class="insight-label">第{{ idx + 1 }}点</span>
              <el-input v-model="form.insights[idx]" type="textarea" :rows="2" placeholder="选填" />
              <el-button
                v-if="form.insights.length > 1"
                link
                type="danger"
                @click="removeInsightRow(idx)"
              >
                删除
              </el-button>
            </div>
            <el-button type="primary" link @click="addInsightRow">增加一点</el-button>
          </div>
        </el-form-item>
        <el-form-item label="权重">
          <div class="weight-inputs">
            <span>技术面</span>
            <el-input-number v-model="form.weight_technical" :min="0" :max="100" :controls="true" />
            <span>基本面</span>
            <el-input-number v-model="form.weight_fundamental" :min="0" :max="100" :controls="true" />
            <span>消息面</span>
            <el-input-number v-model="form.weight_message" :min="0" :max="100" :controls="true" />
          </div>
          <p class="weight-sum">三者之和须为 100，当前合计：{{ weightSum }}</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">
          {{ isFirstSaveDialog ? '保存' : '保存为新版本' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import {
  createInvestmentLogicEntry,
  fetchInvestmentLogicCurrent,
  fetchInvestmentLogicEntries,
  type InvestmentLogicEntry,
  type InvestmentLogicPayload,
} from '@/api/investmentLogic'
import MarketTemperatureCard from '@/components/MarketTemperatureCard.vue'

const userStore = useUserStore()
const displayName = computed(() => userStore.user?.username ?? '用户')

const loading = ref(true)
const saving = ref(false)
const current = ref<InvestmentLogicEntry | null>(null)
const history = ref<InvestmentLogicEntry[]>([])
const historyDrawerVisible = ref(false)
const historyLoading = ref(false)

const dialogVisible = ref(false)
/** 是否首次在系统中保存（无任何历史时的第一次填写） */
const isFirstSaveDialog = ref(true)
/** 从预填行合并 extra_json（含 insights 与其它扩展键） */
const editExtraJsonSnapshot = ref<Record<string, unknown> | null>(null)

const dialogTitle = computed(() =>
  isFirstSaveDialog.value ? '填写投资逻辑' : '编辑投资逻辑',
)

const form = reactive({
  technical_content: '',
  fundamental_content: '',
  message_content: '',
  weight_technical: 34,
  weight_fundamental: 33,
  weight_message: 33,
  insights: [''] as string[],
})

const weightSum = computed(
  () => form.weight_technical + form.weight_fundamental + form.weight_message,
)

async function refreshCurrent() {
  const cur = await fetchInvestmentLogicCurrent()
  current.value = cur.data.entry
}

async function loadHistory() {
  const hist = await fetchInvestmentLogicEntries('created_desc')
  history.value = hist.data.items
}

async function refreshAfterMutation() {
  await refreshCurrent()
  if (historyDrawerVisible.value) {
    await loadHistory()
  }
}

function onHistoryDrawerOpened() {
  historyLoading.value = true
  loadHistory()
    .catch(() => {
      /* 错误由拦截器处理 */
    })
    .finally(() => {
      historyLoading.value = false
    })
}

function openHistoryDrawer() {
  historyDrawerVisible.value = true
}

function formatDt(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

/** 首页展示：非空感悟，按顺序编号为第1点、第2点… */
function insightsDisplay(entry: InvestmentLogicEntry | null): string[] {
  if (!entry?.extra_json || typeof entry.extra_json !== 'object' || Array.isArray(entry.extra_json)) {
    return []
  }
  const arr = (entry.extra_json as { insights?: unknown }).insights
  if (!Array.isArray(arr)) return []
  return arr.map((x) => String(x ?? '').trim()).filter(Boolean)
}

/** 历史表格「重要感悟」列：全文展示，分点换行 */
function insightsCellText(row: InvestmentLogicEntry): string {
  const lines = insightsDisplay(row)
  if (!lines.length) return '—'
  return lines.map((line, i) => `第${i + 1}点：${line}`).join('\n')
}

function resetForm() {
  form.technical_content = ''
  form.fundamental_content = ''
  form.message_content = ''
  form.weight_technical = 34
  form.weight_fundamental = 33
  form.weight_message = 33
  form.insights = ['']
  editExtraJsonSnapshot.value = null
}

/** 从已有条目预填表单（保存时仅 POST 插入新版本，不调用 PUT） */
function fillFormFromRow(row: InvestmentLogicEntry) {
  form.technical_content = row.technical_content || ''
  form.fundamental_content = row.fundamental_content || ''
  form.message_content = row.message_content || ''
  form.weight_technical = row.weight_technical
  form.weight_fundamental = row.weight_fundamental
  form.weight_message = row.weight_message
  editExtraJsonSnapshot.value =
    row.extra_json && typeof row.extra_json === 'object' && !Array.isArray(row.extra_json)
      ? { ...(row.extra_json as Record<string, unknown>) }
      : {}
  const raw = editExtraJsonSnapshot.value.insights
  if (Array.isArray(raw) && raw.length > 0) {
    form.insights = raw.map((x) => String(x ?? ''))
  } else {
    form.insights = ['']
  }
}

/** 首次使用：无任何记录时 */
function openFirstDialog() {
  isFirstSaveDialog.value = true
  resetForm()
  dialogVisible.value = true
}

/** 基于某条（当前或历史）修改后保存为新行 */
function openNewVersionDialog(row: InvestmentLogicEntry) {
  isFirstSaveDialog.value = false
  fillFormFromRow(row)
  dialogVisible.value = true
}

function addInsightRow() {
  form.insights.push('')
}

function removeInsightRow(idx: number) {
  if (form.insights.length <= 1) {
    form.insights[0] = ''
    return
  }
  form.insights.splice(idx, 1)
}

function buildExtraJson(): Record<string, unknown> | null {
  const cleaned = form.insights.map((s) => s.trim()).filter(Boolean)
  const merged: Record<string, unknown> = editExtraJsonSnapshot.value
    ? { ...editExtraJsonSnapshot.value }
    : {}
  if (cleaned.length > 0) {
    merged.insights = cleaned
  } else {
    delete merged.insights
  }
  return Object.keys(merged).length ? merged : null
}

function buildPayload(): InvestmentLogicPayload {
  return {
    technical_content: form.technical_content || null,
    fundamental_content: form.fundamental_content || null,
    message_content: form.message_content || null,
    weight_technical: form.weight_technical,
    weight_fundamental: form.weight_fundamental,
    weight_message: form.weight_message,
    extra_json: buildExtraJson(),
  }
}

async function submitForm() {
  const t = form.technical_content.trim()
  const f = form.fundamental_content.trim()
  const m = form.message_content.trim()
  if (!t && !f && !m) {
    ElMessage.warning('技术面、基本面、消息面至少填写一面')
    return
  }
  if (weightSum.value !== 100) {
    ElMessage.warning('三面权重之和须为 100')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    await createInvestmentLogicEntry(payload)
    ElMessage.success(isFirstSaveDialog.value ? '已保存' : '已保存为新版本')
    dialogVisible.value = false
    await refreshAfterMutation()
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (e as Error)?.message ||
      '保存失败'
    ElMessage.error(typeof msg === 'string' ? msg : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  userStore.loadUserFromStorage()
  loading.value = true
  try {
    await refreshCurrent()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home {
  max-width: 100%;
  min-height: calc(100vh - 120px);
}
.welcome {
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  color: #1e3a5f;
}
.hero {
  border-radius: 16px;
  border: 2px solid #c45656;
  background: linear-gradient(180deg, #fff5f5 0%, #ffffff 52%);
  box-shadow: 0 8px 32px rgba(196, 86, 86, 0.14);
}
.home-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  min-height: calc(100vh - 170px);
}
.temp-side {
  position: sticky;
  top: 8px;
  height: calc(100vh - 185px);
  overflow: auto;
}
.hero :deep(.el-card__header) {
  padding: 18px 28px;
  border-bottom: 1px solid rgba(196, 86, 86, 0.2);
}
.hero :deep(.el-card__body) {
  padding: 28px 28px 32px;
}
.hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hero-title {
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: #9f1239;
}
.tip-icon {
  cursor: help;
  color: #909399;
}
.tip-block {
  max-width: 320px;
  line-height: 1.5;
  font-size: 13px;
}
.warn-line {
  margin: 0 0 20px;
  font-weight: 700;
  color: #9f1239;
  font-size: 1.35rem;
  line-height: 1.45;
  letter-spacing: 0.02em;
}
.weights {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 24px;
  font-size: 1.1rem;
  color: #1d2129;
}
.weights span {
  padding: 8px 14px;
  background: #fde2e2;
  border-radius: 8px;
  font-weight: 700;
  font-size: 1.05rem;
}
.faces {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}
.face {
  padding: 18px 20px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.face h3 {
  margin: 0 0 12px;
  font-size: 1.15rem;
  font-weight: 700;
  color: #1e3a5f;
}
.face-body {
  margin: 0;
  white-space: pre-wrap;
  color: #1d2129;
  line-height: 1.75;
  font-size: 1.125rem;
  font-weight: 500;
}
.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.drawer-hint {
  margin: 0 0 12px;
  color: #909399;
  font-size: 13px;
}
.drawer-loading {
  padding: 12px 0;
}
.empty-copy {
  max-width: 420px;
  margin: 0 auto 16px;
  text-align: center;
}
.empty-title {
  margin: 0 0 8px;
  font-size: 1.2rem;
  font-weight: 600;
  color: #303133;
}
.empty-desc {
  margin: 0;
  color: #606266;
  line-height: 1.6;
  font-size: 1rem;
}
.weight-inputs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.weight-sum {
  margin: 8px 0 0;
  font-size: 13px;
  color: #909399;
}
.state-loading {
  padding: 8px 0;
}
.dialog-version-hint {
  margin: 0 0 16px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.55;
  color: #606266;
  background: #f4f4f5;
  border-radius: 8px;
}
.dialog-version-hint strong {
  color: #303133;
}
.insights-block {
  margin-bottom: 28px;
  padding: 20px 22px;
  border-radius: 12px;
  background: #fafafa;
  border: 1px dashed #dcdfe6;
}
.insights-block.is-empty {
  background: #fdfdfd;
}
.insights-title {
  margin: 0 0 14px;
  font-size: 1.15rem;
  font-weight: 700;
  color: #1e3a5f;
}
.insights-list {
  margin: 0;
  padding-left: 1.35rem;
  color: #1d2129;
  font-size: 1.05rem;
  line-height: 1.75;
  font-weight: 500;
}
.insights-item {
  margin-bottom: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}
.insights-empty {
  margin: 0;
  font-size: 1rem;
  line-height: 1.65;
  color: #606266;
}
.insights-form {
  width: 100%;
}
.insights-form-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.insight-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}
.insight-label {
  flex: 0 0 52px;
  padding-top: 6px;
  font-size: 13px;
  color: #606266;
}
.insight-row :deep(.el-textarea) {
  flex: 1;
}
.history-table-wrap {
  width: 100%;
  overflow-x: auto;
}
.history-table {
  min-width: 1180px;
}
.history-cell {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.55;
  font-size: 13px;
  color: #303133;
}
.history-cell-insights {
  line-height: 1.65;
}
@media (max-width: 1100px) {
  .home-grid {
    grid-template-columns: 1fr;
  }
  .temp-side {
    position: static;
  }
}
</style>
