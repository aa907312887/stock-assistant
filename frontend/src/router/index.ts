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
        {
          path: 'market-temperature',
          name: 'market-temperature',
          component: () => import('@/views/MarketTemperatureView.vue'),
        },
        { path: 'stock-screening', name: 'stock-screening', component: () => import('@/views/StockScreeningView.vue') },
        {
          path: 'fundamental-analysis',
          name: 'fundamental-analysis',
          component: () => import('@/views/FundamentalAnalysisView.vue'),
        },
        { path: 'stock-basic', name: 'stock-basic', component: () => import('@/views/StockBasicView.vue') },
        { path: 'sync-jobs', name: 'sync-jobs', component: () => import('@/views/SyncJobMonitorView.vue') },
        { path: 'sync-tasks', name: 'sync-tasks', component: () => import('@/views/SyncTaskListView.vue') },
        {
          path: 'personal-holdings',
          name: 'personal-holdings',
          component: () => import('@/views/PersonalHoldingsView.vue'),
        },
        {
          path: 'strategy/chong-gao-hui-luo',
          name: 'strategy-chong-gao-hui-luo',
          component: () => import('@/views/ChongGaoHuiLuoView.vue'),
        },
        {
          path: 'strategy/panic-pullback',
          name: 'strategy-panic-pullback',
          component: () => import('@/views/PanicPullbackView.vue'),
        },
        {
          path: 'strategy/bottom-consolidation-breakout',
          name: 'strategy-bottom-consolidation-breakout',
          component: () => import('@/views/BottomConsolidationBreakoutView.vue'),
        },
        {
          path: 'strategy/ma-golden-cross',
          name: 'strategy-ma-golden-cross',
          component: () => import('@/views/MAGoldenCrossView.vue'),
        },
        {
          path: 'strategy/ma60-slope-buy',
          name: 'strategy-ma60-slope-buy',
          component: () => import('@/views/Ma60SlopeBuyView.vue'),
        },
        {
          path: 'strategy/da-yang-hui-luo',
          name: 'strategy-da-yang-hui-luo',
          component: () => import('@/views/DaYangHuiLuoView.vue'),
        },
        {
          path: 'strategy/zao-chen-shi-zi-xing',
          name: 'strategy-zao-chen-shi-zi-xing',
          component: () => import('@/views/ZaoChenShiZiXingView.vue'),
        },
        {
          path: 'strategy/di-wei-lian-yang',
          name: 'strategy-di-wei-lian-yang',
          component: () => import('@/views/DiWeiLianYangView.vue'),
        },
        {
          path: 'strategy/pe-value-investment',
          name: 'strategy-pe-value-investment',
          component: () => import('@/views/PeValueInvestmentView.vue'),
        },
        {
          path: 'backtest/history',
          name: 'backtest-history',
          component: () => import('@/views/HistoryBacktestView.vue'),
        },
        {
          path: 'backtest/simulation',
          name: 'backtest-simulation',
          component: () => import('@/views/HistorySimulationView.vue'),
        },
        {
          path: 'paper-trading',
          name: 'paper-trading',
          component: () => import('@/views/PaperTradingView.vue'),
        },
        {
          path: 'paper-trading/:sessionId',
          name: 'paper-trading-session',
          component: () => import('@/views/PaperTradingSessionView.vue'),
        },
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
