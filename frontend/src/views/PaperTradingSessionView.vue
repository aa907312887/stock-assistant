<template>
  <div class="session-view">
    <header class="session-top-bar">
      <el-button text type="primary" @click="goBackToList">
        <el-icon class="nav-back-icon"><ArrowLeft /></el-icon>
        返回列表
      </el-button>
      <el-tooltip placement="bottom" :show-after="200">
        <template #content>
          <div style="max-width: 260px; line-height: 1.6">
            返回「历史模拟交易」列表，不结束本会话，下次仍可从列表点「继续」。若要终止并锁定（不可再交易），请使用左下角「结束本次测试」。
          </div>
        </template>
        <el-icon class="nav-help"><QuestionFilled /></el-icon>
      </el-tooltip>
    </header>

    <el-alert
      v-if="store.currentSession && !store.isSessionActive"
      type="warning"
      show-icon
      :closable="false"
      class="session-ended-alert"
      title="本模拟已结束，仅可查看数据，不可再交易或推进日期。"
    />

    <!-- 主体：左栏 + 图 + 右栏 -->
    <div class="session-main">
    <!-- 左栏：账户与持仓 -->
    <div class="left-panel">
      <!-- 账户信息 -->
      <el-card class="account-card" shadow="never">
        <div class="account-date">
          <span class="date-text">{{ store.currentSession?.current_date }}</span>
          <el-tag size="small" :type="store.isOpenPhase ? 'warning' : 'success'">
            {{ store.isOpenPhase ? '开盘' : '收盘' }}
          </el-tag>
        </div>
        <div v-if="store.currentSession" class="market-temp-hero">
          <el-tooltip placement="bottom" :show-after="200">
            <template #content>
              <div style="max-width: 280px; line-height: 1.6">
                数值与级别对应<strong>前一交易日</strong>收盘后的大盘温度（数据日见右侧日期），不包含当前模拟日；避免使用尚未收盘的「当日」温度，与实盘可获知信息对齐。
              </div>
            </template>
            <div class="market-temp-hero-inner" role="status" aria-label="前一交易日大盘温度">
              <div class="market-temp-title-row">
                <span class="market-temp-title">大盘温度</span>
                <span class="market-temp-note">（前一交易日）</span>
              </div>
              <template v-if="store.currentSession.market_temp_ref_date">
                <div class="market-temp-values">
                  <span class="market-temp-score">{{
                    store.currentSession.market_temp_score != null
                      ? store.currentSession.market_temp_score.toFixed(1)
                      : '—'
                  }}</span>
                  <el-tag v-if="store.currentSession.market_temp_level" type="primary" effect="plain" size="small">
                    {{ store.currentSession.market_temp_level }}
                  </el-tag>
                  <span class="market-temp-date">{{ store.currentSession.market_temp_ref_date }}</span>
                </div>
              </template>
              <div v-else class="market-temp-empty">无上一交易日或暂无温度数据</div>
            </div>
          </el-tooltip>
        </div>
        <div class="account-row">
          <span class="label">总资产</span>
          <span class="value">¥{{ totalAsset.toFixed(2) }}</span>
        </div>
        <div class="account-row">
          <span class="label">可用资金</span>
          <span class="value">¥{{ (store.currentSession?.available_cash ?? 0).toFixed(2) }}</span>
        </div>
        <div class="account-row">
          <span class="label">总盈亏</span>
          <span class="value" :class="totalPL >= 0 ? 'profit' : 'loss'">
            {{ totalPL >= 0 ? '+' : '' }}{{ totalPL.toFixed(2) }}
            ({{ (totalPLPct * 100).toFixed(2) }}%)
          </span>
        </div>
      </el-card>

      <!-- 持仓 / 已清仓 -->
      <div class="positions-toolbar">
        <el-radio-group v-model="positionListTab" size="small" class="position-tabs">
          <el-radio-button value="holding">当前持仓</el-radio-button>
          <el-radio-button value="closed">已清仓</el-radio-button>
        </el-radio-group>
        <el-tooltip placement="top" :show-after="200">
          <template #content>
            <div style="max-width: 240px; line-height: 1.5">
              「已清仓」列出当前对该股已无持仓、但本会话内曾全部卖出的股票；点「查看」可浏览该股票在本会话中的全部买卖成交记录。
            </div>
          </template>
          <el-icon class="positions-help"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <div v-show="positionListTab === 'holding'" class="positions-list">
        <div
          v-for="pos in store.currentSession?.positions ?? []"
          :key="pos.stock_code"
          class="position-item"
          :class="{ active: selectedStock === pos.stock_code }"
          @click="selectStock(pos.stock_code)"
        >
          <div class="pos-header">
            <span class="pos-name">{{ pos.stock_name || pos.stock_code }}</span>
            <span class="pos-pl" :class="(pos.profit_loss ?? 0) >= 0 ? 'profit' : 'loss'">
              {{ (pos.profit_loss ?? 0) >= 0 ? '+' : '' }}{{ ((pos.profit_loss_pct ?? 0) * 100).toFixed(2) }}%
            </span>
          </div>
          <div class="pos-detail">
            <span>均价 {{ pos.avg_cost_price.toFixed(3) }}</span>
            <span>现价 {{ pos.current_price?.toFixed(3) ?? '-' }}</span>
            <span>{{ pos.total_quantity }} 股</span>
          </div>
          <div class="pos-actions">
            <el-tooltip
              placement="top"
              :show-after="200"
              :disabled="store.isSessionActive && pos.can_sell_quantity > 0"
            >
              <template #content>{{ sellDisabledReason(pos) }}</template>
              <span class="sell-btn-wrap">
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :disabled="!store.isSessionActive || pos.can_sell_quantity <= 0"
                  @click.stop="openSellDialog(pos)"
                >
                  卖出
                </el-button>
              </span>
            </el-tooltip>
          </div>
        </div>
        <el-empty v-if="!store.currentSession?.positions?.length" description="暂无持仓" :image-size="60" />
      </div>
      <div v-show="positionListTab === 'closed'" class="positions-list">
        <div
          v-for="row in store.currentSession?.closed_stocks ?? []"
          :key="row.stock_code"
          class="position-item closed-stock-item"
        >
          <div class="pos-header">
            <span class="pos-name">{{ row.stock_name || row.stock_code }}</span>
            <span
              class="pos-pl"
              :class="(row.realized_profit_loss ?? 0) >= 0 ? 'profit' : 'loss'"
            >
              {{ (row.realized_profit_loss ?? 0) >= 0 ? '+' : '' }}{{ ((row.realized_profit_loss_pct ?? 0) * 100).toFixed(2) }}%
            </span>
          </div>
          <div class="pos-detail">
            <span>已清仓批次 {{ row.closed_batch_count }}</span>
            <span
              class="closed-pl-amt"
              :class="(row.realized_profit_loss ?? 0) >= 0 ? 'profit' : 'loss'"
            >
              盈亏 {{ (row.realized_profit_loss ?? 0) >= 0 ? '+' : '' }}¥{{ (row.realized_profit_loss ?? 0).toFixed(2) }}
            </span>
          </div>
          <div class="pos-actions">
            <el-button size="small" type="primary" plain @click="openStockTradeHistory(row)">查看</el-button>
          </div>
        </div>
        <el-empty
          v-if="!(store.currentSession?.closed_stocks?.length)"
          description="暂无已清仓记录"
          :image-size="60"
        />
      </div>

      <!-- 底部操作按钮（窄栏内收缩，避免撑破左栏） -->
      <div class="phase-actions">
        <el-button
          v-if="store.isOpenPhase"
          class="phase-action-btn"
          type="primary"
          size="small"
          :loading="store.loading"
          :disabled="!store.isSessionActive"
          title="快捷键：键盘 →（右方向键）"
          @click="store.advanceToClose()"
        >
          推进到收盘 →
        </el-button>
        <el-button
          v-else
          class="phase-action-btn"
          type="success"
          size="small"
          :loading="store.loading"
          :disabled="!store.isSessionActive"
          title="快捷键：键盘 →（右方向键）"
          @click="store.nextDay()"
        >
          进入下一交易日 →
        </el-button>
        <el-button
          v-if="store.isSessionActive"
          class="phase-action-btn phase-action-btn--secondary"
          type="danger"
          plain
          size="small"
          :loading="store.loading"
          @click="handleEndSession"
        >
          结束本次测试
        </el-button>
      </div>
    </div>

    <!-- 中栏：K 线图表 -->
    <div class="chart-panel">
      <div class="chart-toolbar">
        <el-input
          v-model="stockInput"
          placeholder="代码或名称，如 000001.SZ、平安"
          style="width: 220px"
          clearable
          @keyup.enter="queryKlineFromInput"
        />
        <el-button type="primary" :loading="resolveLoading" @click="queryKlineFromInput">查询</el-button>
        <el-button @click="openStockInfoFromInput" :loading="stockInfoLoading">查看股票信息</el-button>
        <el-tooltip placement="bottom" :show-after="200">
          <template #content>
            <div style="max-width: 280px; line-height: 1.6">
              「查询」：支持代码或名称模糊匹配，解析成功后加载 K 线；多条匹配时请在列表中选定一只。<br />
              「查看股票信息」：弹窗展示基础资料、当前模拟日对应的日表行情，以及报告期不晚于模拟日的最近一期财报指标（如 ROE、资产负债率等）。
            </div>
          </template>
          <el-icon class="chart-toolbar-help"><QuestionFilled /></el-icon>
        </el-tooltip>
        <el-radio-group v-model="chartPeriod" size="small" @change="onPeriodChange">
          <el-radio-button value="daily">日</el-radio-button>
          <el-radio-button value="weekly">周</el-radio-button>
          <el-radio-button value="monthly">月</el-radio-button>
        </el-radio-group>
        <el-tooltip placement="bottom" :show-after="200">
          <template #content>
            <div style="max-width: 260px; line-height: 1.6">
              建议先使用「查看股票信息」了解标的后再下单。需已通过「查询」加载当前股票 K 线；若当前为周/月视图，将自动切回<strong>日线</strong>后再打开买入弹窗，以便使用模拟<strong>当日</strong>开盘价与涨跌停快捷填入。
            </div>
          </template>
          <el-button
            type="primary"
            size="small"
            :disabled="!store.chartData || store.chartLoading || !store.isSessionActive"
            @click="openBuyFromChartToolbar"
          >
            买入
          </el-button>
        </el-tooltip>
        <span v-if="store.chartData" class="chart-stock-name">
          {{ store.chartData.stock_name || store.chartData.stock_code }}
          <span v-if="store.isOpenPhase" class="phase-hint">（开盘中，收盘价待揭晓）</span>
        </span>
        <span
          v-if="store.isOpenPhase && store.chartData?.open_price != null && chartPeriod === 'daily'"
          class="open-price-pill"
        >
          今日开盘
          <strong>{{ store.chartData.open_price.toFixed(3) }}</strong>
        </span>
      </div>
      <div v-loading="store.chartLoading" class="chart-container">
        <div ref="chartRef" style="width: 100%; height: 100%" />
        <el-empty v-if="!store.chartData && !store.chartLoading" description="输入代码或名称后点击「查询」加载 K 线" />
      </div>
    </div>

    <!-- 右栏：选股与交易 -->
    <div class="right-panel">
      <el-tabs v-model="rightTab">
        <el-tab-pane label="推荐" name="recommend">
          <div class="tab-toolbar">
            <el-button size="small" :disabled="!store.isSessionActive" @click="store.loadRecommend()">
              换一批
            </el-button>
          </div>
          <div class="stock-list">
            <div
              v-for="item in store.recommendList"
              :key="item.stock_code"
              class="stock-item"
            >
              <div class="stock-info" @click="selectStock(item.stock_code)">
                <span class="stock-code">{{ item.stock_code }}</span>
                <span class="stock-name">{{ item.stock_name }}</span>
                <span class="stock-pct" :class="pctClass(item.pct_change)">
                  {{ formatPct(item.pct_change) }}
                </span>
              </div>
              <el-button size="small" type="primary" plain :disabled="!store.isSessionActive" @click="openBuyDialog(item)">
                买入
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="筛选" name="screen">
          <div class="screen-form">
            <el-form :model="screenForm" label-width="70px" size="small">
              <el-form-item label="涨跌幅">
                <div style="display: flex; gap: 4px; align-items: center">
                  <el-input-number v-model="screenForm.pct_change_min" :precision="1" :step="1" style="width: 80px" placeholder="最小" />
                  <span>~</span>
                  <el-input-number v-model="screenForm.pct_change_max" :precision="1" :step="1" style="width: 80px" placeholder="最大" />
                  <span>%</span>
                </div>
              </el-form-item>
              <el-form-item label="均线金叉">
                <el-select v-model="screenForm.ma_golden_cross" clearable placeholder="不限" style="width: 100%">
                  <el-option label="MA5 上穿 MA10" value="ma5_ma10" />
                  <el-option label="MA5 上穿 MA20" value="ma5_ma20" />
                </el-select>
              </el-form-item>
              <el-form-item label="MACD金叉">
                <el-switch v-model="screenForm.macd_golden_cross" />
              </el-form-item>
              <el-button type="primary" size="small" style="width: 100%" :disabled="!store.isSessionActive" @click="doScreen">
                筛选
              </el-button>
            </el-form>
          </div>
          <div class="screen-result-count" v-if="store.screenResult.total > 0">
            共 {{ store.screenResult.total }} 支
          </div>
          <div class="stock-list">
            <div
              v-for="item in store.screenResult.items"
              :key="item.stock_code"
              class="stock-item"
            >
              <div class="stock-info" @click="selectStock(item.stock_code)">
                <span class="stock-code">{{ item.stock_code }}</span>
                <span class="stock-name">{{ item.stock_name }}</span>
                <span class="stock-pct" :class="pctClass(item.pct_change)">
                  {{ formatPct(item.pct_change) }}
                </span>
              </div>
              <el-button size="small" type="primary" plain :disabled="!store.isSessionActive" @click="openBuyDialog(item)">
                买入
              </el-button>
            </div>
            <el-empty v-if="store.screenResult.items.length === 0" description="暂无结果" :image-size="50" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    </div><!-- /.session-main -->

    <!-- 买入弹窗 -->
    <el-dialog v-model="buyDialog.visible" title="买入" width="360px" :close-on-click-modal="false">
      <el-form :model="buyForm" label-width="80px">
        <el-form-item label="股票">
          <span>{{ buyDialog.stock?.stock_code }}</span>
        </el-form-item>
        <el-form-item label="买入价格">
          <div style="display: flex; gap: 6px; align-items: center; width: 100%">
            <el-input-number v-model="buyForm.price" :precision="3" :step="0.01" :min="0" style="flex: 1" />
          </div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" @click="buyForm.price = buyDialog.stock?.open ?? 0">开盘价 {{ buyDialog.stock?.open?.toFixed(3) }}</el-button>
            <el-button
              v-if="!store.isOpenPhase"
              size="small"
              @click="buyForm.price = buyDialog.stock?.close ?? 0"
            >收盘价 {{ buyDialog.stock?.close?.toFixed(3) }}</el-button>
          </div>
        </el-form-item>
        <el-form-item label="买入数量">
          <el-input-number v-model="buyForm.quantity" :min="100" :step="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预计金额">
          <span>¥{{ buyEstimate.amount.toFixed(2) }} + 手续费 ¥{{ buyEstimate.commission.toFixed(2) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="buyDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" @click="confirmBuy">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- 多只匹配时选人 -->
    <el-dialog
      v-model="pickDialog.visible"
      title="请选择股票"
      width="480px"
      destroy-on-close
      @closed="onPickDialogClosed"
    >
      <p class="pick-hint">根据您的输入匹配到多只股票，请选择一行或双击确认。</p>
      <el-table
        :data="pickDialog.items"
        max-height="320"
        highlight-current-row
        @row-dblclick="(row: StockResolveItem) => confirmPickStock(row)"
      >
        <el-table-column prop="stock_code" label="代码" width="120" />
        <el-table-column prop="stock_name" label="名称" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="confirmPickStock(row)">选用</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="pickDialog.visible = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 股票资料（日表 + 财报指标） -->
    <el-dialog
      v-model="stockInfoDialog.visible"
      :title="stockInfoTitle"
      width="640px"
      destroy-on-close
      class="stock-info-dialog"
    >
      <div v-loading="stockInfoDialog.loading">
        <template v-if="stockInfoDialog.data">
          <div class="info-section-title">基本信息</div>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="代码">{{ stockInfoDialog.data.basic.stock_code }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ stockInfoDialog.data.basic.stock_name ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="交易所">{{ stockInfoDialog.data.basic.exchange ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="板块">{{ stockInfoDialog.data.basic.market ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="行业">{{ stockInfoDialog.data.basic.industry_name ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="地域">{{ stockInfoDialog.data.basic.region ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="上市日期" :span="2">{{ stockInfoDialog.data.basic.list_date ?? '—' }}</el-descriptions-item>
          </el-descriptions>

          <div class="info-section-title">模拟日行情（日 K 线表）</div>
          <p v-if="stockInfoDialog.data.phase === 'open'" class="phase-note">当前为开盘阶段：高、低、收盘、涨跌幅、振幅、成交量、成交额等尚未揭晓（与 K 线图及 MACD 掩码规则一致）。</p>
          <template v-if="stockInfoDialog.data.daily">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="交易日">{{ stockInfoDialog.data.daily.trade_date }}</el-descriptions-item>
              <el-descriptions-item label="昨收">{{ fmtPrice(stockInfoDialog.data.daily.prev_close) }}</el-descriptions-item>
              <el-descriptions-item label="开盘">{{ fmtPrice(stockInfoDialog.data.daily.open) }}</el-descriptions-item>
              <el-descriptions-item label="最高">{{ fmtPrice(stockInfoDialog.data.daily.high) }}</el-descriptions-item>
              <el-descriptions-item label="最低">{{ fmtPrice(stockInfoDialog.data.daily.low) }}</el-descriptions-item>
              <el-descriptions-item label="收盘">{{ fmtPrice(stockInfoDialog.data.daily.close) }}</el-descriptions-item>
              <el-descriptions-item label="涨跌幅">{{ fmtPctPoint(stockInfoDialog.data.daily.pct_change) }}</el-descriptions-item>
              <el-descriptions-item label="振幅">{{ fmtPctPoint(stockInfoDialog.data.daily.amplitude) }}</el-descriptions-item>
              <el-descriptions-item label="成交量(手)">{{ fmtInt(stockInfoDialog.data.daily.volume) }}</el-descriptions-item>
              <el-descriptions-item label="成交额(千元)">{{ fmtInt(stockInfoDialog.data.daily.amount) }}</el-descriptions-item>
              <el-descriptions-item label="换手率">{{ fmtPctPoint(stockInfoDialog.data.daily.turnover_rate) }}</el-descriptions-item>
              <el-descriptions-item label="PE(TTM)">{{ fmtNum(stockInfoDialog.data.daily.pe_ttm) }}</el-descriptions-item>
              <el-descriptions-item label="PB">{{ fmtNum(stockInfoDialog.data.daily.pb) }}</el-descriptions-item>
              <el-descriptions-item label="总市值(万元)">{{ fmtInt(stockInfoDialog.data.daily.total_market_cap) }}</el-descriptions-item>
              <el-descriptions-item label="流通市值(万元)">{{ fmtInt(stockInfoDialog.data.daily.float_market_cap) }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="该日在日表中无行情数据（可能停牌或无同步）" :image-size="56" />

          <div class="info-section-title">经营与财务（最近一期财报，报告期 ≤ 模拟日）</div>
          <template v-if="stockInfoDialog.data.financial">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="报告期">{{ stockInfoDialog.data.financial.report_date }}</el-descriptions-item>
              <el-descriptions-item label="报告类型">{{ stockInfoDialog.data.financial.report_type ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="ROE">{{ fmtPctMaybe(stockInfoDialog.data.financial.roe) }}</el-descriptions-item>
              <el-descriptions-item label="ROE(扣非)">{{ fmtPctMaybe(stockInfoDialog.data.financial.roe_dt) }}</el-descriptions-item>
              <el-descriptions-item label="ROA">{{ fmtPctMaybe(stockInfoDialog.data.financial.roa) }}</el-descriptions-item>
              <el-descriptions-item label="资产负债率">{{ fmtPctMaybe(stockInfoDialog.data.financial.debt_to_assets) }}</el-descriptions-item>
              <el-descriptions-item label="毛利率">{{ fmtPctMaybe(stockInfoDialog.data.financial.gross_margin) }}</el-descriptions-item>
              <el-descriptions-item label="净利率">{{ fmtPctMaybe(stockInfoDialog.data.financial.net_margin) }}</el-descriptions-item>
              <el-descriptions-item label="营收(元)">{{ fmtLargeMoney(stockInfoDialog.data.financial.revenue) }}</el-descriptions-item>
              <el-descriptions-item label="净利润(元)">{{ fmtLargeMoney(stockInfoDialog.data.financial.net_profit) }}</el-descriptions-item>
              <el-descriptions-item label="EPS">{{ fmtNum(stockInfoDialog.data.financial.eps) }}</el-descriptions-item>
              <el-descriptions-item label="BPS">{{ fmtNum(stockInfoDialog.data.financial.bps) }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="暂无财报数据（未同步或报告期晚于当前模拟日）" :image-size="56" />
        </template>
      </div>
    </el-dialog>

    <!-- 已清仓股票：本会话内该代码全部成交记录 -->
    <el-dialog
      v-model="tradeHistoryDialog.visible"
      :title="tradeHistoryTitle"
      width="760px"
      destroy-on-close
      class="trade-history-dialog"
    >
      <div v-loading="tradeHistoryDialog.loading">
        <div
          v-if="tradeHistoryDialog.realized_profit_loss != null"
          class="trade-history-summary"
        >
          <span class="summary-label">已实现盈亏（本会话·该股）</span>
          <span
            class="summary-value"
            :class="tradeHistoryDialog.realized_profit_loss >= 0 ? 'profit' : 'loss'"
          >
            {{ tradeHistoryDialog.realized_profit_loss >= 0 ? '+' : '' }}¥{{
              tradeHistoryDialog.realized_profit_loss.toFixed(2)
            }}
            （{{ ((tradeHistoryDialog.realized_profit_loss_pct ?? 0) * 100).toFixed(2) }}%）
          </span>
          <span class="summary-hint">相对买入总成本（含买手续费）；与列表卡片一致</span>
        </div>
        <el-table
          v-if="tradeHistoryDialog.items.length"
          :data="tradeHistoryDialog.items"
          stripe
          max-height="440"
          size="small"
        >
          <el-table-column label="操作时间" width="156">
            <template #default="{ row }">{{ fmtOrderCreatedAt(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="trade_date" label="模拟日" width="100" />
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
          <el-table-column prop="cash_after" label="成交后余额" align="right" min-width="112">
            <template #default="{ row }">¥{{ row.cash_after.toFixed(2) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else-if="!tradeHistoryDialog.loading" description="暂无成交记录" />
      </div>
    </el-dialog>

    <!-- 卖出弹窗 -->
    <el-dialog v-model="sellDialog.visible" title="卖出" width="420px" :close-on-click-modal="false">
      <el-form :model="sellForm" label-width="80px">
        <el-form-item label="股票">
          <span>{{ sellDialog.position?.stock_name || sellDialog.position?.stock_code }}</span>
        </el-form-item>
        <el-form-item label="可卖数量">
          <span>{{ sellDialog.position?.can_sell_quantity }} 股</span>
        </el-form-item>
        <el-form-item label="卖出价格">
          <el-input-number v-model="sellForm.price" :precision="3" :step="0.01" :min="0" style="width: 100%" />
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" @click="fillSellPrice('open')">开盘价</el-button>
            <el-button v-if="!store.isOpenPhase" size="small" @click="fillSellPrice('close')">收盘价</el-button>
          </div>
        </el-form-item>
        <el-form-item label="卖出数量">
          <el-input-number
            v-model="sellForm.quantity"
            v-bind="sellQtyInputNumberProps"
            :step="100"
            :precision="0"
            style="width: 100%"
          />
          <div class="sell-qty-shortcuts">
            <el-tooltip placement="top" :show-after="200" :disabled="sellShortcutQuarter > 0" content="按 100 股取整后不足一手">
              <span class="sell-shortcut-wrap">
                <el-button
                  size="small"
                  :disabled="sellShortcutQuarter <= 0"
                  @click="applySellQtyShortcut('quarter')"
                >
                  1/4 仓
                </el-button>
              </span>
            </el-tooltip>
            <el-tooltip placement="top" :show-after="200" :disabled="sellShortcutHalf > 0" content="按 100 股取整后不足一手">
              <span class="sell-shortcut-wrap">
                <el-button
                  size="small"
                  :disabled="sellShortcutHalf <= 0"
                  @click="applySellQtyShortcut('half')"
                >
                  1/2 仓
                </el-button>
              </span>
            </el-tooltip>
            <el-button
              size="small"
              type="primary"
              plain
              :disabled="!sellDialog.position || sellDialog.position.can_sell_quantity <= 0"
              @click="applySellQtyShortcut('full')"
            >
              全仓
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="预计金额">
          <span>¥{{ sellEstimate.amount.toFixed(2) }} - 手续费 ¥{{ sellEstimate.commission.toFixed(2) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sellDialog.visible = false">取消</el-button>
        <el-button
          type="danger"
          :loading="tradeLoading"
          :disabled="!sellDialog.position || sellDialog.position.can_sell_quantity <= 0"
          @click="confirmSell"
        >
          确认卖出
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePaperTradingStore } from '@/stores/paperTrading'
import { paperTradingApi } from '@/api/paperTrading'
import type {
  ClosedStockSummary,
  OrderResponse,
  PaperStockInfoResponse,
  PositionSummary,
  StockQuote,
  StockResolveItem,
} from '@/api/paperTrading'
import type * as ECharts from 'echarts'

let echarts: typeof ECharts

const route = useRoute()
const router = useRouter()
const store = usePaperTradingStore()
const sessionId = route.params.sessionId as string

function goBackToList() {
  router.push({ name: 'paper-trading' })
}

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const chartPeriod = ref('daily')
const stockInput = ref('')
const selectedStock = ref('')
const rightTab = ref('recommend')
const tradeLoading = ref(false)

const screenForm = ref({
  pct_change_min: undefined as number | undefined,
  pct_change_max: undefined as number | undefined,
  ma_golden_cross: undefined as string | undefined,
  macd_golden_cross: false,
})

const buyDialog = ref<{ visible: boolean; stock: StockQuote | null }>({ visible: false, stock: null })
const sellDialog = ref<{ visible: boolean; position: PositionSummary | null }>({ visible: false, position: null })
const buyForm = ref({ price: 0, quantity: 100 })
const sellForm = ref({ price: 0, quantity: 100 })

const resolveLoading = ref(false)
let pickResolver: ((code: string | null) => void) | null = null
const pickDialog = ref<{ visible: boolean; items: StockResolveItem[] }>({ visible: false, items: [] })
const stockInfoLoading = ref(false)
const stockInfoDialog = ref<{
  visible: boolean
  loading: boolean
  data: PaperStockInfoResponse | null
}>({ visible: false, loading: false, data: null })

const stockInfoTitle = computed(() => {
  const d = stockInfoDialog.value.data
  if (!d) return '股票信息'
  return `股票信息 — ${d.basic.stock_name ?? d.stock_code}（${d.stock_code}）`
})

const positionListTab = ref<'holding' | 'closed'>('holding')

const tradeHistoryDialog = ref<{
  visible: boolean
  loading: boolean
  stockCode: string
  stockName: string
  items: OrderResponse[]
  realized_profit_loss: number | null
  realized_profit_loss_pct: number
}>({
  visible: false,
  loading: false,
  stockCode: '',
  stockName: '',
  items: [],
  realized_profit_loss: null,
  realized_profit_loss_pct: 0,
})

const tradeHistoryTitle = computed(() => {
  const d = tradeHistoryDialog.value
  if (!d.stockCode) return '成交记录'
  return `成交记录 — ${d.stockName || d.stockCode}（${d.stockCode}）`
})

const totalAsset = computed(() => store.currentSession?.total_asset ?? 0)
const totalPL = computed(() => store.currentSession?.total_profit_loss ?? 0)
const totalPLPct = computed(() => store.currentSession?.total_profit_loss_pct ?? 0)

const buyEstimate = computed(() => {
  const amount = buyForm.value.price * buyForm.value.quantity
  return { amount, commission: Math.max(amount * 0.0003, 5) }
})
const sellEstimate = computed(() => {
  const amount = sellForm.value.price * sellForm.value.quantity
  return { amount, commission: Math.max(amount * 0.0013, 5) }
})

/**
 * 卖出数量输入框：可卖为 0 时用 min=max=0（避免 EP 报 min>max）。
 * 可卖大于 0 时不传 max，避免组件在失焦时把「1000」静默截成可卖上限导致误下单。
 */
const sellQtyInputNumberProps = computed(() => {
  const maxSell = sellDialog.value.position?.can_sell_quantity ?? 0
  if (maxSell <= 0) {
    return { min: 0, max: 0 }
  }
  return { min: Math.min(100, maxSell) }
})

/** 快捷卖出：按可卖数量 × 比例后向下取整到 100 股 */
const sellMaxForShortcuts = computed(() => sellDialog.value.position?.can_sell_quantity ?? 0)
const sellShortcutQuarter = computed(() => {
  const max = sellMaxForShortcuts.value
  if (max <= 0) return 0
  return Math.floor((max * 0.25) / 100) * 100
})
const sellShortcutHalf = computed(() => {
  const max = sellMaxForShortcuts.value
  if (max <= 0) return 0
  return Math.floor((max * 0.5) / 100) * 100
})

function applySellQtyShortcut(kind: 'quarter' | 'half' | 'full') {
  const max = sellDialog.value.position?.can_sell_quantity ?? 0
  if (max <= 0) return
  if (kind === 'full') {
    sellForm.value.quantity = max
    return
  }
  const q = kind === 'half' ? sellShortcutHalf.value : sellShortcutQuarter.value
  if (q <= 0) return
  sellForm.value.quantity = q
}

function sellDisabledReason(pos: PositionSummary): string {
  if (!store.isSessionActive) return '本模拟已结束，无法卖出'
  if (pos.can_sell_quantity <= 0) return 'T+1：当日买入的股票次日才能卖出'
  return ''
}

/** 是否在应独占键盘的控件内（避免与输入、弹窗冲突） */
function isKeyboardConsumedTarget(target: EventTarget | null): boolean {
  const el = target instanceof Element ? target : null
  if (!el) return false
  if (el.closest('input, textarea, select, [contenteditable="true"]')) return true
  if (el.closest('.el-message-box')) return true
  return false
}

function onPhaseAdvanceHotkey(ev: KeyboardEvent) {
  if (ev.key !== 'ArrowRight') return
  if (store.loading) return
  if (!store.isSessionActive) return
  if (buyDialog.value.visible || sellDialog.value.visible) return
  if (pickDialog.value.visible || stockInfoDialog.value.visible || tradeHistoryDialog.value.visible) return
  if (isKeyboardConsumedTarget(ev.target)) return
  if (!store.currentSession) return
  ev.preventDefault()
  if (store.isOpenPhase) void store.advanceToClose()
  else void store.nextDay()
}

onMounted(async () => {
  // 动态导入 echarts 以减少初始包大小
  echarts = await import('echarts')
  await store.loadSession(sessionId)
  if (store.isSessionActive) await store.loadRecommend()
  window.addEventListener('keydown', onPhaseAdvanceHotkey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onPhaseAdvanceHotkey)
})

watch(() => store.chartData, async (data) => {
  if (!data) return
  await nextTick()
  if (!chartRef.value) return
  if (!chartInstance && echarts) chartInstance = echarts.init(chartRef.value)
  renderChart(data)
}, { deep: true })

/** 将 K 线数据转为 ECharts candlestick 四维；开盘阶段仅知 open 时后端会置空 high/low/close，需用 open 填平才能画出「一字」形态。 */
function toCandleOHLC(d: { open: number | null; close: number | null; low: number | null; high: number | null }): [number, number, number, number] {
  const o = d.open
  if (o == null) return [0, 0, 0, 0]
  const onlyOpenKnown = d.close == null && d.low == null && d.high == null
  if (onlyOpenKnown) return [o, o, o, o]
  const c = d.close ?? o
  const lo = d.low ?? Math.min(o, c)
  const hi = d.high ?? Math.max(o, c)
  return [o, c, lo, hi]
}

function renderChart(data: typeof store.chartData) {
  if (!data || !chartInstance) return
  const dates = data.data.map(d => d.date)
  const kData = data.data.map(d => toCandleOHLC(d))
  const volumes = data.data.map(d => d.volume ?? 0)
  const upColor = '#f56c6c', downColor = '#67c23a'
  const showOpenMarkLine =
    store.isOpenPhase &&
    data.period === 'daily' &&
    data.open_price != null

  chartInstance.setOption({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['MA5', 'MA10', 'MA20', 'MA60'], top: 4, textStyle: { fontSize: 11 } },
    grid: [
      { left: 60, right: 20, top: 36, height: '52%' },
      { left: 60, right: 20, top: '62%', height: '14%' },
      { left: 60, right: 20, top: '80%', height: '16%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: { fontSize: 10 } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitNumber: 4, axisLabel: { fontSize: 10 } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { fontSize: 10 } },
      { scale: true, gridIndex: 2, splitNumber: 2, axisLabel: { fontSize: 10 } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2], bottom: 4, height: 16 },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: kData,
        itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor },
        markLine: showOpenMarkLine
          ? {
              symbol: 'none',
              lineStyle: { color: '#e6a23c', width: 2, type: 'dashed' },
              label: {
                show: true,
                position: 'end',
                formatter: () => `开盘 ${(data!.open_price as number).toFixed(3)}`,
                color: '#b88230',
                fontSize: 11,
              },
              data: [{ yAxis: data.open_price as number }],
            }
          : undefined,
      },
      { name: 'MA5',  type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.data.map(d => d.ma5),  smooth: true, lineStyle: { width: 1 }, showSymbol: false },
      { name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.data.map(d => d.ma10), smooth: true, lineStyle: { width: 1 }, showSymbol: false },
      { name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.data.map(d => d.ma20), smooth: true, lineStyle: { width: 1 }, showSymbol: false },
      { name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.data.map(d => d.ma60), smooth: true, lineStyle: { width: 1 }, showSymbol: false },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
        itemStyle: { color: (p: any) => ((data!.data[p.dataIndex].close ?? 0) >= (data!.data[p.dataIndex].open ?? 0) ? upColor : downColor) },
      },
      { name: 'DIF',  type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.data.map(d => d.macd_dif), lineStyle: { width: 1 }, showSymbol: false },
      { name: 'DEA',  type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.data.map(d => d.macd_dea), lineStyle: { width: 1 }, showSymbol: false },
      {
        name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: data.data.map(d => d.macd_hist),
        itemStyle: { color: (p: any) => ((data!.data[p.dataIndex].macd_hist ?? 0) >= 0 ? upColor : downColor) },
      },
    ],
  }, true)
}

async function resolveUserInputToCode(): Promise<string | null> {
  const raw = stockInput.value.trim()
  if (!raw) {
    ElMessage.warning('请输入股票代码或名称')
    return null
  }
  resolveLoading.value = true
  try {
    const { data } = await paperTradingApi.resolveStock({ q: raw })
    if (!data.items.length) {
      ElMessage.warning('未找到匹配的股票')
      return null
    }
    if (data.items.length === 1) return data.items[0].stock_code
    pickDialog.value = { visible: true, items: data.items }
    return await new Promise<string | null>(resolve => {
      pickResolver = resolve
    })
  } catch {
    ElMessage.error('解析股票失败')
    return null
  } finally {
    resolveLoading.value = false
  }
}

function confirmPickStock(row: StockResolveItem) {
  const fn = pickResolver
  pickResolver = null
  pickDialog.value.visible = false
  fn?.(row.stock_code)
}

function onPickDialogClosed() {
  if (pickResolver) {
    pickResolver(null)
    pickResolver = null
  }
}

async function queryKlineFromInput() {
  const code = await resolveUserInputToCode()
  if (!code) return
  await selectStock(code)
}

async function openStockInfoFromInput() {
  const code = await resolveUserInputToCode()
  if (!code || !store.currentSession) return
  stockInfoLoading.value = true
  stockInfoDialog.value.visible = true
  stockInfoDialog.value.loading = true
  stockInfoDialog.value.data = null
  try {
    const { data } = await paperTradingApi.getStockInfo({
      stock_code: code,
      end_date: store.currentSession.current_date,
      phase: store.currentSession.current_phase,
    })
    stockInfoDialog.value.data = data
    stockInput.value = code
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message ?? '加载股票信息失败')
    stockInfoDialog.value.visible = false
  } finally {
    stockInfoDialog.value.loading = false
    stockInfoLoading.value = false
  }
}

/** 已清仓股票：本会话内该代码的全部买卖订单（按日期正序便于阅读） */
async function openStockTradeHistory(row: ClosedStockSummary) {
  if (!store.currentSession) return
  tradeHistoryDialog.value.visible = true
  tradeHistoryDialog.value.loading = true
  tradeHistoryDialog.value.stockCode = row.stock_code
  tradeHistoryDialog.value.stockName = row.stock_name ?? row.stock_code
  tradeHistoryDialog.value.items = []
  tradeHistoryDialog.value.realized_profit_loss = row.realized_profit_loss ?? 0
  tradeHistoryDialog.value.realized_profit_loss_pct = row.realized_profit_loss_pct ?? 0
  try {
    const { data } = await paperTradingApi.listOrders(store.currentSession.session_id, {
      stock_code: row.stock_code,
      page_size: 200,
      sort: 'asc',
    })
    tradeHistoryDialog.value.items = data.items
  } catch {
    ElMessage.error('加载成交记录失败')
    tradeHistoryDialog.value.visible = false
  } finally {
    tradeHistoryDialog.value.loading = false
  }
}

async function selectStock(code: string) {
  if (!code) return
  selectedStock.value = code
  stockInput.value = code
  await store.loadChartData(code, chartPeriod.value)
}

async function onPeriodChange() {
  if (selectedStock.value) await store.loadChartData(selectedStock.value, chartPeriod.value)
}

/** 由当前图表响应构造买入弹窗所需的行情（与模拟日当日日 K 口径对齐） */
function buildStockQuoteFromChartData(cd: NonNullable<typeof store.chartData>): StockQuote {
  const cur = store.currentSession?.current_date
  const bar = cur ? cd.data.find(d => d.date === cur) : undefined
  const last = cd.data[cd.data.length - 1]
  const dayBar = bar ?? last
  return {
    stock_code: cd.stock_code,
    stock_name: cd.stock_name,
    open: cd.open_price ?? dayBar?.open ?? null,
    close: cd.close_price ?? (store.isClosePhase ? dayBar?.close ?? null : null),
    pct_change: dayBar?.pct_change ?? null,
    volume: dayBar?.volume ?? null,
    limit_up: cd.limit_up,
    limit_down: cd.limit_down,
  }
}

async function openBuyFromChartToolbar() {
  if (!store.isSessionActive) {
    ElMessage.warning('本模拟已结束，无法买入')
    return
  }
  const code = selectedStock.value || store.chartData?.stock_code
  if (!code || !store.chartData) {
    ElMessage.warning('请先查询股票并加载 K 线后再买入')
    return
  }
  if (chartPeriod.value !== 'daily') {
    chartPeriod.value = 'daily'
    await store.loadChartData(code, 'daily')
  }
  const cd = store.chartData
  if (!cd) {
    ElMessage.warning('日线数据加载失败，请重试')
    return
  }
  openBuyDialog(buildStockQuoteFromChartData(cd))
}

function openBuyDialog(stock: StockQuote) {
  if (!store.isSessionActive) {
    ElMessage.warning('本模拟已结束，无法买入')
    return
  }
  buyDialog.value = { visible: true, stock }
  buyForm.value = { price: stock.open ?? 0, quantity: 100 }
}

function openSellDialog(pos: PositionSummary) {
  if (!store.isSessionActive) {
    ElMessage.warning('本模拟已结束，无法卖出')
    return
  }
  if (pos.can_sell_quantity <= 0) {
    ElMessage.warning('T+1 限制：当日买入的股票次日才能卖出')
    return
  }
  sellDialog.value = { visible: true, position: pos }
  sellForm.value = { price: pos.current_price ?? 0, quantity: Math.min(100, pos.can_sell_quantity) }
}

function fillSellPrice(type: 'open' | 'close') {
  if (!store.chartData) return
  sellForm.value.price = type === 'open' ? (store.chartData.open_price ?? 0) : (store.chartData.close_price ?? 0)
}

async function confirmBuy() {
  if (!store.isSessionActive) return
  if (!buyDialog.value.stock) return
  tradeLoading.value = true
  try {
    await store.buyStock(buyDialog.value.stock.stock_code, buyForm.value.price, buyForm.value.quantity)
    buyDialog.value.visible = false
  } finally {
    tradeLoading.value = false
  }
}

async function confirmSell() {
  if (!store.isSessionActive) return
  if (!sellDialog.value.position) return
  if (sellDialog.value.position.can_sell_quantity <= 0) {
    ElMessage.warning('T+1 限制：当日买入的股票次日才能卖出')
    return
  }
  const max = sellDialog.value.position.can_sell_quantity
  const q = sellForm.value.quantity
  if (q <= 0 || !Number.isFinite(q)) {
    ElMessage.warning('请输入有效的卖出数量')
    return
  }
  if (q % 100 !== 0) {
    ElMessage.warning('卖出数量须为 100 股的整数倍')
    return
  }
  if (q > max) {
    ElMessage.warning(`可用股票数额不足：当前最多可卖 ${max} 股，您提交的数量为 ${q} 股`)
    return
  }
  tradeLoading.value = true
  try {
    await store.sellStock(sellDialog.value.position.stock_code, sellForm.value.price, q)
    sellDialog.value.visible = false
  } finally {
    tradeLoading.value = false
  }
}

async function doScreen() {
  await store.screenStocks({
    pct_change_min: screenForm.value.pct_change_min,
    pct_change_max: screenForm.value.pct_change_max,
    ma_golden_cross: screenForm.value.ma_golden_cross,
    macd_golden_cross: screenForm.value.macd_golden_cross || undefined,
  })
}

const handleEndSession = async () => {
  const confirmed = await new Promise(resolve => {
    ElMessageBox.confirm(
      '确定要结束本次测试吗？结束后会话将标记为「已结束」，无法再交易、换股或推进日期，仅可回看 K 线与在列表中查看成交详情。',
      '结束测试',
      {
        confirmButtonText: '确定结束',
        cancelButtonText: '取消',
        type: 'warning',
      }
    ).then(() => resolve(true)).catch(() => resolve(false))
  })

  if (!confirmed) return

  try {
    store.loading = true
    await store.endSession()
    ElMessage.success('本模拟已结束并锁定，已返回列表')
    router.push({ name: 'paper-trading' })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || '结束失败')
  } finally {
    store.loading = false
  }
}

function fmtPrice(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(3)
}
/** 订单落库时间，同日多笔时区分先后 */
function fmtOrderCreatedAt(iso: string | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}
function fmtPctPoint(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v.toFixed(2)}%`
}
function fmtPctMaybe(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v.toFixed(2)}%`
}
function fmtNum(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  const s = v.toFixed(4).replace(/\.?0+$/, '')
  return s || '0'
}
function fmtInt(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  return Math.round(v).toLocaleString('zh-CN')
}
function fmtLargeMoney(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function pctClass(pct: number | null) { return pct === null ? '' : pct >= 0 ? 'profit' : 'loss' }
function formatPct(pct: number | null) { return pct === null ? '-' : (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%' }
</script>

<style scoped>
.session-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #f5f7fa;
}
.session-top-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.nav-back-icon {
  margin-right: 2px;
  vertical-align: middle;
}
.nav-help {
  color: #909399;
  cursor: help;
  font-size: 16px;
}
.session-ended-alert {
  flex-shrink: 0;
  margin: 0;
  border-radius: 0;
}
.session-main {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.left-panel {
  width: 260px;
  min-width: 260px;
  max-width: 260px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e4e7ed;
  background: #fff;
  overflow: hidden;
  min-height: 0;
}
.account-card { border-radius: 0; border: none; border-bottom: 1px solid #e4e7ed; }
.account-date { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.market-temp-hero {
  margin: 0 0 10px 0;
  padding: 10px 10px;
  border-radius: 8px;
  background: linear-gradient(120deg, #ecf5ff 0%, #f0f9ff 55%, #fafcff 100%);
  border: 1px solid #b3d8ff;
  box-shadow: 0 1px 2px rgba(64, 158, 255, 0.12);
  cursor: help;
}
.market-temp-hero-inner { min-height: 40px; }
.market-temp-title-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 4px;
}
.market-temp-title { font-size: 13px; font-weight: 700; color: #303133; }
.market-temp-note { font-size: 11px; color: #909399; }
.market-temp-values {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.market-temp-score {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
  line-height: 1.2;
  letter-spacing: 0.02em;
}
.market-temp-date { font-size: 11px; color: #909399; }
.market-temp-empty { font-size: 12px; color: #909399; }
.date-text { font-size: 14px; font-weight: 600; }
.account-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.label { color: #909399; }
.value { font-weight: 500; }
.positions-title { padding: 8px 12px 4px; font-size: 13px; color: #606266; font-weight: 600; }
.positions-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px 4px;
  border-bottom: 1px solid #ebeef5;
}
.position-tabs { flex: 1; }
.positions-help { color: #909399; cursor: help; font-size: 15px; flex-shrink: 0; }
.positions-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.closed-stock-item { cursor: default; }
.closed-stock-item .pos-meta { font-size: 11px; color: #909399; }
.position-item { padding: 8px; border-radius: 6px; margin-bottom: 6px; cursor: pointer; border: 1px solid #ebeef5; transition: border-color 0.2s; }
.position-item:hover, .position-item.active { border-color: #409eff; }
.pos-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.pos-name { font-size: 13px; font-weight: 500; }
.pos-detail { font-size: 11px; color: #909399; display: flex; gap: 6px; margin-bottom: 4px; }
.pos-actions { display: flex; justify-content: flex-end; }
.sell-btn-wrap { display: inline-block; }
.sell-shortcut-wrap { display: inline-block; }
.sell-qty-shortcuts {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.phase-actions {
  flex-shrink: 0;
  padding: 8px 6px;
  border-top: 1px solid #e4e7ed;
  box-sizing: border-box;
  min-width: 0;
}
.phase-actions .phase-action-btn {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin-left: 0;
  justify-content: center;
  white-space: normal;
  line-height: 1.35;
  padding-left: 8px;
  padding-right: 8px;
  height: auto;
  min-height: 28px;
}
.phase-actions .phase-action-btn--secondary {
  margin-top: 6px;
}

.chart-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: #fff; border-right: 1px solid #e4e7ed; }
.chart-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid #e4e7ed; flex-wrap: wrap; }
.chart-toolbar-help { color: #909399; cursor: help; font-size: 16px; vertical-align: middle; }
.chart-stock-name { font-size: 13px; font-weight: 500; color: #303133; }
.phase-hint { font-size: 11px; color: #e6a23c; }
.open-price-pill {
  font-size: 12px;
  color: #b88230;
  padding: 2px 10px;
  border-radius: 4px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
}
.open-price-pill strong { color: #e6a23c; margin-left: 4px; }
.chart-container { flex: 1; position: relative; overflow: hidden; }

.right-panel { width: 300px; min-width: 300px; background: #fff; display: flex; flex-direction: column; overflow: hidden; }
.right-panel :deep(.el-tabs) { height: 100%; display: flex; flex-direction: column; }
.right-panel :deep(.el-tabs__content) { flex: 1; overflow: hidden; }
.right-panel :deep(.el-tab-pane) { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.tab-toolbar { padding: 6px 12px; border-bottom: 1px solid #ebeef5; }
.screen-form { padding: 8px 12px; border-bottom: 1px solid #ebeef5; }
.screen-result-count { padding: 4px 12px; font-size: 12px; color: #909399; }
.stock-list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.stock-item { display: flex; align-items: center; justify-content: space-between; padding: 6px 4px; border-bottom: 1px solid #f2f6fc; }
.stock-info { flex: 1; cursor: pointer; }
.stock-code { font-size: 12px; color: #303133; }
.stock-name { font-size: 12px; color: #909399; margin-left: 4px; }
.stock-pct { font-size: 12px; margin-left: 6px; }

.profit { color: #f56c6c; }
.loss   { color: #67c23a; }
.closed-pl-amt { font-weight: 500; }
.trade-history-summary {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}
.trade-history-summary .summary-label { color: #606266; }
.trade-history-summary .summary-value { font-weight: 600; }
.trade-history-summary .summary-hint { width: 100%; font-size: 11px; color: #909399; margin: 0; }

.pick-hint { font-size: 13px; color: #606266; margin: 0 0 10px; }
.info-section-title { font-size: 14px; font-weight: 600; margin: 16px 0 8px; color: #303133; }
.info-section-title:first-of-type { margin-top: 0; }
.phase-note { font-size: 12px; color: #e6a23c; margin: 0 0 8px; }
.stock-info-dialog :deep(.el-descriptions__label) { width: 140px; }
</style>
