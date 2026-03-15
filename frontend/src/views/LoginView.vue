<template>
  <div class="login-wrap">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <span class="title">股票分析助手</span>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="0"
        size="large"
        @submit.prevent="onSubmit"
      >
        <el-form-item prop="username">
          <el-select
            v-model="form.username"
            placeholder="请选择用户"
            clearable
            style="width: 100%"
            @keyup.enter="onSubmit"
          >
            <el-option
              v-for="name in usernameOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width: 100%" @click="onSubmit">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { login } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const usernameOptions = ['杨佳兴', '王悦']

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请选择用户', trigger: 'change' }],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate((valid) => {
    if (!valid) return
  })
  loading.value = true
  try {
    const { data } = await login({ username: form.username.trim() })
    userStore.setLogin(data.access_token, data.user)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: unknown) {
    const err = e as {
      message?: string
      response?: { status?: number; data?: { detail?: string; debug?: string } }
    }
    const statusCode = err?.response?.status
    const detail = err?.response?.data?.detail
    const debug = err?.response?.data?.debug
    if (statusCode === 401 && detail) {
      ElMessage.error(detail)
    } else if (statusCode && statusCode >= 500) {
      ElMessage.error(debug ? `服务器错误: ${debug}` : '服务器 500，请查看后端日志 backend/logs/app.log')
    } else if (!statusCode || statusCode === 0) {
      ElMessage.error(err?.message ? `请求失败: ${err.message}` : '网络异常，请确认后端已启动 (端口 8000)')
    } else {
      ElMessage.error(detail || '登录失败')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
}
.login-card {
  width: 380px;
  border-radius: 12px;
}
.title {
  font-size: 1.25rem;
  font-weight: 600;
}
</style>
