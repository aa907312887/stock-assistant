<template>
  <el-container class="layout">
    <el-header class="header">
      <span class="logo">股票分析助手</span>
      <div class="user">
        <span>{{ userStore.user?.username }}</span>
        <el-button type="primary" link @click="handleLogout">退出</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" class="aside">
        <el-menu
          :default-active="activeMenu"
          :default-openeds="['stock-info', 'personal-services', 'strategy', 'backtest']"
          router
          class="menu"
        >
          <el-menu-item index="/">首页</el-menu-item>
          <el-sub-menu index="stock-info">
            <template #title>股票信息</template>
            <el-menu-item index="/market-temperature">大盘温度</el-menu-item>
            <el-menu-item index="/stock-screening">综合选股</el-menu-item>
            <el-menu-item index="/fundamental-analysis">基本面分析</el-menu-item>
            <el-menu-item index="/stock-basic">股票基本信息</el-menu-item>
            <el-menu-item index="/sync-jobs">同步批次</el-menu-item>
            <el-menu-item index="/sync-tasks">同步子任务</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="personal-services">
            <template #title>个人服务</template>
            <el-menu-item index="/personal-holdings">个人持仓</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="strategy">
            <template #title>策略选股</template>
            <el-menu-item index="/strategy/chong-gao-hui-luo">冲高回落战法</el-menu-item>
            <el-menu-item index="/strategy/panic-pullback">恐慌回落战法</el-menu-item>
            <el-menu-item index="/strategy/bottom-consolidation-breakout">底部盘整突破</el-menu-item>
            <el-menu-item index="/strategy/ma-golden-cross">均线金叉</el-menu-item>
            <el-menu-item index="/strategy/da-yang-hui-luo">大阳回落法</el-menu-item>
            <el-menu-item index="/strategy/zao-chen-shi-zi-xing">早晨十字星</el-menu-item>
            <el-menu-item index="/strategy/pe-value-investment">市盈率长线价值</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="backtest">
            <template #title>智能回测</template>
            <el-menu-item index="/backtest/history">历史回测</el-menu-item>
            <el-menu-item index="/backtest/simulation">历史模拟</el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  userStore.loadUserFromStorage()
})

const activeMenu = computed(() => route.path === '/' ? '/' : route.path)

function handleLogout() {
  userStore.setLogout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 0 24px;
}
.logo {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1e3a5f;
}
.user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.aside {
  background: #fff;
  box-shadow: 1px 0 4px rgba(0, 0, 0, 0.06);
}
.menu {
  border-right: none;
}
.main {
  padding: 24px;
  overflow: auto;
}
</style>
