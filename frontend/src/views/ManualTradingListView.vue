<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="titleRow">
          <span class="title">手动模拟交易</span>
          <el-tooltip placement="bottom-start" :show-after="200">
            <template #content>
              <div class="tipBlock">
                <p>自定义标的名称，<strong>手动输入</strong>成交价与推进后收盘价；采用<strong>比例跟盘</strong>（不算股数）。</p>
                <p>数据<strong>落盘保存</strong>，可断点续作；与「历史模拟交易」（系统 A 股行情）相互独立。</p>
                <p>简化验算工具，不构成投资建议。</p>
              </div>
            </template>
            <span class="helpIcon" tabindex="0" aria-label="能力说明">?</span>
          </el-tooltip>
        </div>
        <div class="subtitle">手填价格快速验算总收益；支持按天/周/月/年推进时间。</div>
      </div>
      <el-button type="primary" @click="showCreate = true">新建模拟</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="items" stripe style="width: 100%">
        <el-table-column prop="asset_name" label="标的" min-width="120" />
        <el-table-column label="备注" min-width="100">
          <template #default="{ row }">{{ row.name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="起始日" width="110" />
        <el-table-column prop="current_date" label="当前模拟日" width="120" />
        <el-table-column label="持仓金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.position_value) }}</template>
        </el-table-column>
        <el-table-column label="总盈亏" width="120" align="right">
          <template #default="{ row }">
            <span :class="pnlClass(row.total_pnl)">
              {{ row.total_pnl >= 0 ? '+' : '' }}{{ formatMoney(row.total_pnl) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row)">
              {{ statusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              link
              type="primary"
              size="small"
              @click="enterSession(row.session_id)"
            >
              继续
            </el-button>
            <el-button link type="primary" size="small" @click="enterSession(row.session_id)">
              {{ row.status === 'ended' ? '复盘' : '详情' }}
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && items.length === 0" description="暂无记录，点击「新建模拟」开始" />
    </el-card>

    <el-dialog v-model="showCreate" title="新建手动模拟" width="480px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="标的名称" required>
          <el-input v-model="form.asset_name" placeholder="如：纳斯达克100" maxlength="100" />
        </el-form-item>
        <el-form-item label="起始日期" required>
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.name" placeholder="可选" maxlength="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createSession,
  deleteSession,
  listSessions,
  type SessionListItem,
} from '@/api/manualTrading'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const showCreate = ref(false)
const items = ref<SessionListItem[]>([])

const form = reactive({
  asset_name: '',
  start_date: '2001-01-01',
  name: '',
})

function formatMoney(v: number) {
  return v.toFixed(2)
}

function pnlClass(v: number) {
  return v >= 0 ? 'profit' : 'loss'
}

function statusTagType(row: SessionListItem): 'success' | 'warning' | 'info' {
  if (row.status === 'ended') return 'info'
  if (row.awaiting_reval) return 'warning'
  return 'success'
}

function statusLabel(row: SessionListItem) {
  if (row.status === 'ended') return '已结束'
  if (row.awaiting_reval) return '待录价'
  return '进行中'
}

async function loadList() {
  loading.value = true
  try {
    const res = await listSessions({ page_size: 50 })
    items.value = res.items
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '加载列表失败'))
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.asset_name.trim()) {
    ElMessage.warning('请输入标的名称')
    return
  }
  if (!form.start_date) {
    ElMessage.warning('请选择起始日期')
    return
  }
  creating.value = true
  try {
    const session = await createSession({
      asset_name: form.asset_name.trim(),
      start_date: form.start_date,
      name: form.name.trim() || undefined,
    })
    showCreate.value = false
    ElMessage.success('创建成功')
    router.push(`/backtest/manual-trading/${session.session_id}`)
  } catch (e: unknown) {
    ElMessage.error(getErrMsg(e, '创建失败'))
  } finally {
    creating.value = false
  }
}

function enterSession(sessionId: string) {
  router.push(`/backtest/manual-trading/${sessionId}`)
}

async function handleDelete(row: SessionListItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.asset_name}」的模拟记录？相关流水将一并删除。`,
      '删除确认',
      { type: 'warning' },
    )
    await deleteSession(row.session_id)
    ElMessage.success('已删除')
    await loadList()
  } catch (e: unknown) {
    if (e === 'cancel') return
    ElMessage.error(getErrMsg(e, '删除失败'))
  }
}

function getErrMsg(e: unknown, fallback: string) {
  const err = e as { response?: { data?: { detail?: { message?: string } | string } } }
  const detail = err.response?.data?.detail
  if (typeof detail === 'object' && detail?.message) return detail.message
  if (typeof detail === 'string') return detail
  return fallback
}

onMounted(loadList)
</script>

<style scoped>
.page {
  padding: 8px 4px 24px;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.titleRow {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 20px;
  font-weight: 600;
}
.subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.helpIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--el-border-color);
  font-size: 12px;
  cursor: help;
  color: var(--el-text-color-secondary);
}
.tipBlock p {
  margin: 0 0 6px;
  max-width: 280px;
  line-height: 1.5;
}
.tipBlock p:last-child {
  margin-bottom: 0;
}
.profit {
  color: #f56c6c;
}
.loss {
  color: #67c23a;
}
</style>
