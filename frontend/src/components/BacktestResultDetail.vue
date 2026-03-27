<template>
  <el-card shadow="hover" v-loading="loading">
    <template #header>
      <div class="card-header">
        <span class="title">回测结果详情</span>
        <el-tooltip placement="top">
          <template #content>
            <div style="max-width: 320px">
              绩效指标基于已平仓交易计算。收益率 = 各笔 (卖出价 - 买入价) / 买入价 之和，不含手续费与复利。<br/>
              大盘温度统计展示不同市场温度下的策略表现差异。
            </div>
          </template>
          <el-icon class="hint-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
        <el-button v-if="detail" text @click="$emit('close')">关闭</el-button>
      </div>
    </template>

    <template v-if="detail && detail.status === 'failed'">
      <el-alert title="回测执行失败" type="error" :closable="false" show-icon />
    </template>

    <template v-else-if="detail && detail.report">
      <template v-if="detail.report.total_trades === 0">
        <el-empty description="该时间范围内无符合策略条件的交易" />
      </template>
      <template v-else>
        <!-- 盈亏结论 -->
        <div class="conclusion-banner" :class="detail.report.total_return >= 0 ? 'positive' : 'negative'">
          {{ detail.report.conclusion }}
        </div>

        <!-- 核心指标网格 -->
        <div class="metrics-grid">
          <div class="metric-item">
            <div class="metric-label">总交易</div>
            <div class="metric-value">{{ detail.report.total_trades }}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">胜率</div>
            <div class="metric-value">{{ (detail.report.win_rate * 100).toFixed(1) }}%</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">总收益率</div>
            <div class="metric-value" :class="detail.report.total_return >= 0 ? 'profit' : 'loss'">
              {{ detail.report.total_return >= 0 ? '+' : '' }}{{ (detail.report.total_return * 100).toFixed(2) }}%
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">平均收益</div>
            <div class="metric-value">{{ (detail.report.avg_return * 100).toFixed(2) }}%</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">最大盈利</div>
            <div class="metric-value profit">+{{ (detail.report.max_win * 100).toFixed(2) }}%</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">最大亏损</div>
            <div class="metric-value loss">{{ (detail.report.max_loss * 100).toFixed(2) }}%</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">盈利笔数</div>
            <div class="metric-value">{{ detail.report.win_trades }}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">亏损笔数</div>
            <div class="metric-value">{{ detail.report.lose_trades }}</div>
          </div>
          <div class="metric-item" v-if="detail.report.unclosed_count > 0">
            <div class="metric-label">未平仓</div>
            <div class="metric-value">{{ detail.report.unclosed_count }}</div>
          </div>
          <div class="metric-item" v-if="detail.report.skipped_count > 0">
            <div class="metric-label">跳过</div>
            <div class="metric-value">{{ detail.report.skipped_count }}</div>
          </div>
        </div>

        <!-- 大盘温度分组统计 -->
        <div v-if="detail.report.temp_level_stats.length > 0" class="section">
          <h4 class="section-title">
            大盘温度分组统计
            <el-tooltip content="展示策略在不同大盘温度级别下的表现差异" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <el-table :data="detail.report.temp_level_stats" stripe size="small">
            <el-table-column prop="level" label="温度级别" width="100" />
            <el-table-column prop="total" label="交易数" width="80" align="right" />
            <el-table-column label="胜率" width="90" align="right">
              <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="平均收益" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                  {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="detail.report.exchange_stats.length > 0" class="section">
          <h4 class="section-title">
            交易所分组统计
            <el-tooltip content="按 SSE/SZSE/BSE 分组，展示交易次数、胜率与平均收益" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <el-table :data="detail.report.exchange_stats" stripe size="small">
            <el-table-column prop="name" label="交易所" width="120" />
            <el-table-column prop="total" label="交易数" width="80" align="right" />
            <el-table-column label="胜率" width="90" align="right">
              <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="平均收益" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                  {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="detail.report.market_stats.length > 0" class="section">
          <h4 class="section-title">
            板块分组统计
            <el-tooltip content="按主板/创业板/科创板等板块分组，展示交易次数、胜率与平均收益" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <el-table :data="detail.report.market_stats" stripe size="small">
            <el-table-column prop="name" label="板块" width="120" />
            <el-table-column prop="total" label="交易数" width="80" align="right" />
            <el-table-column label="胜率" width="90" align="right">
              <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="平均收益" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.avg_return >= 0 ? 'profit' : 'loss'">
                  {{ row.avg_return >= 0 ? '+' : '' }}{{ (row.avg_return * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 交易明细 -->
        <div class="section">
          <h4 class="section-title">交易明细</h4>
          <div class="trade-filters">
            <el-select v-model="tradeFilters.exchange" clearable placeholder="按交易所筛选" style="width: 160px">
              <el-option
                v-for="ex in exchangeOptions"
                :key="ex.value"
                :label="ex.label"
                :value="ex.value"
              />
            </el-select>
            <el-select v-model="tradeFilters.market_temp_level" clearable placeholder="按温度筛选" style="width: 160px">
              <el-option
                v-for="lvl in tempLevelOptions"
                :key="lvl"
                :label="lvl"
                :value="lvl"
              />
            </el-select>
            <el-select v-model="tradeFilters.market" clearable placeholder="按板块筛选" style="width: 180px">
              <el-option
                v-for="m in marketOptions"
                :key="m"
                :label="m"
                :value="m"
              />
            </el-select>
            <el-button @click="handleTradeFilterSearch">筛选</el-button>
            <el-button @click="handleTradeFilterReset">重置</el-button>
          </div>
          <el-table :data="trades" stripe size="small" v-loading="tradesLoading">
            <el-table-column prop="stock_code" label="代码" width="100" />
            <el-table-column prop="stock_name" label="名称" width="90" />
            <el-table-column prop="buy_date" label="买入日" width="110" />
            <el-table-column label="买入价" width="90" align="right">
              <template #default="{ row }">{{ row.buy_price.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="卖出日" width="110">
              <template #default="{ row }">{{ row.sell_date || '-' }}</template>
            </el-table-column>
            <el-table-column label="卖出价" width="90" align="right">
              <template #default="{ row }">{{ row.sell_price != null ? row.sell_price.toFixed(2) : '-' }}</template>
            </el-table-column>
            <el-table-column label="收益率" width="90" align="right">
              <template #default="{ row }">
                <span v-if="row.return_rate != null" :class="row.return_rate >= 0 ? 'profit' : 'loss'">
                  {{ row.return_rate >= 0 ? '+' : '' }}{{ (row.return_rate * 100).toFixed(2) }}%
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="交易所" width="90">
              <template #default="{ row }">{{ row.exchange || '-' }}</template>
            </el-table-column>
            <el-table-column label="板块" width="110">
              <template #default="{ row }">{{ row.market || '-' }}</template>
            </el-table-column>
            <el-table-column label="温度" width="70">
              <template #default="{ row }">{{ row.market_temp_level || '-' }}</template>
            </el-table-column>
            <el-table-column prop="trade_type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag :type="row.trade_type === 'closed' ? 'success' : 'warning'" size="small">
                  {{ row.trade_type === 'closed' ? '已平仓' : '未平仓' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination" v-if="tradesTotal > tradesPageSize">
            <el-pagination
              v-model:current-page="tradesPage"
              :page-size="tradesPageSize"
              :total="tradesTotal"
              layout="prev, pager, next, total"
              @current-change="loadTrades"
            />
          </div>
        </div>

        <!-- 口径说明 -->
        <div v-if="detail.assumptions" class="section assumptions">
          <h4 class="section-title">
            口径与假设
            <el-tooltip content="回测所用的数据口径与简化假设" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <div class="assumption-tags">
            <el-tag
              v-for="(val, key) in detail.assumptions"
              :key="key"
              type="info"
              size="small"
              class="assumption-tag"
            >
              {{ key }}: {{ val }}
            </el-tag>
          </div>
        </div>
      </template>
    </template>

    <template v-else-if="detail && detail.status === 'running'">
      <el-alert title="回测执行中，请稍候..." type="info" :closable="false" show-icon />
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import {
  getBacktestTaskDetail,
  getBacktestTrades,
  type BacktestTaskDetailResponse,
  type BacktestTradeItem,
} from '@/api/backtest'

const props = defineProps<{
  taskId: string
}>()

defineEmits<{
  close: []
}>()

const detail = ref<BacktestTaskDetailResponse | null>(null)
const loading = ref(false)
const trades = ref<BacktestTradeItem[]>([])
const tradesLoading = ref(false)
const tradesPage = ref(1)
const tradesPageSize = 50
const tradesTotal = ref(0)
const tradeFilters = ref<{ exchange?: string; market_temp_level?: string; market?: string }>({})

const tempLevelOptions = computed(() => {
  const levels = detail.value?.report?.temp_level_stats?.map((x) => x.level) ?? []
  return levels.filter(Boolean)
})

const marketOptions = computed(() => {
  const markets = detail.value?.report?.market_stats?.map((x) => x.name) ?? []
  return markets.filter(Boolean)
})

const exchangeOptions = computed(() => {
  const exchanges = detail.value?.report?.exchange_stats?.map((x) => x.name).filter(Boolean) ?? []
  return exchanges.map((v) => ({
    value: v,
    label: v === 'SSE' ? '上交所(SSE)' : v === 'SZSE' ? '深交所(SZSE)' : v === 'BSE' ? '北交所(BSE)' : v,
  }))
})

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getBacktestTaskDetail(props.taskId)
    tradesPage.value = 1
    await loadTrades()
  } finally {
    loading.value = false
  }
}

async function loadTrades() {
  tradesLoading.value = true
  try {
    const res = await getBacktestTrades(props.taskId, {
      market_temp_level: tradeFilters.value.market_temp_level,
      market: tradeFilters.value.market,
      exchange: tradeFilters.value.exchange,
      page: tradesPage.value,
      page_size: tradesPageSize,
    })
    trades.value = res.items
    tradesTotal.value = res.total
  } finally {
    tradesLoading.value = false
  }
}

function handleTradeFilterSearch() {
  tradesPage.value = 1
  loadTrades()
}

function handleTradeFilterReset() {
  tradeFilters.value = {}
  tradesPage.value = 1
  loadTrades()
}

watch(() => props.taskId, loadDetail, { immediate: true })
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
  flex: 1;
}
.hint-icon {
  color: #909399;
  cursor: pointer;
}
.hint-icon-sm {
  color: #909399;
  cursor: pointer;
  font-size: 14px;
  margin-left: 4px;
}

.conclusion-banner {
  padding: 16px 20px;
  border-radius: 8px;
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 20px;
}
.conclusion-banner.positive {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}
.conclusion-banner.negative {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.metric-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.profit {
  color: #f56c6c;
}
.loss {
  color: #67c23a;
}

.section {
  margin-top: 24px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.trade-filters {
  margin-bottom: 10px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.assumptions {
  margin-top: 20px;
}
.assumption-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.assumption-tag {
  font-size: 12px;
}
</style>
