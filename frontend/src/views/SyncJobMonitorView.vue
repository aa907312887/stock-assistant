<template>
  <div class="sync-job-monitor">
    <el-card shadow="never">
      <template #header>
        <span>同步批次（结果表）</span>
        <el-popover placement="bottom-start" :width="360" trigger="hover">
          <template #reference>
            <el-link type="primary" class="capability-link">查看当前产品能力</el-link>
          </template>
          <div class="capability-content">
            <p><strong>当前能力范围</strong></p>
            <p>1) 展示股票同步任务的批次、状态、写入行数与错误摘要。</p>
            <p>2) 详情中可查看模块级执行结果与批次扩展信息。</p>
            <p>3) 监控页面仅允许账号“杨佳兴”访问，其他用户不可查看。</p>
          </div>
        </el-popover>
      </template>

      <el-form :inline="true" class="filters" @submit.prevent="fetchJobs">
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" style="width: 160px">
            <el-option label="运行中" value="running" />
            <el-option label="成功" value="success" />
            <el-option label="部分失败" value="partial_failed" />
            <el-option label="失败" value="failed" />
            <el-option label="跳过" value="skipped" />
          </el-select>
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="modeFilter" clearable placeholder="全部" style="width: 160px">
            <el-option label="增量" value="incremental" />
            <el-option label="回灌" value="backfill" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="items" stripe border>
        <el-table-column prop="batch_id" label="批次号" min-width="180" />
        <el-table-column prop="job_mode" label="模式" width="100" />
        <el-table-column prop="status" label="状态" width="130" />
        <el-table-column prop="trade_date" label="业务日期" width="120" />
        <el-table-column prop="daily_rows" label="日线" width="90" align="right" />
        <el-table-column prop="weekly_rows" label="周线" width="90" align="right" />
        <el-table-column prop="monthly_rows" label="月线" width="90" align="right" />
        <el-table-column prop="report_rows" label="财报" width="90" align="right" />
        <el-table-column prop="failed_stock_count" label="失败股票数" width="110" align="right" />
        <el-table-column prop="error_message" label="错误摘要" min-width="200" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row.batch_id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="fetchJobs"
        @size-change="fetchJobs"
      />
    </el-card>

    <el-drawer v-model="drawerVisible" title="任务详情" size="45%">
      <pre class="detail-block">{{ detailText }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSyncJobDetail, getSyncJobs, type SyncJobItem } from '@/api/syncJob'

const statusFilter = ref<string | undefined>()
const modeFilter = ref<string | undefined>()
const loading = ref(false)
const items = ref<SyncJobItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const drawerVisible = ref(false)
const detailText = ref('')

async function fetchJobs() {
  loading.value = true
  try {
    const res = await getSyncJobs({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value,
      job_mode: modeFilter.value,
    })
    items.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '任务查询失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchJobs()
}

async function showDetail(batchId: string) {
  try {
    const res = await getSyncJobDetail(batchId)
    detailText.value = JSON.stringify(res.data, null, 2)
    drawerVisible.value = true
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '任务详情查询失败'
    ElMessage.error(msg)
  }
}

onMounted(() => {
  fetchJobs()
})
</script>

<style scoped>
.sync-job-monitor {
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

.detail-block {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
</style>
