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
          :default-openeds="['stock-info']"
          router
          class="menu"
        >
          <el-menu-item index="/">首页</el-menu-item>
          <el-sub-menu index="stock-info">
            <template #title>股票信息</template>
            <el-menu-item index="/stock-screening">综合选股</el-menu-item>
            <el-menu-item index="/stock-basic">股票基本信息</el-menu-item>
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
