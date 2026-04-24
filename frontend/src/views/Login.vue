<script setup>
// Login · 次战场
// Phase 0.5 (D5) · 冒烟里程碑 gate
// Phase 2.5 (D12.5) · polish（401 全链路 + 记忆重定向 e2e）
//
// 当前占位：Phase 1 交付 useAuthFetch + authStore 后，此处接入实现
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
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
    // 占位：直接调后端 /auth/login（Phase 1 会换成 useAuthFetch）
    const resp = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      error.value = data.detail || `登录失败 (${resp.status})`
      return
    }
    const data = await resp.json()
    // v2: 命名空间（Pass 3 B4）
    localStorage.setItem('v2:auth.token', data.token)
    localStorage.setItem('v2:auth.user', JSON.stringify(data.user || {}))
    // 兼容老版同步（灰度期 /legacy/ 需要）
    localStorage.setItem('token', data.token)

    const redirect = localStorage.getItem('v2:__redirect_after_login') || '/'
    localStorage.removeItem('v2:__redirect_after_login')
    router.push(redirect)
  } catch (err) {
    error.value = `网络错误: ${err.message}`
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
    <p class="note">Phase 0.5 冒烟里程碑 · Phase 2.5 polish 后补注册</p>
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
  font-size: 16px; /* 防 iOS 自动缩放 */
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
