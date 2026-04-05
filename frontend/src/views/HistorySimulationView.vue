<template>
  <div class="history-simulation">
    <SimulationConfigPanel @simulation-started="handleSimulationStarted" />

    <!-- 任务列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">模拟记录</span>
        </div>
      </template>
      <el-table :data="tasks" v-loading="loadingTasks" stripe style="width: 100%">
        <el-table-column prop="strategy_name" label="策略" min-width="140" />
        <el-table-column label="时间范围" width="200">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="statusType(row.status)"
              size="small"
            >{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="胜率" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.win_rate != null">{{ (row.win_rate * 100).toFixed(1) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="平均收益" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.avg_return != null" :class="row.avg_return >= 0 ? 'profit' : 'loss'">
              {{ (row.avg_return * 100).toFixed(2) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="交易数" width="80" align="right">
          <template #default="{ row }">{{ row.total_trades ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleViewDetail(row.task_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="taskPage"
          :page-size="taskPageSize"
          :total="taskTotal"
          layout="total, prev, pager, next"
          @current-change="loadTasks"
        />
      </div>
    </el-card>

    <!-- 结果详情 -->
    <SimulationResultDetail
      v-if="selectedTaskId"
      :task-id="selectedTaskId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import SimulationConfigPanel from '@/components/SimulationConfigPanel.vue'
import SimulationResultDetail from '@/components/SimulationResultDetail.vue'
import { getSimulationTasks, type SimulationTaskItem } from '@/api/simulation'

const selectedTaskId = ref<string | null>(null)
const tasks = ref<SimulationTaskItem[]>([])
const loadingTasks = ref(false)
const taskPage = ref(1)
const taskPageSize = 20
const taskTotal = ref(0)

let pollTimer: ReturnType<typeof setInterval> | null = null

function statusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'incomplete': return 'warning'
    case 'failed': return 'danger'
    case 'running': return 'info'
    default: return 'info'
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'completed': return '已完成'
    case 'incomplete': return '未完全平仓'
    case 'failed': return '失败'
    case 'running': return '运行中'
    default: return status
  }
}

function formatTime(t: string | null) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function loadTasks() {
  loadingTasks.value = true
  try {
    const res = await getSimulationTasks({ page: taskPage.value, page_size: taskPageSize })
    tasks.value = res.items
    taskTotal.value = res.total

    // 有运行中的任务时启动轮询
    const hasRunning = tasks.value.some((t) => t.status === 'running')
    if (hasRunning) {
      startPolling()
    } else {
      stopPolling()
    }
  } finally {
    loadingTasks.value = false
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    loadTasks()
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleSimulationStarted() {
  loadTasks()
}

function handleViewDetail(taskId: string) {
  selectedTaskId.value = taskId
}

onMounted(() => {
  loadTasks()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.history-simulation { display: flex; flex-direction: column; gap: 20px; }
.card-header { display: flex; align-items: center; gap: 8px; }
.title { font-weight: 600; font-size: 16px; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: flex-end; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
