<script setup>
// Login · 次战场
// Phase 0.5 冒烟里程碑 gate + Phase 2.5 polish（401 全链路 + 记忆重定向 e2e）
//
// Phase 1 已接入：useAuthFetch · useAuthStore
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAuthFetch } from '@/composables/useAuthFetch'

const router = useRouter()
const authStore = useAuthStore()
const { authFetchJson } = useAuthFetch()

const email = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref('')

async function onLogin() {
  if (!email.value || !password.value) {
    error.value = '请输入邮箱和密码'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const data = await authFetchJson('/auth/login', {
      email: email.value,
      password: password.value,
    })
    authStore.setAuth(data.token, data.user)

    const redirect = localStorage.getItem('v2:__redirect_after_login') || '/'
    localStorage.removeItem('v2:__redirect_after_login')
    router.push(redirect)
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login">
    <h1>登录</h1>
    <form @submit.prevent="onLogin" class="form">
      <label>
        邮箱
        <input v-model="email" type="email" autocomplete="email" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <button type="submit" :disabled="submitting" class="primary">
        {{ submitting ? '登录中...' : '登录' }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p class="note">Phase 0.5 冒烟 · Phase 2.5 polish 后补注册</p>
  </main>
</template>

<style scoped>
.login {
  max-width: 360px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
  padding-top: calc(var(--safe-top) + var(--space-6));
}
h1 {
  margin: 0 0 var(--space-5);
  color: var(--accent);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
label {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: 14px;
  color: var(--text-2);
}
input {
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  font-size: 16px;
}
input:focus {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
  border-color: var(--accent);
}
.primary {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius-sm);
  font-weight: 500;
  transition: background var(--duration) var(--ease);
}
.primary:active {
  background: var(--accent-hover);
}
.primary:disabled {
  opacity: 0.6;
}
.error {
  color: #c6463a;
  font-size: 13px;
  margin: 0;
}
.note {
  margin-top: var(--space-5);
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
}
</style>
