<template>
  <div class="sync-task-list">
    <el-card shadow="never">
      <template #header>
        <span>同步子任务</span>
        <el-popover placement="bottom-start" :width="380" trigger="hover">
          <template #reference>
            <el-link type="primary" class="capability-link">查看说明</el-link>
          </template>
          <div class="capability-content">
            <p><strong>本页展示什么</strong></p>
            <p>1) 定时任务在<strong>交易日</strong>会生成 <code>basic / daily / weekly / monthly</code> 四条 <strong>auto</strong> 子任务，执行过程写入本表。</p>
            <p>2) <code>sync_job_run</code> 为<strong>批次结果</strong>（行数汇总），本表为<strong>子任务状态</strong>（幂等键：交易日 + 类型 + 触发来源）。</p>
            <p>3) 手动「管理接口同步」仍走原编排器，不一定产生本表记录；仅展示已落库的子任务。</p>
            <p>4) 仅账号「杨佳兴」可访问。</p>
          </div>
        </el-popover>
      </template>

      <el-form :inline="true" class="filters" @submit.prevent="fetchTasks">
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" style="width: 140px">
            <el-option label="待执行" value="pending" />
            <el-option label="执行中" value="running" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="跳过" value="skipped" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="taskTypeFilter" clearable placeholder="全部" style="width: 120px">
            <el-option label="basic" value="basic" />
            <el-option label="daily" value="daily" />
            <el-option label="weekly" value="weekly" />
            <el-option label="monthly" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发">
          <el-select v-model="triggerFilter" clearable placeholder="全部" style="width: 120px">
            <el-option label="自动" value="auto" />
            <el-option label="手动" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易日从">
          <el-date-picker v-model="dateFrom" type="date" value-format="YYYY-MM-DD" placeholder="可选" />
        </el-form-item>
        <el-form-item label="到">
          <el-date-picker v-model="dateTo" type="date" value-format="YYYY-MM-DD" placeholder="可选" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="items" stripe border>
        <el-table-column prop="id" label="ID" width="80" align="right" />
        <el-table-column prop="trade_date" label="交易日" width="120" />
        <el-table-column prop="task_type" label="任务类型" width="100" />
        <el-table-column prop="trigger_type" label="触发" width="90" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="rows_affected" label="写入行数" width="100" align="right" />
        <el-table-column prop="batch_id" label="批次号" min-width="200" show-overflow-tooltip />
        <el-table-column prop="error_message" label="错误" min-width="200" show-overflow-tooltip />
        <el-table-column prop="started_at" label="开始" width="170" />
        <el-table-column prop="finished_at" label="结束" width="170" />
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="fetchTasks"
        @size-change="fetchTasks"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSyncTasks, type SyncTaskItem } from '@/api/syncJob'

const statusFilter = ref<string | undefined>()
const taskTypeFilter = ref<string | undefined>()
const triggerFilter = ref<string | undefined>()
const dateFrom = ref<string | undefined>()
const dateTo = ref<string | undefined>()
const loading = ref(false)
const items = ref<SyncTaskItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

async function fetchTasks() {
  loading.value = true
  try {
    const res = await getSyncTasks({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value,
      task_type: taskTypeFilter.value,
      trigger_type: triggerFilter.value,
      trade_date_from: dateFrom.value,
      trade_date_to: dateTo.value,
    })
    items.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '查询失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchTasks()
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.sync-task-list {
  min-height: 400px;
}
.capability-link {
  margin-left: 12px;
  font-size: 13px;
}
.capability-content p {
  margin: 6px 0;
  line-height: 1.5;
}
.filters {
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
