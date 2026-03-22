import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: () => import('@/views/Layout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'home', component: () => import('@/views/HomeView.vue') },
        { path: 'stock-screening', name: 'stock-screening', component: () => import('@/views/StockScreeningView.vue') },
        { path: 'stock-basic', name: 'stock-basic', component: () => import('@/views/StockBasicView.vue') },
        { path: 'sync-jobs', name: 'sync-jobs', component: () => import('@/views/SyncJobMonitorView.vue') },
        { path: 'sync-tasks', name: 'sync-tasks', component: () => import('@/views/SyncTaskListView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  const hasToken = !!userStore.token
  if (to.meta.requiresAuth && !hasToken) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.meta.guest && hasToken && to.name === 'login') {
    next({ name: 'home' })
  } else {
    next()
  }
})

export default router
