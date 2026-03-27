<template>
  <div class="history-backtest">
    <BacktestConfigPanel @backtest-started="handleBacktestStarted" />
    <BacktestTaskList
      ref="taskListRef"
      @view-detail="handleViewDetail"
    />
    <BacktestResultDetail
      v-if="selectedTaskId"
      :task-id="selectedTaskId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import BacktestConfigPanel from '@/components/BacktestConfigPanel.vue'
import BacktestTaskList from '@/components/BacktestTaskList.vue'
import BacktestResultDetail from '@/components/BacktestResultDetail.vue'

const selectedTaskId = ref<string | null>(null)
const taskListRef = ref<InstanceType<typeof BacktestTaskList> | null>(null)

function handleBacktestStarted() {
  taskListRef.value?.refresh()
}

function handleViewDetail(taskId: string) {
  selectedTaskId.value = taskId
}
</script>

<style scoped>
.history-backtest {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
