<template>
  <div class="paper-trading-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <span class="title">历史模拟交易</span>
      <el-tooltip placement="right" :show-after="200">
        <template #content>
          <div style="max-width: 260px; line-height: 1.6">
            选择历史节点逐日推进，手动买卖股票，体验 A 股 T+1 规则。<br />
            每日分开盘/收盘两个时间节点，图表数据截止到当前模拟日期，不展示未来信息。
          </div>
        </template>
        <el-icon class="help-icon"><QuestionFilled /></el-icon>
      </el-tooltip>
      <el-button type="primary" @click="showCreateDialog = true" style="margin-left: auto">
        开始新模拟
      </el-button>
    </div>

    <!-- 会话列表 -->
    <el-card shadow="hover">
      <el-table :data="store.sessionList" v-loading="listLoading" stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }">{{ row.name || '未命名' }}</template>
        </el-table-column>
        <el-table-column label="起始日期" width="110">
          <template #default="{ row }">{{ row.start_date }}</template>
        </el-table-column>
        <el-table-column label="当前日期" width="130">
          <template #default="{ row }">
            {{ row.current_date }}
            <el-tag size="small" :type="row.current_phase === 'open' ? 'warning' : 'success'" style="margin-left: 4px">
              {{ row.current_phase === 'open' ? '开盘' : '收盘' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总资产" width="120" align="right">
          <template #default="{ row }">
            ¥{{ row.total_asset.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="盈亏" width="120" align="right">
          <template #default="{ row }">
            <span :class="(row.total_asset - row.initial_cash) >= 0 ? 'profit' : 'loss'">
              {{ (row.total_asset - row.initial_cash) >= 0 ? '+' : '' }}{{ (row.total_asset - row.initial_cash).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="enterSession(row.session_id)" v-if="row.status === 'active'">
              继续
            </el-button>
            <el-button link type="primary" size="small" @click="showSessionDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!listLoading && store.sessionList.length === 0" description="暂无模拟记录，点击「开始新模拟」创建" />
    </el-card>

    <!-- 会话详情：总盈亏 + 按股票汇总 + 查看成交明细 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="'模拟详情 - ' + (selectedSession?.name || '未命名')"
      width="820px"
      class="session-detail-dialog"
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <template v-if="detailSession && !detailLoading">
          <div class="detail-hero">
            <div class="hero-label">本模拟总盈亏（相对初始资金）</div>
            <div
              class="hero-value"
              :class="detailSession.total_profit_loss >= 0 ? 'profit' : 'loss'"
            >
              {{ detailSession.total_profit_loss >= 0 ? '+' : '' }}¥{{
                detailSession.total_profit_loss.toFixed(2)
              }}
              <span class="hero-pct">
                （{{ (detailSession.total_profit_loss_pct * 100).toFixed(2) }}%）
              </span>
            </div>
            <div class="hero-sub">
              初始资金 ¥{{ detailSession.initial_cash.toFixed(2) }} · 总资产 ¥{{
                detailSession.total_asset.toFixed(2)
              }}
              · 可用 ¥{{ detailSession.available_cash.toFixed(2) }} · 模拟日 {{ detailSession.current_date }}
              {{ detailSession.current_phase === 'open' ? '开盘' : '收盘' }}
            </div>
          </div>

          <el-alert
            v-if="ordersTotalCount > 500"
            type="warning"
            show-icon
            :closable="false"
            class="detail-alert"
            title="本会话成交笔数超过 500，下列明细仅加载前 500 笔；汇总仍基于已加载数据，完整对账请增大单页上限或分页拉取。"
          />

          <div class="detail-section-title">按股票汇总</div>
          <p class="detail-hint">
            盈亏与涨跌幅口径：持仓中为相对成本的浮动盈亏比例；已清仓为已实现盈亏比例（与模拟内订单一致）。
          </p>
          <el-table :data="stockSummaryRows" stripe size="small" max-height="360" empty-text="暂无交易记录">
            <el-table-column label="股票" min-width="140">
              <template #default="{ row }">
                <span class="stk-name">{{ row.stock_name || row.stock_code }}</span>
                <span class="stk-code">{{ row.stock_code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="盈亏（元）" align="right" width="120">
              <template #default="{ row }">
                <span :class="row.profit_loss >= 0 ? 'profit' : 'loss'">
                  {{ row.profit_loss >= 0 ? '+' : '' }}{{ row.profit_loss.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="涨跌幅" align="right" width="100">
              <template #default="{ row }">
                <span :class="row.profit_pct >= 0 ? 'profit' : 'loss'">
                  {{ row.profit_pct >= 0 ? '+' : '' }}{{ (row.profit_pct * 100).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openStockOps(row)">
                  查看详细操作
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-dialog>

    <!-- 单只股票：成交时间线 -->
    <el-dialog
      v-model="showStockOpsDialog"
      :title="stockOpsTitle"
      width="760px"
      destroy-on-close
      append-to-body
      class="stock-ops-dialog"
    >
      <el-table :data="stockOpsRows" stripe size="small" max-height="420">
        <el-table-column label="操作时间" width="168">
          <template #default="{ row }">{{ fmtCreatedAt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="trade_date" label="模拟交易日" width="112" />
        <el-table-column prop="order_type" label="类型" width="72">
          <template #default="{ row }">
            <el-tag :type="row.order_type === 'buy' ? 'danger' : 'success'" size="small">
              {{ row.order_type === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" align="right" width="88">
          <template #default="{ row }">{{ row.price.toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" align="right" width="72" />
        <el-table-column prop="amount" label="成交金额" align="right" width="108">
          <template #default="{ row }">¥{{ row.amount.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="commission" label="手续费" align="right" width="88">
          <template #default="{ row }">¥{{ row.commission.toFixed(2) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 创建会话弹窗 -->
    <el-dialog v-model="showCreateDialog" title="开始新模拟" width="420px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="90px" @submit.prevent>
        <el-form-item label="起始日期" required>
          <el-date-picker
            v-model="createForm.start_date"
            type="date"
            placeholder="选择历史日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            :disabled-date="disabledDate"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="初始资金" required>
          <el-input-number
            v-model="createForm.initial_cash"
            :min="1000"
            :step="10000"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="会话名称">
          <el-input v-model="createForm.name" placeholder="可选，如「2021年牛市复盘」" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">开始模拟</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { usePaperTradingStore } from '@/stores/paperTrading'
import { paperTradingApi } from '@/api/paperTrading'
import type { OrderResponse, SessionListItem, SessionResponse } from '@/api/paperTrading'

/** 列表页「详情」里按股票汇总的一行 */
type StockSummaryRow = {
  stock_code: string
  stock_name: string | null
  status: 'holding' | 'closed' | 'orders_only'
  profit_loss: number
  profit_pct: number
}

const router = useRouter()
const store = usePaperTradingStore()

const listLoading = ref(false)
const showCreateDialog = ref(false)
const creating = ref(false)
const showDetailDialog = ref(false)
const detailLoading = ref(false)
const selectedSession = ref<SessionListItem | null>(null)
const detailSession = ref<SessionResponse | null>(null)
const allOrdersAsc = ref<OrderResponse[]>([])
const ordersTotalCount = ref(0)
const stockSummaryRows = ref<StockSummaryRow[]>([])

const showStockOpsDialog = ref(false)
const stockOpsTitle = ref('')
const stockOpsRows = ref<OrderResponse[]>([])

const createForm = ref({
  start_date: '',
  initial_cash: 100000,
  name: '',
})

function normalizeTsCode(code: string): string {
  const s = (code || '').trim()
  if (!s) return s
  const i = s.lastIndexOf('.')
  if (i >= 0) {
    return `${s.slice(0, i).toUpperCase()}.${s.slice(i + 1).toUpperCase()}`
  }
  return s.toUpperCase()
}

function pnlFromOrders(orders: OrderResponse[], canonicalCode: string): { pl: number; pct: number } {
  const n = normalizeTsCode(canonicalCode)
  let buy = 0
  let sell = 0
  for (const o of orders) {
    if (normalizeTsCode(o.stock_code) !== n) continue
    const ot = (o.order_type || '').toLowerCase()
    if (ot === 'buy') buy += o.amount + o.commission
    else if (ot === 'sell') sell += o.amount - o.commission
  }
  const pl = sell - buy
  const pct = buy > 0 ? pl / buy : 0
  return { pl, pct }
}

function buildStockSummaryRows(session: SessionResponse, orders: OrderResponse[]): StockSummaryRow[] {
  const map = new Map<string, StockSummaryRow>()

  for (const p of session.positions) {
    const key = normalizeTsCode(p.stock_code)
    map.set(key, {
      stock_code: p.stock_code,
      stock_name: p.stock_name,
      status: 'holding',
      profit_loss: p.profit_loss ?? 0,
      profit_pct: p.profit_loss_pct ?? 0,
    })
  }
  for (const c of session.closed_stocks ?? []) {
    const key = normalizeTsCode(c.stock_code)
    map.set(key, {
      stock_code: c.stock_code,
      stock_name: c.stock_name,
      status: 'closed',
      profit_loss: c.realized_profit_loss ?? 0,
      profit_pct: c.realized_profit_loss_pct ?? 0,
    })
  }

  const seenOrphan = new Set<string>()
  for (const o of orders) {
    const key = normalizeTsCode(o.stock_code)
    if (map.has(key) || seenOrphan.has(key)) continue
    seenOrphan.add(key)
    const { pl, pct } = pnlFromOrders(orders, o.stock_code)
    map.set(key, {
      stock_code: o.stock_code,
      stock_name: o.stock_name,
      status: 'orders_only',
      profit_loss: pl,
      profit_pct: pct,
    })
  }

  return Array.from(map.values()).sort(
    (a, b) => Math.abs(b.profit_loss) - Math.abs(a.profit_loss)
  )
}

function statusLabel(s: StockSummaryRow['status']): string {
  if (s === 'holding') return '持仓中'
  if (s === 'closed') return '已清仓'
  return '仅成交'
}

function statusTagType(s: StockSummaryRow['status']): 'success' | 'warning' | 'info' {
  if (s === 'holding') return 'warning'
  if (s === 'closed') return 'info'
  return 'success'
}

function fmtCreatedAt(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}

function openStockOps(row: StockSummaryRow) {
  const n = normalizeTsCode(row.stock_code)
  stockOpsRows.value = allOrdersAsc.value.filter(o => normalizeTsCode(o.stock_code) === n)
  stockOpsTitle.value = `成交明细 — ${row.stock_name || row.stock_code}（${row.stock_code}）`
  showStockOpsDialog.value = true
}

// 禁用今天及以后的日期
const disabledDate = (d: Date) => d >= new Date()

onMounted(async () => {
  listLoading.value = true
  await store.loadSessionList()
  listLoading.value = false
})

async function handleCreate() {
  if (!createForm.value.start_date) {
    ElMessage.warning('请选择起始日期')
    return
  }
  creating.value = true
  try {
    const res = await paperTradingApi.createSession({
      start_date: createForm.value.start_date,
      initial_cash: createForm.value.initial_cash,
      name: createForm.value.name || undefined,
    })
    showCreateDialog.value = false
    router.push({ name: 'paper-trading-session', params: { sessionId: res.data.session_id } })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || '创建失败，请检查日期是否为交易日')
  } finally {
    creating.value = false
  }
}

function enterSession(sessionId: string) {
  router.push({ name: 'paper-trading-session', params: { sessionId } })
}

async function showSessionDetail(row: SessionListItem) {
  selectedSession.value = row
  showDetailDialog.value = true
  detailLoading.value = true
  detailSession.value = null
  allOrdersAsc.value = []
  stockSummaryRows.value = []
  ordersTotalCount.value = 0
  try {
    const [sessRes, ordRes] = await Promise.all([
      paperTradingApi.getSession(row.session_id),
      paperTradingApi.listOrders(row.session_id, { page_size: 500, sort: 'asc' }),
    ])
    detailSession.value = sessRes.data
    allOrdersAsc.value = ordRes.data.items
    ordersTotalCount.value = ordRes.data.total
    stockSummaryRows.value = buildStockSummaryRows(sessRes.data, ordRes.data.items)
  } catch {
    ElMessage.error('加载会话详情失败')
    showDetailDialog.value = false
  } finally {
    detailLoading.value = false
  }
}
</script>

<style scoped>
.paper-trading-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.help-icon {
  color: #909399;
  cursor: pointer;
  font-size: 16px;
}
.profit { color: #f56c6c; }
.loss  { color: #67c23a; }

.detail-hero {
  margin-bottom: 16px;
  padding: 16px 18px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}
.hero-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.hero-value {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.hero-pct {
  font-size: 16px;
  font-weight: 600;
  margin-left: 6px;
}
.hero-sub {
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
}
.detail-alert {
  margin-bottom: 12px;
}
.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.detail-hint {
  font-size: 12px;
  color: #909399;
  margin: 0 0 10px;
  line-height: 1.5;
}
.stk-name {
  font-weight: 500;
  display: block;
}
.stk-code {
  font-size: 11px;
  color: #909399;
}
</style>
