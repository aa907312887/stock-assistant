<template>
  <div class="personal-holdings">
    <el-card shadow="never">
      <template #header>
        <div class="card-header-row">
          <div class="card-header-left">
            <span class="page-title">个人持仓</span>
            <span class="sub-hint">管理持仓、操作记录与复盘（不构成投资建议）</span>
            <el-popover placement="bottom-start" :width="460" trigger="click">
              <template #reference>
                <el-link type="primary" class="capability-link">查看说明</el-link>
              </template>
              <div class="capability-content">
                <p><strong>能力范围</strong></p>
                <p>1）一笔交易 = 从<strong>建仓</strong>到<strong>清仓</strong>；加仓/减仓记在操作记录里，不是新交易。</p>
                <p>2）<strong>股票胜率</strong>按整笔已实现盈亏；<strong>操作胜率</strong>按每条操作自评，可与整笔盈亏无关。</p>
                <p>3）参考市值来自已同步日线收盘价，无数据时显示「—」，不伪造价格。</p>
              </div>
            </el-popover>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="main-tabs">
        <el-tab-pane label="当前持仓" name="open">
          <div class="toolbar">
            <el-button type="primary" @click="openDialogOpen">建仓</el-button>
            <el-button @click="showClosedInOpen = !showClosedInOpen">
              {{ showClosedInOpen ? '隐藏已清仓' : '显示已清仓' }}
            </el-button>
            <el-button @click="loadOpen">刷新</el-button>
          </div>
          <el-table v-loading="loadingOpen || loadingClosed" :data="openTabItems" stripe border style="width: 100%">
            <el-table-column prop="stock_code" label="代码" width="110" />
            <el-table-column prop="stock_name" label="名称" width="120" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.is_closed" type="info" size="small">已清仓</el-tag>
                <el-tag v-else type="success" size="small">持仓中</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="持仓数量" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.total_qty) }}</template>
            </el-table-column>
            <el-table-column label="成本价" width="100" align="right">
              <template #default="{ row }">{{ fmtNum(row.avg_cost) }}</template>
            </el-table-column>
            <el-table-column label="参考收盘" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.has_ref_price">{{ fmtNum(row.ref_close) }}</span>
                <el-tooltip v-else content="暂无同步日线数据" placement="top">
                  <span class="muted">—</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="参考市值" width="120" align="right">
              <template #default="{ row }">
                <span v-if="row.has_ref_price">{{ fmtNum(row.ref_market_value) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="参考盈亏" width="120" align="right">
              <template #default="{ row }">
                <span v-if="row.is_closed" :class="pnlClass(row.ref_pnl)">{{ fmtNum(row.ref_pnl) }}</span>
                <span v-else-if="row.has_ref_price" :class="pnlClass(row.ref_pnl)">{{ fmtNum(row.ref_pnl) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.is_closed && row.ref_pnl_pct !== null && row.ref_pnl_pct !== undefined">
                  {{ rateStr(row.ref_pnl_pct) }}
                </span>
                <span v-else-if="!row.is_closed && row.has_ref_price">{{ rateStr(row.ref_pnl_pct) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <template v-if="!row.is_closed">
                  <el-button link type="primary" size="small" @click="openDialogAdd(row)">加仓</el-button>
                  <el-button link type="primary" size="small" @click="openDialogReduce(row)">减仓</el-button>
                  <el-button link type="warning" size="small" @click="openDialogClose(row)">清仓</el-button>
                  <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
                </template>
                <template v-else>
                  <el-button link type="primary" size="small" @click="openDrawer(row.trade_id)">查看详情</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loadingOpen && !loadingClosed && openTabItems.length === 0" description="暂无持仓，点击建仓开始" />
        </el-tab-pane>

        <el-tab-pane label="已完结与复盘" name="closed">
          <div class="toolbar">
            <el-button @click="loadClosed">刷新</el-button>
          </div>
          <el-table v-loading="loadingClosed" :data="closedItems" stripe border style="width: 100%">
            <el-table-column prop="stock_code" label="代码" width="110" />
            <el-table-column prop="stock_name" label="名称" width="120" />
            <el-table-column label="清仓时间" width="170">
              <template #default="{ row }">{{ row.closed_at || '—' }}</template>
            </el-table-column>
            <el-table-column label="整笔盈亏" width="120" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.realized_pnl)">{{ fmtNum(row.realized_pnl) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="复盘/图片" width="100">
              <template #default="{ row }">
                {{ row.review_text ? '有文字' : '' }} {{ row.image_count ? row.image_count + '图' : '' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openDrawer(row.trade_id)">详情与复盘</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="统计" name="stats">
          <el-row :gutter="16" v-loading="loadingStats">
            <el-col :span="24">
              <el-card shadow="hover" class="stat-card">
                <template #header>整体收益情况（已完结交易）</template>
                <p class="stat-line">
                  总盈利：
                  <span class="pnl-up">{{ fmtNum(stats?.overall_pnl.total_profit) }}</span>
                </p>
                <p class="stat-line">
                  总亏损：
                  <span class="pnl-down">{{ fmtNum(stats?.overall_pnl.total_loss) }}</span>
                </p>
                <p class="stat-line">
                  净收益：
                  <span :class="pnlClass(stats?.overall_pnl.net_pnl)">{{ fmtNum(stats?.overall_pnl.net_pnl) }}</span>
                </p>
                <p class="stat-rate">净收益占比：{{ rateStr(stats?.overall_pnl.net_pnl_rate) }}</p>
                <p class="stat-hint">占比口径：净收益 /（总盈利 + |总亏损|）</p>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="hover" class="stat-card">
                <template #header>股票胜率（整笔盈亏）</template>
                <p class="stat-line">盈利笔数：{{ stats?.stock_win_rate.won ?? '—' }}</p>
                <p class="stat-line">亏损笔数：{{ stats?.stock_win_rate.lost ?? '—' }}</p>
                <p class="stat-line">持平：{{ stats?.stock_win_rate.breakeven ?? '—' }}</p>
                <p class="stat-line">合计笔数：{{ stats?.stock_win_rate.total ?? '—' }}</p>
                <p class="stat-rate">胜率：{{ rateStr(stats?.stock_win_rate.rate) }}</p>
                <p class="stat-hint">分母为已完结交易笔数</p>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="hover" class="stat-card">
                <template #header>操作胜率（操作自评）</template>
                <p class="stat-line">好操作：{{ stats?.operation_win_rate.good ?? '—' }}</p>
                <p class="stat-line">坏操作：{{ stats?.operation_win_rate.bad ?? '—' }}</p>
                <p class="stat-line">未评价：{{ stats?.operation_win_rate.unrated ?? '—' }}</p>
                <p class="stat-rate">占比：{{ rateStr(stats?.operation_win_rate.rate) }}</p>
                <p class="stat-hint">分母仅含已评价（好+坏），未评价不计入分母</p>
              </el-card>
            </el-col>
          </el-row>
          <el-button class="mt" @click="loadStats">刷新统计</el-button>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 建仓 -->
    <el-dialog v-model="dlgOpen" title="建仓" width="440px" @closed="resetForm">
      <el-form :model="formOpen" label-width="100px">
        <el-form-item label="股票代码/名称" required>
          <el-autocomplete
            v-model="formOpen.stock_keyword"
            :fetch-suggestions="queryStockSuggestions"
            clearable
            placeholder="输入代码或名称，如 600000.SH / 浦发银行"
            style="width: 100%"
            @select="onSelectStockSuggestion"
          />
        </el-form-item>
        <el-form-item label="成交日期" required>
          <el-date-picker v-model="formOpen.op_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="formOpen.qty" :min="0.0001" :step="100" />
        </el-form-item>
        <el-form-item label="价格" required>
          <el-input-number v-model="formOpen.price" :min="0.0001" :precision="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOpen">确定</el-button>
      </template>
    </el-dialog>

    <!-- 加仓/减仓 -->
    <el-dialog v-model="dlgOp" :title="opMode === 'add' ? '加仓' : '减仓'" width="440px">
      <el-form :model="formOp" label-width="100px">
        <el-form-item label="成交日期" required>
          <el-date-picker v-model="formOp.op_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="formOp.qty" :min="0.0001" :step="100" />
        </el-form-item>
        <el-form-item label="价格" required>
          <el-input-number v-model="formOp.price" :min="0.0001" :precision="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgOp = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOp">确定</el-button>
      </template>
    </el-dialog>

    <!-- 清仓 -->
    <el-dialog v-model="dlgClose" title="清仓" width="480px">
      <p class="warn-text">清仓将结束本笔交易，并生成已完结记录。请确认卖出数量与价格。</p>
      <el-form :model="formClose" label-width="100px">
        <el-form-item label="成交日期" required>
          <el-date-picker v-model="formClose.op_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="卖出数量" required>
          <el-input-number v-model="formClose.qty" :min="0.0001" :step="100" />
        </el-form-item>
        <el-form-item label="价格" required>
          <el-input-number v-model="formClose.price" :min="0.0001" :precision="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgClose = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitClose">确认清仓</el-button>
      </template>
    </el-dialog>

    <!-- 已完结详情 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="min(560px, 92vw)" destroy-on-close>
      <div v-loading="loadingDetail">
        <template v-if="detail">
          <p class="drawer-pnl" :class="pnlClass(detail.trade.realized_pnl)">
            整笔盈亏：{{ fmtNum(detail.trade.realized_pnl) }}
          </p>
          <p class="drawer-pnl-rate">
            盈亏比例：{{ rateStr(detail.trade.realized_pnl_rate) }}
          </p>
          <h4>操作时间线</h4>
          <el-timeline>
            <el-timeline-item
              v-for="o in detail.operations"
              :key="o.id"
              :timestamp="o.op_date"
              placement="top"
            >
              <div class="op-line">
                <span>{{ opTypeLabel(o.op_type) }}</span>
                <span>数量 {{ fmtNum(o.qty) }} × 价 {{ fmtNum(o.price) }}</span>
              </div>
              <div class="op-rating">
                <span>自评：</span>
                <el-select
                  :model-value="o.operation_rating ?? undefined"
                  placeholder="未评"
                  clearable
                  size="small"
                  style="width: 120px"
                  @update:model-value="(v: string | undefined) => onOpRating(o.id, v ?? null)"
                >
                  <el-option label="好操作" value="good" />
                  <el-option label="坏操作" value="bad" />
                </el-select>
              </div>
            </el-timeline-item>
          </el-timeline>
          <h4>复盘</h4>
          <el-input
            v-model="reviewDraft"
            type="textarea"
            :rows="5"
            placeholder="心得、教训…"
          />
          <el-button class="mt" type="primary" size="small" :loading="savingReview" @click="saveReview">保存复盘文字</el-button>
          <h4 class="mt">图片</h4>
          <el-upload
            :http-request="onUploadImage"
            :show-file-list="false"
            accept="image/jpeg,image/png,image/webp"
            multiple
          >
            <el-button type="primary" size="small">上传图片</el-button>
          </el-upload>
          <div v-if="imagePreviewUrls.length" class="img-grid">
            <div v-for="(u, i) in imagePreviewUrls" :key="i" class="img-cell">
              <el-image
                :src="u"
                :preview-src-list="imagePreviewUrls"
                :initial-index="i"
                preview-teleported
                fit="cover"
                style="width: 100px; height: 100px"
              />
              <el-button
                class="img-delete-btn"
                type="danger"
                size="small"
                circle
                :loading="deletingImageId === detail?.images?.[i]?.id"
                @click="onDeleteImage(i)"
              >
                ×
              </el-button>
            </div>
          </div>
          <p v-else-if="detail?.images?.length === 0" class="muted">暂无图片</p>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import type { UploadRequestOptions } from 'element-plus'
import * as api from '@/api/portfolio'
import type { ClosedTradeItem, OpenTradeItem, StatsResponse, TradeDetail } from '@/api/portfolio'
import { getStockBasicList } from '@/api/stockBasic'

const activeTab = ref('open')
const loadingOpen = ref(false)
const loadingClosed = ref(false)
const loadingStats = ref(false)
const loadingDetail = ref(false)
const openItems = ref<OpenTradeItem[]>([])
const closedItems = ref<ClosedTradeItem[]>([])
const showClosedInOpen = ref(false)
const stats = ref<StatsResponse | null>(null)

const dlgOpen = ref(false)
const dlgOp = ref(false)
const dlgClose = ref(false)
const submitting = ref(false)
const opMode = ref<'add' | 'reduce'>('add')
const currentTradeId = ref<number | null>(null)

const formOpen = ref({
  stock_keyword: '',
  op_date: '',
  qty: 100 as number,
  price: 0 as number,
})
const formOp = ref({
  op_date: '',
  qty: 100 as number,
  price: 0 as number,
})
const formClose = ref({
  op_date: '',
  qty: 0 as number,
  price: 0 as number,
})

const drawerVisible = ref(false)
const detail = ref<TradeDetail | null>(null)
const reviewDraft = ref('')
const savingReview = ref(false)
const imagePreviewUrls = ref<string[]>([])
const deletingImageId = ref<number | null>(null)
const drawerTradeId = ref<number | null>(null)

const drawerTitle = computed(() => {
  if (!detail.value) return '交易详情'
  return `${detail.value.trade.stock_code} ${detail.value.trade.stock_name || ''}`
})

type OpenTabItem = OpenTradeItem & { is_closed: boolean }

const openTabItems = computed<OpenTabItem[]>(() => {
  const openRows: OpenTabItem[] = openItems.value.map((x) => ({ ...x, is_closed: false }))
  if (!showClosedInOpen.value) return openRows
  const closedRows: OpenTabItem[] = closedItems.value.map((x) => ({
    trade_id: x.trade_id,
    stock_code: x.stock_code,
    stock_name: x.stock_name,
    total_qty: 0,
    avg_cost: null,
    ref_close: null,
    ref_close_date: null,
    ref_market_value: null,
    ref_pnl: x.realized_pnl,
    ref_pnl_pct: x.realized_pnl_rate,
    has_ref_price: false,
    is_closed: true,
  }))
  return [...openRows, ...closedRows]
})

function fmtNum(v: number | null | undefined) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

function pnlClass(v: number | null | undefined) {
  if (v === null || v === undefined) return ''
  return v >= 0 ? 'pnl-up' : 'pnl-down'
}

function rateStr(r: number | null | undefined) {
  if (r === null || r === undefined) return '—'
  return `${(r * 100).toFixed(2)}%`
}

function opTypeLabel(t: string) {
  const m: Record<string, string> = {
    open: '建仓',
    add: '加仓',
    reduce: '减仓',
    close: '清仓',
  }
  return m[t] || t
}

async function loadOpen() {
  loadingOpen.value = true
  try {
    const { data } = await api.getOpenTrades()
    openItems.value = data.items
  } catch (e: unknown) {
    console.error(e)
    ElMessage.error('加载当前持仓失败')
  } finally {
    loadingOpen.value = false
  }
}

async function loadClosed() {
  loadingClosed.value = true
  try {
    const { data } = await api.getClosedTrades({ page: 1, page_size: 50 })
    closedItems.value = data.items
  } catch (e: unknown) {
    console.error(e)
    ElMessage.error('加载已完结失败')
  } finally {
    loadingClosed.value = false
  }
}

async function loadStats() {
  loadingStats.value = true
  try {
    const { data } = await api.getStats()
    stats.value = data
  } catch (e: unknown) {
    console.error(e)
    ElMessage.error('加载统计失败')
  } finally {
    loadingStats.value = false
  }
}

function resetForm() {
  formOpen.value = {
    stock_keyword: '',
    op_date: new Date().toISOString().slice(0, 10),
    qty: 100,
    price: 0,
  }
}

type StockSuggestion = { value: string; code: string; name: string | null }

function onSelectStockSuggestion(item: StockSuggestion) {
  formOpen.value.stock_keyword = item.code
}

async function queryStockSuggestions(
  q: string,
  cb: (items: StockSuggestion[]) => void
) {
  const keyword = q.trim()
  if (!keyword) {
    cb([])
    return
  }
  try {
    const [byCode, byName] = await Promise.all([
      getStockBasicList({ page: 1, page_size: 10, code: keyword }),
      getStockBasicList({ page: 1, page_size: 10, name: keyword }),
    ])
    const map = new Map<string, StockSuggestion>()
    for (const x of [...byCode.data.items, ...byName.data.items]) {
      if (map.has(x.code)) continue
      map.set(x.code, {
        value: `${x.code} ${x.name || ''}`.trim(),
        code: x.code,
        name: x.name,
      })
    }
    cb(Array.from(map.values()).slice(0, 20))
  } catch {
    cb([])
  }
}

async function resolveStockCodeByKeyword(keyword: string): Promise<string> {
  const text = keyword.trim()
  if (!text) {
    throw new Error('请输入股票代码或名称')
  }
  const [byCode, byName] = await Promise.all([
    getStockBasicList({ page: 1, page_size: 20, code: text }),
    getStockBasicList({ page: 1, page_size: 20, name: text }),
  ])
  const all = [...byCode.data.items, ...byName.data.items]
  const uniq = new Map(all.map((x) => [x.code, x]))
  const rows = Array.from(uniq.values())
  const exactCode = rows.find((x) => x.code.toUpperCase() === text.toUpperCase())
  if (exactCode) return exactCode.code
  const exactName = rows.filter((x) => (x.name || '').trim() === text)
  if (exactName.length === 1) return exactName[0].code
  if (rows.length === 1) return rows[0].code
  if (rows.length === 0) {
    throw new Error('未找到匹配的股票代码/名称，请确认后重试')
  }
  throw new Error('匹配到多只股票，请输入更精确代码或从联想列表选择')
}

function openDialogOpen() {
  resetForm()
  dlgOpen.value = true
}

async function submitOpen() {
  submitting.value = true
  try {
    const resolvedCode = await resolveStockCodeByKeyword(formOpen.value.stock_keyword)
    await api.openTrade({
      stock_code: resolvedCode,
      op_date: formOpen.value.op_date,
      qty: formOpen.value.qty,
      price: formOpen.value.price,
    })
    ElMessage.success('建仓成功')
    dlgOpen.value = false
    await loadOpen()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '建仓失败')
  } finally {
    submitting.value = false
  }
}

function openDialogAdd(row: OpenTradeItem) {
  opMode.value = 'add'
  currentTradeId.value = row.trade_id
  formOp.value = {
    op_date: new Date().toISOString().slice(0, 10),
    qty: 100,
    price: Number(row.avg_cost) || 0,
  }
  dlgOp.value = true
}

function openDialogReduce(row: OpenTradeItem) {
  opMode.value = 'reduce'
  currentTradeId.value = row.trade_id
  formOp.value = {
    op_date: new Date().toISOString().slice(0, 10),
    qty: 100,
    price: Number(row.avg_cost) || 0,
  }
  dlgOp.value = true
}

async function submitOp() {
  if (!currentTradeId.value) return
  submitting.value = true
  try {
    await api.addOperation(currentTradeId.value, {
      op_type: opMode.value,
      op_date: formOp.value.op_date,
      qty: formOp.value.qty,
      price: formOp.value.price,
    })
    ElMessage.success('已保存')
    dlgOp.value = false
    await loadOpen()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

function openDialogClose(row: OpenTradeItem) {
  currentTradeId.value = row.trade_id
  formClose.value = {
    op_date: new Date().toISOString().slice(0, 10),
    qty: Number(row.total_qty) || 0,
    price: Number(row.ref_close) || Number(row.avg_cost) || 0,
  }
  dlgClose.value = true
}

async function submitClose() {
  if (!currentTradeId.value) return
  submitting.value = true
  try {
    await api.closeTrade(currentTradeId.value, {
      op_date: formClose.value.op_date,
      qty: formClose.value.qty,
      price: formClose.value.price,
    })
    ElMessage.success('已清仓')
    dlgClose.value = false
    await loadOpen()
    await loadClosed()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '清仓失败')
  } finally {
    submitting.value = false
  }
}

async function confirmDelete(row: OpenTradeItem) {
  try {
    await ElMessageBox.confirm('将删除本笔未完结交易及全部操作记录，是否继续？', '确认删除', {
      type: 'warning',
    })
    await api.deleteOpenTrade(row.trade_id)
    ElMessage.success('已删除')
    await loadOpen()
  } catch (e: unknown) {
    if (e === 'cancel') return
    const err = e as { response?: { data?: { detail?: string } } }
    if (!err.response) return
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

async function loadImageBlobs(d: TradeDetail) {
  imagePreviewUrls.value.forEach((u) => URL.revokeObjectURL(u))
  imagePreviewUrls.value = []
  const ids = (d.images || []).map((x) => x.id)
  for (const id of ids) {
    try {
      const url = await api.fetchImageBlob(id)
      imagePreviewUrls.value.push(url)
    } catch {
      /* 忽略单张失败 */
    }
  }
}

async function openDrawer(tradeId: number) {
  drawerTradeId.value = tradeId
  drawerVisible.value = true
  loadingDetail.value = true
  imagePreviewUrls.value = []
  try {
    const { data } = await api.getTradeDetail(tradeId)
    detail.value = data
    reviewDraft.value = data.trade.review_text || ''
    await loadImageBlobs(data)
  } catch (e: unknown) {
    console.error(e)
    ElMessage.error('加载详情失败')
  } finally {
    loadingDetail.value = false
  }
}

async function saveReview() {
  if (!drawerTradeId.value) return
  savingReview.value = true
  try {
    await api.patchReview(drawerTradeId.value, reviewDraft.value || null)
    ElMessage.success('已保存')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    savingReview.value = false
  }
}

async function onUploadImage(options: UploadRequestOptions) {
  const file = options.file as File
  if (!drawerTradeId.value) {
    options.onError?.(new Error('no trade') as never)
    return
  }
  try {
    await api.uploadReviewImage(drawerTradeId.value, file)
    ElMessage.success('上传成功')
    const { data } = await api.getTradeDetail(drawerTradeId.value)
    detail.value = data
    await loadImageBlobs(data)
    options.onSuccess?.({} as never)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '上传失败')
    options.onError?.(e as never)
  }
}

async function onDeleteImage(index: number) {
  if (!detail.value) return
  const image = detail.value.images[index]
  if (!image) return
  deletingImageId.value = image.id
  try {
    await api.deleteReviewImage(image.id)
    ElMessage.success('已删除图片')
    const { data } = await api.getTradeDetail(detail.value.trade.id)
    detail.value = data
    await loadImageBlobs(data)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '删除图片失败')
  } finally {
    deletingImageId.value = null
  }
}

async function onOpRating(operationId: number, v: string | null) {
  try {
    await api.patchOperationRating(
      operationId,
      v === 'good' ? 'good' : v === 'bad' ? 'bad' : null
    )
    ElMessage.success('已更新自评')
    if (drawerTradeId.value) {
      const { data } = await api.getTradeDetail(drawerTradeId.value)
      detail.value = data
    }
    loadStats()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || '更新失败')
  }
}

watch(drawerVisible, (v) => {
  if (!v) {
    imagePreviewUrls.value.forEach((u) => URL.revokeObjectURL(u))
    imagePreviewUrls.value = []
  }
})

onMounted(() => {
  loadOpen()
  loadClosed()
  loadStats()
})
</script>

<style scoped>
.personal-holdings {
  max-width: 1400px;
}
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.card-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.page-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1e3a5f;
}
.sub-hint {
  font-size: 0.85rem;
  color: #909399;
}
.capability-link {
  font-size: 0.9rem;
}
.capability-content p {
  margin: 0.35em 0;
  font-size: 0.9rem;
  line-height: 1.5;
}
.toolbar {
  margin-bottom: 12px;
}
.muted {
  color: #909399;
}
.pnl-up {
  color: #16a34a;
  font-variant-numeric: tabular-nums;
}
.pnl-down {
  color: #dc2626;
  font-variant-numeric: tabular-nums;
}
.main-tabs {
  margin-top: 4px;
}
.stat-card {
  margin-bottom: 8px;
}
.stat-line,
.stat-rate {
  margin: 6px 0;
  font-variant-numeric: tabular-nums;
}
.stat-rate {
  font-size: 1.2rem;
  font-weight: 600;
  color: #1e3a5f;
}
.stat-hint {
  font-size: 0.8rem;
  color: #909399;
  margin-top: 8px;
}
.mt {
  margin-top: 12px;
}
.warn-text {
  color: #e6a23c;
  margin-bottom: 12px;
}
.drawer-pnl {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 6px;
}
.drawer-pnl-rate {
  font-size: 0.95rem;
  color: #606266;
  margin-bottom: 16px;
}
.op-line {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.9rem;
}
.op-rating {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.img-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.img-cell {
  position: relative;
}
.img-delete-btn {
  position: absolute;
  right: 2px;
  top: 2px;
  width: 18px;
  height: 18px;
  min-height: 18px;
  padding: 0;
  line-height: 16px;
}
h4 {
  margin: 16px 0 8px;
  font-size: 0.95rem;
  color: #303133;
}
</style>
