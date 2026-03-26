<template>
  <el-card class="temp-card" shadow="never">
    <template #header>
      <div class="head">
        <span class="title">大盘温度</span>
        <el-button link type="primary" @click="showExplain = true">?</el-button>
      </div>
    </template>

    <div v-if="loading" class="loading"><el-skeleton :rows="3" animated /></div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="latest">
      <div
        class="hero-main"
        :style="{ color: heroAccentColor(latest.temperature_level) }"
      >
        <span class="level-title">{{ latest.temperature_level }}</span>
        <span class="score-inline">{{ latest.temperature_score.toFixed(2) }}</span>
      </div>
      <div class="meta">方向：{{ latest.trend_flag }} / 更新：{{ formatDt(latest.updated_at) }}</div>
      <el-tooltip placement="top" :show-after="150">
        <template #content>{{ latest.strategy_hint }}</template>
        <div class="hint">{{ latest.strategy_hint }}</div>
      </el-tooltip>
      <div class="trend-block">
        <div class="trend-title">近 {{ trend.length || 20 }} 个交易日</div>
        <div class="trend-pills">
          <el-tooltip
            v-for="item in trend"
            :key="item.trade_date"
            placement="top"
            :show-after="200"
          >
            <template #content>
              {{ item.trade_date }} · {{ item.temperature_level }} · {{ item.trend_flag }}
            </template>
            <button
              type="button"
              :class="['trend-pill', levelClass(item.temperature_level)]"
              :style="trendPillStyle(item.temperature_level)"
            >
              <span class="trend-pill-line1">{{ item.temperature_level }}</span>
              <span class="trend-pill-line2">{{ item.temperature_score.toFixed(2) }}</span>
            </button>
          </el-tooltip>
        </div>
      </div>
    </template>

    <MarketTemperatureExplainModal v-model:visible="showExplain" :explain="explain" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  getLatestMarketTemperature,
  getMarketTemperatureExplain,
  getMarketTemperatureTrend,
  type MarketTemperatureLatest,
  type MarketTemperatureTrendPoint,
} from '@/api/marketTemperature'
import MarketTemperatureExplainModal from '@/components/MarketTemperatureExplainModal.vue'

const loading = ref(true)
const error = ref('')
const latest = ref<MarketTemperatureLatest | null>(null)
const trend = ref<MarketTemperatureTrendPoint[]>([])
const showExplain = ref(false)
const explain = ref<any>(null)

function formatDt(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function isHexColor(token: string) {
  return typeof token === 'string' && /^#[0-9a-fA-F]{6}$/.test(token.trim())
}

function levelHex(level: string): string | null {
  const item = latest.value?.level_styles.find((s) => s.level_name === level)
  if (item && isHexColor(item.visual_token)) return item.visual_token.trim()
  return null
}

/** 标题行「档位 + 分数」共用颜色 */
function heroAccentColor(level: string) {
  return levelHex(level) || '#1e3a5f'
}

function levelClass(level: string) {
  if (level === '极冷') return 'very-cold'
  if (level === '偏冷') return 'cold'
  if (level === '中性') return 'neutral'
  if (level === '偏热') return 'warm'
  return 'hot'
}

function trendPillStyle(level: string) {
  const hex = levelHex(level)
  if (!hex) return {}
  return {
    backgroundColor: hex,
    color: '#fff',
    borderColor: hex,
  }
}

onMounted(async () => {
  loading.value = true
  try {
    latest.value = await getLatestMarketTemperature()
    const trendData = await getMarketTemperatureTrend(20)
    trend.value = trendData.points
    explain.value = await getMarketTemperatureExplain()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '大盘温度加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.temp-card { border: 1px solid #e4e7ed; border-radius: 12px; }
.head { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 700; color: #303133; }
.hero-main {
  margin-bottom: 8px;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px 14px;
  line-height: 1.2;
}
.level-title {
  font-size: 1.55rem;
  font-weight: 800;
  letter-spacing: 0.06em;
}
.score-inline {
  font-size: 1.85rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.meta { margin-top: 8px; font-size: 12px; color: #909399; }
.hint { margin-top: 8px; color: #606266; cursor: help; font-size: 13px; line-height: 1.5; }
.trend-block { margin-top: 16px; }
.trend-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #303133;
  margin-bottom: 14px;
  letter-spacing: 0.02em;
}
.trend-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: center;
}
.trend-pill {
  cursor: default;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px 12px;
  min-width: 4.25rem;
  border-radius: 10px;
  border: 1px solid transparent;
  line-height: 1.15;
}
.trend-pill-line1 {
  font-size: 0.88rem;
  font-weight: 700;
}
.trend-pill-line2 {
  font-size: 1rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  opacity: 0.98;
}
.trend-pill.very-cold { background: #1e3a8a; color: #fff; }
.trend-pill.cold { background: #3b82f6; color: #fff; }
.trend-pill.neutral { background: #9ca3af; color: #fff; }
.trend-pill.warm { background: #f59e0b; color: #fff; }
.trend-pill.hot { background: #ef4444; color: #fff; }
.error { color: #f56c6c; }
</style>
