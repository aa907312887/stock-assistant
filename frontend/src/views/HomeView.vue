<template>
  <div class="home">
    <el-container>
      <el-header class="header">
        <span class="logo">股票分析助手</span>
        <div class="user">
          <span>{{ userStore.user?.username }}</span>
          <el-button type="primary" link @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <el-card shadow="never" class="welcome">
          <h2>欢迎使用</h2>
          <p>当前为 Demo 初始版本，后续将开放：</p>
          <ul>
            <li>综合选股</li>
            <li>持仓助手</li>
            <li>数据与定时任务</li>
          </ul>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  userStore.loadUserFromStorage()
})

function handleLogout() {
  userStore.setLogout()
  router.push('/login')
}
</script>

<style scoped>
.home {
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
.main {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}
.welcome {
  border-radius: 12px;
}
.welcome h2 {
  margin-top: 0;
  color: #1e3a5f;
}
.welcome ul {
  color: #606266;
}
</style>
