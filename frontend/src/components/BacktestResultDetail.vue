<template>
  <el-card shadow="hover" v-loading="loading">
    <template #header>
      <div class="card-header">
        <span class="title">回测结果详情</span>
        <el-tooltip placement="top">
          <template #content>
            <div v-if="detail?.report?.portfolio_capital" style="max-width: 340px">
              本任务已启用<strong>单仓位+补仓池</strong>资金仿真：总收益率按初始「持仓本金+补仓池」合计相对盈亏；同日全市场仅一笔；盈利进补仓池，开仓前不足由补仓池补足。<br/>
              <template v-if="detail.report.portfolio_capital.allow_rebuy_same_day_as_prior_sell !== false">
                当前为<strong>恐慌回落法</strong>日历：允许上一笔<strong>卖出当日</strong>再按收盘价买入另一只标的。<br/>
              </template>
              <template v-else>
                当前策略日历：<strong>须上一笔卖出日次日及以后</strong>才能再开仓（卖出当日不得换股）。<br/>
              </template>
              胜率、平均收益、最大盈亏等按落库已平仓成交笔数统计；不含手续费与复利。<br/>
              大盘温度统计展示不同市场温度下的表现差异。
            </div>
            <div v-else style="max-width: 340px">
              本任务结果中无资金仿真摘要（可能为较早记录或未完成）。总收益率等以接口返回为准。<br/>
              胜率、平均收益、最大盈亏等按已平仓笔数统计；不含手续费与复利。
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
      <template v-if="!showReportBody">
        <el-empty description="该时间范围内无符合策略条件的交易" />
      </template>
      <template v-else>
        <!-- 盈亏结论 -->
        <div class="conclusion-banner" :class="detail.report.total_return >= 0 ? 'positive' : 'negative'">
          {{ detail.report.conclusion }}
        </div>

        <!-- 策略逻辑说明 -->
        <div v-if="detail.strategy_description" class="section strategy-description">
          <h4 class="section-title">
            策略逻辑
            <el-tooltip content="本次回测使用的策略买入/卖出条件与参数" placement="top">
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <el-card shadow="never" class="strategy-card">
            <pre class="strategy-text">{{ detail.strategy_description }}</pre>
          </el-card>
        </div>

        <div v-if="detail.report.portfolio_capital" class="section portfolio-capital">
          <h4 class="section-title">
            资金账户（仓位约束）
            <el-tooltip placement="top">
              <template #content>
                <div style="max-width: 320px">{{ detail.report.portfolio_capital.description }}</div>
              </template>
              <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
            </el-tooltip>
          </h4>
          <div class="metrics-grid portfolio-grid">
            <div class="metric-item">
              <div class="metric-label">持仓金额/笔</div>
              <div class="metric-value">{{ fmtMoney(detail.report.portfolio_capital.position_size) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">初始补仓池</div>
              <div class="metric-value">{{ fmtMoney(detail.report.portfolio_capital.initial_reserve) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">策略闭仓信号</div>
              <div class="metric-value">{{ detail.report.portfolio_capital.strategy_raw_closed_count }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">实际成交（已平仓）</div>
              <div class="metric-value">{{ detail.report.portfolio_capital.executed_closed_count }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">因仓位规则跳过</div>
              <div class="metric-value">{{ detail.report.portfolio_capital.skipped_closed_count }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">同日选中未交易</div>
              <div class="metric-value">{{ detail.report.portfolio_capital.same_day_not_traded_count ?? 0 }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                日历冲突未交易
                <el-tooltip placement="top">
                  <template #content>
                    <div style="max-width: 300px">
                      <template v-if="detail.report.portfolio_capital.allow_rebuy_same_day_as_prior_sell !== false">
                        买入日早于上一笔卖出日（与上一笔持仓重叠）不成交；<strong>卖出当日可再买他股</strong>（恐慌口径）。
                      </template>
                      <template v-else>
                        买入日早于或等于上一笔卖出日均不成交：须<strong>卖出日次日及以后</strong>才能再开仓。
                      </template>
                    </div>
                  </template>
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </div>
              <div class="metric-value">{{ detail.report.portfolio_capital.before_previous_sell_not_traded_count ?? 0 }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                资金不足未交易
                <el-tooltip content="本金+补仓池仍凑不齐持仓额，该笔跳过；仿真会继续扫描后续全部信号" placement="top">
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </div>
              <div class="metric-value">{{ detail.report.portfolio_capital.insufficient_funds_not_traded_count ?? 0 }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">期末本金账户</div>
              <div class="metric-value">{{ fmtMoney(detail.report.portfolio_capital.final_principal) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">期末补仓池余额</div>
              <div class="metric-value">{{ fmtMoney(detail.report.portfolio_capital.final_reserve) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">期末合计权益</div>
              <div class="metric-value">{{ fmtMoney(detail.report.portfolio_capital.total_wealth_end) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">盈亏金额（相对初始合计）</div>
              <div
                class="metric-value"
                :class="detail.report.portfolio_capital.total_profit >= 0 ? 'profit' : 'loss'"
              >
                {{ detail.report.portfolio_capital.total_profit >= 0 ? '+' : '' }}{{ fmtMoney(detail.report.portfolio_capital.total_profit) }}
              </div>
            </div>
          </div>
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
            <el-tooltip
              v-if="detail.report.portfolio_capital"
              content="相对初始「持仓本金 + 补仓池」合计的收益率（资金仿真口径）"
              placement="top"
            >
              <div class="metric-value" :class="detail.report.total_return >= 0 ? 'profit' : 'loss'">
                {{ detail.report.total_return >= 0 ? '+' : '' }}{{ (detail.report.total_return * 100).toFixed(2) }}%
              </div>
            </el-tooltip>
            <div
              v-else
              class="metric-value"
              :class="detail.report.total_return >= 0 ? 'profit' : 'loss'"
            >
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
          <template v-if="detail.user_decision_stats && detail.user_decision_stats.trade_count > 0">
            <div class="metric-item">
              <div class="metric-label">
                人工策略正确率
                <el-tooltip
                  content="由您在明细中标注的「优秀决策」占已评价笔数之比，为主观判断，与盈亏收益率无关。"
                  placement="top"
                >
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </div>
              <div class="metric-value">
                <template
                  v-if="
                    detail.user_decision_stats.judged_count > 0 &&
                    detail.user_decision_stats.correctness_rate != null
                  "
                >
                  {{ (detail.user_decision_stats.correctness_rate * 100).toFixed(1) }}%
                </template>
                <span v-else class="cell-muted">—</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-label">评价进度</div>
              <div class="metric-value">
                {{ detail.user_decision_stats.judged_count }} / {{ detail.user_decision_stats.trade_count }}
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-label">优秀 / 错误</div>
              <div class="metric-value">
                {{ detail.user_decision_stats.excellent_count }} / {{ detail.user_decision_stats.wrong_count }}
              </div>
            </div>
          </template>
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
            <span class="filter-inline-label">
              <span>交易状态</span>
              <el-tooltip content="与下方明细、交叉验证、分年统计一致；选「已成交」仅看仓位仿真实际买入并平仓的记录" placement="top">
                <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
            <el-select
              v-model="tradeFilters.tradeStatus"
              clearable
              placeholder="全部"
              style="width: 200px"
            >
              <el-option label="已成交（实际买入）" value="closed" />
              <el-option label="选中未交易" value="not_traded" />
              <el-option label="未平仓" value="unclosed" />
            </el-select>
            <el-select
              v-model="tradeFilters.exchanges"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              placeholder="按交易所筛选"
              style="width: 240px"
            >
              <el-option
                v-for="ex in exchangeOptions"
                :key="ex.value"
                :label="ex.label"
                :value="ex.value"
              />
            </el-select>
            <el-select
              v-model="tradeFilters.market_temp_levels"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              placeholder="按温度筛选"
              style="width: 240px"
            >
              <el-option
                v-for="lvl in tempLevelOptions"
                :key="lvl"
                :label="lvl"
                :value="lvl"
              />
            </el-select>
            <el-select
              v-model="tradeFilters.markets"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              placeholder="按板块筛选"
              style="width: 260px"
            >
              <el-option
                v-for="m in marketOptions"
                :key="m"
                :label="m === '__EMPTY__' ? '空板块（北交所等）' : m"
                :value="m"
              />
            </el-select>
            <el-select
              v-model="tradeFilters.tradeYear"
              clearable
              placeholder="交易年份（全部）"
              style="width: 140px"
            >
              <el-option
                v-for="y in yearOptions"
                :key="y"
                :label="String(y)"
                :value="y"
              />
            </el-select>
            <el-button @click="handleTradeFilterSearch">筛选</el-button>
            <el-button @click="handleTradeFilterReset">重置</el-button>
            <el-button type="warning" plain :loading="bestOptionsLoading" @click="handleApplyBestWinRate">
              选择最佳胜率选项
            </el-button>
            <el-button type="danger" plain :loading="bestOptionsLoading" @click="handleApplyBestProfit">
              选择最佳盈利选项
            </el-button>
          </div>
          <div v-if="bestSelectionLabel" class="best-selection-text">{{ bestSelectionLabel }}</div>
          <el-alert
            v-if="filteredMetrics"
            type="info"
            :closable="false"
            class="filtered-summary"
            show-icon
          >
            <template #title>
              条件交叉验证结果：匹配 {{ filteredMetrics.matched_count }} 笔（已平仓 {{ filteredMetrics.total_trades }} 笔），
              胜率 {{ (filteredMetrics.win_rate * 100).toFixed(1) }}%，
              总收益 {{ filteredMetrics.total_return >= 0 ? '+' : '' }}{{ (filteredMetrics.total_return * 100).toFixed(2) }}%，
              平均收益 {{ filteredMetrics.avg_return >= 0 ? '+' : '' }}{{ (filteredMetrics.avg_return * 100).toFixed(2) }}%
            </template>
          </el-alert>
          <el-table :data="trades" stripe size="small" v-loading="tradesLoading">
            <el-table-column width="108">
              <template #header>
                <span>代码</span>
                <el-tooltip content="点击在东方财富打开该股行情（新标签页）" placement="top">
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <a
                  v-if="eastMoneyUrl(row)"
                  class="code-link"
                  :href="eastMoneyUrl(row)!"
                  target="_blank"
                  rel="noopener noreferrer"
                  @click.stop
                >{{ row.stock_code }}</a>
                <span v-else>{{ row.stock_code }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="stock_name" label="名称" width="90" />
            <el-table-column label="触发日" width="110">
              <template #header>
                <span>触发日</span>
                <el-tooltip
                  content="形态或信号触发日（如曙光初现的阳线日、早晨十字星的第三根阳线日），可能与买入日不同"
                  placement="top"
                >
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">{{ row.trigger_date || '-' }}</template>
            </el-table-column>
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
            <el-table-column width="100" align="right">
              <template #header>
                <span>收益率</span>
                <el-tooltip placement="top">
                  <template #content>
                    <div style="max-width: 280px">
                      已平仓：单笔收益率相对买入价。止损/止盈阈值因策略而异（如曙光初现约−10%、早晨十字星约−8%；止盈多为收盘≥买入×1.10 的当日收盘价），以离场原因为准。
                    </div>
                  </template>
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <el-tooltip
                  v-if="row.trade_type === 'not_traded' && row.extra?.hypothetical_return_rate != null"
                  :content="`假设收益率（未实际成交、不计入汇总）：${row.extra.hypothetical_return_rate >= 0 ? '+' : ''}${(row.extra.hypothetical_return_rate * 100).toFixed(2)}%`"
                  placement="top"
                >
                  <span class="cell-muted">—</span>
                </el-tooltip>
                <span v-else-if="row.return_rate != null" :class="row.return_rate >= 0 ? 'profit' : 'loss'">
                  {{ row.return_rate >= 0 ? '+' : '' }}{{ (row.return_rate * 100).toFixed(2) }}%
                </span>
                <span v-else class="cell-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column width="120">
              <template #header>
                <span>离场</span>
                <el-tooltip content="止损比例因策略而异（如−10%或−8%）；止盈多为收盘≥买入×1.10 按当日收盘价。详见离场原因。" placement="top">
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <span v-if="row.trade_type === 'closed'">{{ exitReasonLabel(row.extra) }}</span>
                <span v-else class="cell-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column width="108" align="right">
              <template #header>
                <span>盈亏(元)</span>
                <el-tooltip
                  content="已平仓且经仓位仿真：持仓名义×收益率；盈利为正、亏损为负"
                  placement="top"
                >
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <span
                  v-if="row.trade_type === 'closed' && row.extra?.trade_pnl_yuan != null"
                  :class="row.extra.trade_pnl_yuan >= 0 ? 'profit' : 'loss'"
                >
                  {{ row.extra.trade_pnl_yuan >= 0 ? '+' : '' }}{{ fmtYuan(row.extra.trade_pnl_yuan) }}
                </span>
                <span v-else class="cell-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column width="108" align="right">
              <template #header>
                <span>补仓划入(元)</span>
                <el-tooltip content="本笔开仓前从补仓池划入本金、用于凑齐持仓金额的数额" placement="top">
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <span v-if="row.trade_type === 'closed' && row.extra?.reserve_used_before_open_yuan != null">
                  {{ fmtYuan(row.extra.reserve_used_before_open_yuan) }}
                </span>
                <span v-else class="cell-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column width="118" align="right">
              <template #header>
                <span>补仓池余额(元)</span>
                <el-tooltip content="本笔卖出结算后补仓池剩余（盈利已计入池内）" placement="top">
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <span v-if="row.trade_type === 'closed' && row.extra?.reserve_balance_after_sell_yuan != null">
                  {{ fmtYuan(row.extra.reserve_balance_after_sell_yuan) }}
                </span>
                <span v-else class="cell-muted">-</span>
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
            <el-table-column prop="trade_type" label="类型" width="108">
              <template #default="{ row }">
                <el-tag
                  v-if="row.trade_type === 'closed'"
                  type="success"
                  size="small"
                >已平仓</el-tag>
                <el-tag
                  v-else-if="row.trade_type === 'not_traded'"
                  type="info"
                  size="small"
                >选中未交易</el-tag>
                <el-tag v-else type="warning" size="small">未平仓</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="策略评价" min-width="210" fixed="right">
              <template #header>
                <span>策略评价</span>
                <el-tooltip
                  content="主观判断该笔策略信号是否合适；可填写理由。用于统计人工正确率。"
                  placement="top"
                >
                  <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <template #default="{ row }">
                <div class="decision-cell">
                  <div class="decision-row">
                    <template v-if="row.user_decision === 'excellent'">
                      <el-tag type="success" size="small">优秀</el-tag>
                    </template>
                    <template v-else-if="row.user_decision === 'wrong'">
                      <el-tag type="danger" size="small">错误</el-tag>
                    </template>
                    <span v-else class="cell-muted">未评</span>
                    <el-tooltip
                      v-if="row.user_decision_reason"
                      :content="row.user_decision_reason"
                      placement="top"
                    >
                      <el-button link type="primary" size="small">理由</el-button>
                    </el-tooltip>
                  </div>
                  <div class="decision-actions">
                    <el-button size="small" @click="openDecisionDialog(row, 'excellent')">优秀</el-button>
                    <el-button size="small" @click="openDecisionDialog(row, 'wrong')">错误</el-button>
                    <el-button
                      v-if="row.user_decision"
                      size="small"
                      link
                      type="danger"
                      @click="clearDecision(row)"
                    >
                      清除
                    </el-button>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="未交易原因" width="130">
              <template #default="{ row }">
                <span v-if="row.trade_type === 'not_traded'">{{ skipReasonLabel(row.extra) }}</span>
                <span v-else class="cell-muted">-</span>
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

          <div class="section yearly-section">
            <h4 class="section-title">
              分年度分析
              <el-tooltip placement="top">
                <template #content>
                  <div style="max-width: 320px">
                    按买入日自然年汇总；与上方温度、交易所、板块、年份筛选条件一致（AND）。胜率与总收益仅基于已平仓交易；匹配笔数含未平仓。
                  </div>
                </template>
                <el-icon class="hint-icon-sm"><QuestionFilled /></el-icon>
              </el-tooltip>
            </h4>
            <el-table :data="yearlyItems" stripe size="small" v-loading="yearlyLoading" empty-text="当前筛选下无数据">
              <el-table-column prop="year" label="年份" width="80" />
              <el-table-column prop="matched_count" label="匹配笔数" width="90" align="right" />
              <el-table-column prop="total_trades" label="已平仓" width="80" align="right" />
              <el-table-column label="胜率" width="90" align="right">
                <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
              </el-table-column>
              <el-table-column label="总收益" width="100" align="right">
                <template #default="{ row }">
                  <span :class="row.total_return >= 0 ? 'profit' : 'loss'">
                    {{ row.total_return >= 0 ? '+' : '' }}{{ (row.total_return * 100).toFixed(2) }}%
                  </span>
                </template>
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

    <el-dialog
      v-model="decisionDialogVisible"
      title="策略决策评价"
      width="440px"
      destroy-on-close
      @closed="resetDecisionDialog"
    >
      <el-form label-position="top">
        <el-form-item label="结论">
          <el-radio-group v-model="decisionForm.judgment">
            <el-radio value="excellent">优秀决策</el-radio>
            <el-radio value="wrong">错误决策</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="理由（可选）">
          <el-input
            v-model="decisionForm.reason"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="可简要说明为何认为该笔策略决策合理或不合理"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="decisionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="decisionSaving" @click="submitDecision">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import {
  getBacktestBestOptions,
  getBacktestFilteredReport,
  getBacktestTaskDetail,
  getBacktestTrades,
  getBacktestYearlyAnalysis,
  patchBacktestTradeDecision,
  type BacktestBestOptionsResponse,
  type BacktestFilteredMetrics,
  type BacktestTaskDetailResponse,
  type BacktestTradeItem,
  type BacktestYearlyStatItem,
} from '@/api/backtest'
import { eastMoneyQuoteUrl } from '@/utils/eastMoneyQuoteUrl'

const props = defineProps<{
  taskId: string
}>()

defineEmits<{
  close: []
}>()

const detail = ref<BacktestTaskDetailResponse | null>(null)

const decisionDialogVisible = ref(false)
const decisionSaving = ref(false)
const decisionTradeRow = ref<BacktestTradeItem | null>(null)
const decisionForm = ref<{ judgment: 'excellent' | 'wrong'; reason: string }>({
  judgment: 'excellent',
  reason: '',
})

function resetDecisionDialog() {
  decisionTradeRow.value = null
  decisionForm.value = { judgment: 'excellent', reason: '' }
}

function openDecisionDialog(row: BacktestTradeItem, preset: 'excellent' | 'wrong') {
  decisionTradeRow.value = row
  decisionForm.value = {
    judgment: preset,
    reason: row.user_decision_reason ?? '',
  }
  decisionDialogVisible.value = true
}

async function submitDecision() {
  const row = decisionTradeRow.value
  if (!row) return
  decisionSaving.value = true
  try {
    await patchBacktestTradeDecision(props.taskId, row.id, {
      judgment: decisionForm.value.judgment,
      reason: decisionForm.value.reason.trim() || null,
    })
    ElMessage.success('已保存')
    decisionDialogVisible.value = false
    await loadDetail()
    await loadTrades()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    decisionSaving.value = false
  }
}

async function clearDecision(row: BacktestTradeItem) {
  try {
    await patchBacktestTradeDecision(props.taskId, row.id, { judgment: null })
    ElMessage.success('已清除评价')
    await loadDetail()
    await loadTrades()
  } catch {
    ElMessage.error('操作失败')
  }
}

/** 展示千分位整数金额（元） */
function fmtMoney(n: number): string {
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

/** 明细中的元（可带两位小数） */
function fmtYuan(n: number): string {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

const SKIP_REASON_LABEL: Record<string, string> = {
  same_buy_day: '同日仅一笔',
  before_previous_sell: '早于上一笔卖出日',
  insufficient_funds: '资金不足',
}

function skipReasonLabel(extra: Record<string, unknown> | null | undefined): string {
  const r = extra?.skip_reason
  if (typeof r !== 'string' || !r) return '-'
  return SKIP_REASON_LABEL[r] ?? r
}

const EXIT_REASON_LABEL: Record<string, string> = {
  stop_loss_8pct: '止损(约−8%)',
  take_profit_10pct: '止盈(≥+10%)',
  /** 早晨十字星移动止盈：涨幅≥15%后从最高回落5% */
  trailing_stop_5pct: '移动止盈(≥+15%后回落5%)',
  /** 历史回测记录（改阈值前） */
  stop_loss_6pct: '止损(约−6%)',
  stop_loss_10pct: '止损(约−10%)',
  /** 旧版：曾达+10%后破 MA5 才卖 */
  break_ma5_after_arm: '破MA5(武装后)',
}

function exitReasonLabel(extra: Record<string, unknown> | null | undefined): string {
  const r = extra?.exit_reason
  if (typeof r !== 'string' || !r) return '-'
  return EXIT_REASON_LABEL[r] ?? r
}

function eastMoneyUrl(row: BacktestTradeItem): string | null {
  return eastMoneyQuoteUrl(row.stock_code, row.exchange)
}

/** 有已落库交易、未平仓、或存在被仓位规则挡住的闭仓信号时展示报告主体 */
const showReportBody = computed(() => {
  const r = detail.value?.report
  if (!r) return false
  const pc = r.portfolio_capital
  if (r.total_trades > 0 || r.unclosed_count > 0) return true
  if (pc != null && pc.strategy_raw_closed_count > 0) return true
  return false
})

const loading = ref(false)
const trades = ref<BacktestTradeItem[]>([])
const filteredMetrics = ref<BacktestFilteredMetrics | null>(null)
const bestOptions = ref<BacktestBestOptionsResponse | null>(null)
const bestOptionsLoading = ref(false)
const bestSelectionLabel = ref('')
const tradesLoading = ref(false)
const tradesPage = ref(1)
const tradesPageSize = 50
const tradesTotal = ref(0)
const yearlyItems = ref<BacktestYearlyStatItem[]>([])
const yearlyLoading = ref(false)
const tradeFilters = ref<{
  /** 不传或清空=不限；closed=已成交；not_traded=选中未交易；unclosed=未平仓 */
  tradeStatus: string | undefined
  exchanges: string[]
  market_temp_levels: string[]
  markets: string[]
  tradeYear: number | undefined
}>({
  tradeStatus: undefined,
  exchanges: [],
  market_temp_levels: [],
  markets: [],
  tradeYear: undefined,
})

const tempLevelOptions = computed(() => {
  const levels = detail.value?.report?.temp_level_stats?.map((x) => x.level) ?? []
  return levels.filter(Boolean)
})

const marketOptions = computed(() => {
  const markets = detail.value?.report?.market_stats?.map((x) => x.name).filter(Boolean) ?? []
  // “空板块”主要对应 market 为空（如北交所样本）
  return ['__EMPTY__', ...markets]
})

const exchangeOptions = computed(() => {
  const exchanges = detail.value?.report?.exchange_stats?.map((x) => x.name).filter(Boolean) ?? []
  return exchanges.map((v) => ({
    value: v,
    label: v === 'SSE' ? '上交所(SSE)' : v === 'SZSE' ? '深交所(SZSE)' : v === 'BSE' ? '北交所(BSE)' : v,
  }))
})

const yearOptions = computed(() => {
  const d = detail.value
  if (!d) return []
  const y0 = parseInt(d.start_date.slice(0, 4), 10)
  const y1 = parseInt(d.end_date.slice(0, 4), 10)
  if (Number.isNaN(y0) || Number.isNaN(y1)) return []
  const list: number[] = []
  for (let y = y0; y <= y1; y += 1) list.push(y)
  return list
})

function tradeStatusFilterLabel(v: string | undefined): string {
  if (!v) return '不限'
  if (v === 'closed') return '已成交（实际买入）'
  if (v === 'not_traded') return '选中未交易'
  if (v === 'unclosed') return '未平仓'
  return v
}

function formatFilterText(filters: { market_temp_levels: string[]; markets: string[]; exchanges: string[] }) {
  const marketText = (filters.markets || [])
    .map((m) => (m === '__EMPTY__' ? '空板块（北交所等）' : m))
    .join('、') || '不限'
  const tempText = (filters.market_temp_levels || []).join('、') || '不限'
  const exchangeText = (filters.exchanges || []).join('、') || '不限'
  const st = tradeStatusFilterLabel(tradeFilters.value.tradeStatus)
  return `交易状态=${st}；温度=${tempText}；交易所=${exchangeText}；板块=${marketText}`
}

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getBacktestTaskDetail(props.taskId)
    tradesPage.value = 1
    await loadTrades()
    await loadFilteredMetrics()
    await loadYearlyAnalysis()
    await loadBestOptions()
    bestSelectionLabel.value = ''
  } finally {
    loading.value = false
  }
}

function tradeTypeQueryParam(): { trade_type?: string } {
  const t = tradeFilters.value.tradeStatus
  return t ? { trade_type: t } : {}
}

async function loadTrades() {
  tradesLoading.value = true
  try {
    const res = await getBacktestTrades(props.taskId, {
      ...tradeTypeQueryParam(),
      market_temp_levels: tradeFilters.value.market_temp_levels,
      markets: tradeFilters.value.markets,
      exchanges: tradeFilters.value.exchanges,
      year: tradeFilters.value.tradeYear,
      page: tradesPage.value,
      page_size: tradesPageSize,
    })
    trades.value = res.items
    tradesTotal.value = res.total
  } finally {
    tradesLoading.value = false
  }
}

async function loadFilteredMetrics() {
  const res = await getBacktestFilteredReport(props.taskId, {
    ...tradeTypeQueryParam(),
    market_temp_levels: tradeFilters.value.market_temp_levels,
    markets: tradeFilters.value.markets,
    exchanges: tradeFilters.value.exchanges,
    year: tradeFilters.value.tradeYear,
  })
  filteredMetrics.value = res.metrics
}

async function loadYearlyAnalysis() {
  yearlyLoading.value = true
  try {
    const res = await getBacktestYearlyAnalysis(props.taskId, {
      ...tradeTypeQueryParam(),
      market_temp_levels: tradeFilters.value.market_temp_levels,
      markets: tradeFilters.value.markets,
      exchanges: tradeFilters.value.exchanges,
      year: tradeFilters.value.tradeYear,
    })
    yearlyItems.value = res.items
  } finally {
    yearlyLoading.value = false
  }
}

async function loadBestOptions() {
  bestOptionsLoading.value = true
  try {
    bestOptions.value = await getBacktestBestOptions(props.taskId)
  } finally {
    bestOptionsLoading.value = false
  }
}

async function applyFiltersAndReload(filters: { market_temp_levels: string[]; markets: string[]; exchanges: string[] }) {
  tradeFilters.value = {
    tradeStatus: tradeFilters.value.tradeStatus,
    market_temp_levels: [...(filters.market_temp_levels || [])],
    markets: [...(filters.markets || [])],
    exchanges: [...(filters.exchanges || [])],
    tradeYear: tradeFilters.value.tradeYear,
  }
  tradesPage.value = 1
  await loadTrades()
  await loadFilteredMetrics()
  await loadYearlyAnalysis()
}

function handleTradeFilterSearch() {
  tradesPage.value = 1
  loadTrades()
  loadFilteredMetrics()
  loadYearlyAnalysis()
  bestSelectionLabel.value = ''
}

function handleTradeFilterReset() {
  tradeFilters.value = {
    tradeStatus: undefined,
    exchanges: [],
    market_temp_levels: [],
    markets: [],
    tradeYear: undefined,
  }
  tradesPage.value = 1
  loadTrades()
  loadFilteredMetrics()
  loadYearlyAnalysis()
  bestSelectionLabel.value = ''
}

async function handleApplyBestWinRate() {
  if (!bestOptions.value) {
    await loadBestOptions()
  }
  const target = bestOptions.value?.best_win_rate
  if (!target) return
  await applyFiltersAndReload(target.filters)
  bestSelectionLabel.value = `已应用最佳胜率条件：${formatFilterText(target.filters)}`
}

async function handleApplyBestProfit() {
  if (!bestOptions.value) {
    await loadBestOptions()
  }
  const target = bestOptions.value?.best_total_return
  if (!target) return
  await applyFiltersAndReload(target.filters)
  bestSelectionLabel.value = `已应用最佳盈利条件：${formatFilterText(target.filters)}`
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

.filter-inline-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.code-link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.code-link:hover {
  text-decoration: underline;
}

.cell-muted {
  color: #c0c4cc;
}

.filtered-summary {
  margin-bottom: 10px;
}

.yearly-section {
  margin-top: 20px;
}

.best-selection-text {
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
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

.strategy-description {
  margin-top: 16px;
}
.strategy-card {
  background: #fafafa;
}
.strategy-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  color: #303133;
}
</style>
