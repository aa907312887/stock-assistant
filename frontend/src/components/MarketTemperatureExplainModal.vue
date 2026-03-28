<template>
  <el-dialog v-model="visibleRef" title="大盘温度计算口径" width="720px" class="explain-dialog" destroy-on-close>
    <div v-if="explain" class="explain-scroll">
      <p class="version-line">版本：{{ explain.formula_version }}</p>

      <template v-if="explain.score_pipeline">
        <h4 class="section-title">{{ explain.score_pipeline.title }}</h4>
        <div class="detail-block">{{ explain.score_pipeline.body }}</div>
      </template>

      <h4 class="section-title">三因子构成</h4>
      <p class="section-lead">下列「计算方式」逐步对应后端公式引擎实现（含均线未满窗、风险标准差定义、分位数算法）；「设计思路」说明为何拆成三因子与权重取舍。</p>
      <section v-for="f in explain.factors" :key="f.factor_name" class="factor-section">
        <h5 class="factor-title">{{ f.factor_name }}（{{ (f.weight * 100).toFixed(0) }}%）</h5>
        <p v-if="f.description" class="factor-tagline">{{ f.description }}</p>
        <h6 class="subhead">计算方式</h6>
        <div class="detail-block">{{ f.calculation_detail }}</div>
        <h6 class="subhead">设计思路</h6>
        <div class="detail-block">{{ f.design_rationale }}</div>
      </section>

      <h4 class="section-title">五档说明与操作建议</h4>
      <p class="section-hint">以下为各档位名称、分数区间及倾向操作，与本页趋势区方块一致：上行档位名、下行温度分。</p>
      <ul class="levels-explain">
        <li v-for="l in explain.levels" :key="l.level_name">
          <span v-if="l.color" class="swatch" :style="{ backgroundColor: l.color }" />
          <span class="level-line">
            <strong>{{ l.level_name }}</strong>：{{ l.action }}
            <span class="range">（{{ l.score_range }} 分）</span>
          </span>
        </li>
      </ul>
      <template v-if="explain.content">
        <h4 class="section-title">补充说明</h4>
        <p class="content">{{ explain.content }}</p>
      </template>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  visible: boolean
  explain: any
}>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const visibleRef = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})
</script>

<style scoped>
.explain-scroll {
  max-height: min(70vh, 640px);
  overflow-y: auto;
  padding-right: 6px;
}
.version-line {
  margin: 0 0 12px;
  font-size: 14px;
  color: #303133;
}
.section-lead {
  margin: 0 0 14px;
  font-size: 13px;
  color: #909399;
  line-height: 1.55;
}
.detail-block {
  margin: 0 0 12px;
  font-size: 13px;
  color: #303133;
  line-height: 1.7;
  white-space: pre-line;
}
.factor-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}
.factor-section:last-of-type {
  border-bottom: none;
}
.factor-title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}
.factor-tagline {
  margin: 0 0 12px;
  font-size: 12px;
  color: #909399;
  line-height: 1.55;
}
.subhead {
  margin: 10px 0 6px;
  font-size: 13px;
  font-weight: 700;
  color: #409eff;
}
.content { color: #606266; line-height: 1.6; margin-top: 0; }
.section-title {
  margin: 20px 0 8px;
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}
.version-line + .section-title {
  margin-top: 8px;
}
.section-hint {
  margin: 0 0 10px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}
.levels-explain {
  margin: 0;
  padding-left: 0;
  list-style: none;
}
.levels-explain li { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
.level-line { color: #303133; line-height: 1.5; }
.level-line .range { color: #909399; font-weight: 400; margin-left: 4px; }
.swatch { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; border: 1px solid #e4e7ed; margin-top: 4px; }

/* 窄屏下对话框不溢出视口 */
@media (max-width: 760px) {
  .explain-dialog :deep(.el-dialog) {
    width: 92vw !important;
  }
}
</style>
