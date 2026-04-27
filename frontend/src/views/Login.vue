<script setup>
// Login · 登录 / 注册 双 Tab
// 登录用密码换 token，不走 useAuthFetch（避免 401 被当作 token 过期触发跳转）
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref('login') // login | register
const email = ref('')
const password = ref('')
const password2 = ref('')
const displayName = ref('')
const submitting = ref(false)
const error = ref('')

const isLogin = computed(() => mode.value === 'login')
const ctaLabel = computed(() => {
  if (submitting.value) return isLogin.value ? '登录中...' : '注册中...'
  return isLogin.value ? '登录' : '注册并登录'
})

function switchMode(m) {
  if (mode.value === m) return
  mode.value = m
  error.value = ''
  password2.value = ''
}

async function onSubmit() {
  if (!email.value || !password.value) {
    error.value = '请输入邮箱和密码'
    return
  }
  if (!isLogin.value) {
    if (password.value.length < 8) {
      error.value = '密码至少 8 位'
      return
    }
    if (password.value !== password2.value) {
      error.value = '两次密码不一致'
      return
    }
  }

  submitting.value = true
  error.value = ''
  try {
    const url = isLogin.value ? '/auth/login' : '/auth/register'
    const body = isLogin.value
      ? { email: email.value, password: password.value }
      : {
          email: email.value,
          password: password.value,
          display_name: displayName.value.trim() || null,
        }
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      error.value =
        data.detail || data.error || (isLogin.value ? '邮箱或密码错误' : '注册失败')
      return
    }
    authStore.setAuth(data.token, data.user)
    const redirect = localStorage.getItem('v2:__redirect_after_login') || '/'
    localStorage.removeItem('v2:__redirect_after_login')
    router.push(redirect)
  } catch (err) {
    error.value = err.message || '网络错误，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login">
    <h1>{{ isLogin ? '登录' : '注册' }}</h1>

    <nav class="tabs">
      <button
        type="button"
        :class="{ active: isLogin }"
        @click="switchMode('login')"
      >
        登录
      </button>
      <button
        type="button"
        :class="{ active: !isLogin }"
        @click="switchMode('register')"
      >
        注册
      </button>
    </nav>

    <form @submit.prevent="onSubmit" class="form">
      <label>
        邮箱
        <input
          v-model="email"
          type="email"
          autocomplete="email"
          required
          placeholder="you@example.com"
        />
      </label>

      <label v-if="!isLogin">
        昵称（可选）
        <input
          v-model="displayName"
          type="text"
          autocomplete="nickname"
          placeholder="想让 Alex 怎么叫你"
        />
      </label>

      <label>
        密码
        <input
          v-model="password"
          type="password"
          :autocomplete="isLogin ? 'current-password' : 'new-password'"
          required
          :placeholder="isLogin ? '' : '至少 8 位'"
        />
      </label>

      <label v-if="!isLogin">
        再输一次密码
        <input
          v-model="password2"
          type="password"
          autocomplete="new-password"
          required
        />
      </label>

      <button type="submit" :disabled="submitting" class="primary">
        {{ ctaLabel }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>
    </form>

    <p class="note">
      {{ isLogin ? '还没有账号？' : '已有账号？' }}
      <a
        href="#"
        class="switch-link"
        @click.prevent="switchMode(isLogin ? 'register' : 'login')"
      >
        {{ isLogin ? '注册一个' : '去登录' }}
      </a>
    </p>
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
  margin: 0 0 var(--space-4);
  color: var(--accent);
}
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: var(--space-5);
  border-bottom: 1px solid var(--border);
}
.tabs button {
  flex: 1;
  padding: var(--space-3) 0;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-2);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color var(--duration) var(--ease),
    border-color var(--duration) var(--ease);
}
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
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
  font-size: 13px;
  text-align: center;
}
.switch-link {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
}
.switch-link:hover {
  text-decoration: underline;
}
</style>
