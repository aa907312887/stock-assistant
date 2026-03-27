<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="title">回测记录</span>
        <el-tooltip content="历史回测任务列表，运行中的任务会自动刷新状态。" placement="top">
          <el-icon class="hint-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>
    <el-table :data="tasks" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="strategy_name" label="策略" width="140" />
      <el-table-column label="时间范围" width="220">
        <template #default="{ row }">
          {{ row.start_date }} ~ {{ row.end_date }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="胜率" width="90" align="right">
        <template #default="{ row }">
          {{ row.win_rate != null ? (row.win_rate * 100).toFixed(1) + '%' : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="总收益" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.total_return != null" :class="row.total_return >= 0 ? 'profit' : 'loss'">
            {{ row.total_return >= 0 ? '+' : '' }}{{ (row.total_return * 100).toFixed(2) }}%
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="交易数" prop="total_trades" width="80" align="right">
        <template #default="{ row }">{{ row.total_trades ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status !== 'running'"
            type="primary"
            link
            size="small"
            @click="emit('view-detail', row.task_id)"
          >
            查看
          </el-button>
          <span v-else class="running-text">执行中</span>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadTasks"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { getBacktestTasks, type BacktestTaskItem } from '@/api/backtest'

const emit = defineEmits<{
  'view-detail': [taskId: string]
}>()

const tasks = ref<BacktestTaskItem[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null

function statusType(status: string) {
  const map: Record<string, string> = {
    running: '',
    completed: 'success',
    incomplete: 'warning',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    running: '运行中',
    completed: '已完成',
    incomplete: '未完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatTime(dt: string) {
  if (!dt) return '-'
  return dt.replace('T', ' ').substring(0, 19)
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await getBacktestTasks({ page: page.value, page_size: pageSize })
    tasks.value = res.items
    total.value = res.total
    updatePolling()
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function updatePolling() {
  const hasRunning = tasks.value.some((t) => t.status === 'running')
  if (hasRunning && !pollTimer) {
    pollTimer = setInterval(loadTasks, 5000)
  } else if (!hasRunning && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function refresh() {
  page.value = 1
  loadTasks()
}

defineExpose({ refresh })

onMounted(loadTasks)

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
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
.profit {
  color: #f56c6c;
  font-weight: 500;
}
.loss {
  color: #67c23a;
  font-weight: 500;
}
.running-text {
  color: #909399;
  font-size: 12px;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
