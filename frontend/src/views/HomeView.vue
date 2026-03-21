<template>
  <div class="home">
    <el-card shadow="never" class="welcome">
      <h2>欢迎使用</h2>
      <p>当前为 Demo 初始版本，已开放：</p>
      <ul>
        <li>综合选股（左侧菜单进入）</li>
        <li>持仓助手（后续开放）</li>
        <li>数据与定时任务（每日 17:00 同步）</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home {
  max-width: 960px;
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
