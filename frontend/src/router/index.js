import { createRouter, createWebHistory } from 'vue-router'

// Lazy-loaded views (code-split by route)
const Home = () => import('@/views/Home.vue')
const Chat = () => import('@/views/Chat.vue')
const Articles = () => import('@/views/Articles.vue')
const Vocabulary = () => import('@/views/Vocabulary.vue')
const Translate = () => import('@/views/Translate.vue')
const Polish = () => import('@/views/Polish.vue')
const Memory = () => import('@/views/Memory.vue')
const Review = () => import('@/views/Review.vue')
const ReviewHome = () => import('@/views/ReviewHome.vue')
const BbcArticleReview = () => import('@/views/BbcArticleReview.vue')
const Login = () => import('@/views/Login.vue')
const NotFound = () => import('@/views/NotFound.vue')

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    { path: '/', name: 'home', component: Home, meta: { requiresAuth: true } },
    { path: '/chat', name: 'chat', component: Chat, meta: { requiresAuth: true } },
    {
      path: '/articles',
      name: 'Articles',
      component: Articles,
      meta: { requiresAuth: true },
    },
    {
      path: '/practice',
      redirect: '/articles',
    },
    {
      path: '/vocabulary',
      name: 'Vocabulary',
      component: Vocabulary,
      meta: { requiresAuth: true },
    },
    {
      path: '/translate',
      name: 'translate',
      component: Translate,
      meta: { requiresAuth: true },
    },
    {
      path: '/polish',
      name: 'polish',
      component: Polish,
      meta: { requiresAuth: true },
    },
    {
      path: '/memory',
      name: 'memory',
      component: Memory,
      meta: { requiresAuth: true },
    },
    {
      path: '/review',
      name: 'review-home',
      component: ReviewHome,
      meta: { requiresAuth: true },
    },
    {
      path: '/review/:sessionId',
      name: 'review',
      component: Review,
      meta: { requiresAuth: true },
    },
    {
      path: '/bbc-review/:slug',
      name: 'bbc-review',
      component: BbcArticleReview,
      meta: { requiresAuth: true },
    },
    { path: '/login', name: 'login', component: Login, meta: { requiresAuth: false } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound },
  ],
  scrollBehavior(to, from, saved) {
    return saved || { top: 0 }
  },
})

// Phase 1 完善：读 authStore 判断；此处先用 localStorage 占位（兼容老版 key）
router.beforeEach((to) => {
  if (to.meta.requiresAuth === false) return true
  const token = localStorage.getItem('v2:auth.token') || localStorage.getItem('token')
  if (!token) {
    // 记忆重定向（Phase 0.5 Login 冒烟 + Phase 2.5 polish）
    localStorage.setItem('v2:__redirect_after_login', to.fullPath)
    return { name: 'login' }
  }
  return true
})

export default router
