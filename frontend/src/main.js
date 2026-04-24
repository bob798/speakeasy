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

// 启动时静默校验 token（/auth/me）· 401 则清；其余情况保留 · V0.9.2
const authStore = useAuthStore(pinia)
authStore.initFromStorage().finally(() => {
  app.mount('#app')
})
