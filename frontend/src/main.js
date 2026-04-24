import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/tokens.css'
import './styles/reset.css'
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// 全局 viewport 高度变量 · iOS 键盘弹出时实时响应
function syncViewportHeight() {
  const vv = window.visualViewport
  const h = vv ? vv.height : window.innerHeight
  document.documentElement.style.setProperty('--app-vh', h + 'px')
  document.documentElement.style.setProperty(
    '--kb-offset',
    vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) + 'px' : '0px'
  )
}
syncViewportHeight()
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', syncViewportHeight)
  window.visualViewport.addEventListener('scroll', syncViewportHeight)
}
window.addEventListener('resize', syncViewportHeight)
window.addEventListener('orientationchange', syncViewportHeight)

// 启动时静默校验 token（/auth/me）· 401 则清；其余情况保留 · V0.9.2
const authStore = useAuthStore(pinia)
authStore.initFromStorage().finally(() => {
  app.mount('#app')
})
