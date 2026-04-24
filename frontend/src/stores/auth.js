/**
 * authStore · Pinia 用户认证状态
 *
 * 契约保持（来自 static/js/auth.js）：
 * - token 与 user 存 localStorage，但用 v2: 前缀命名空间（Pass 3 B4）
 * - 旧版 localStorage['token'] 双写保留，方便 /legacy/* 灰度期共存
 * - logout 由 store 内部触发路由跳转（composable 不依赖 router，Architect SF NH8）
 *
 * @typedef {Object} AuthUser
 * @property {number} [id]
 * @property {string} email
 * @property {string} [name]
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '@/router'

const V2_TOKEN_KEY = 'v2:auth.token'
const V2_USER_KEY = 'v2:auth.user'
const LEGACY_TOKEN_KEY = 'token'
const LEGACY_USER_KEY = 'speakeasy_user' // 老版用了这个 key，参考 auth.js:5

function readInitialToken() {
  try {
    return (
      localStorage.getItem(V2_TOKEN_KEY) ||
      localStorage.getItem(LEGACY_TOKEN_KEY) ||
      null
    )
  } catch {
    return null
  }
}

function readInitialUser() {
  try {
    const raw = localStorage.getItem(V2_USER_KEY) || localStorage.getItem(LEGACY_USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(readInitialToken())
  const user = ref(readInitialUser())

  const isAuthenticated = computed(() => !!token.value)

  /**
   * @param {string} newToken
   * @param {AuthUser | null} newUser
   */
  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser || null
    try {
      localStorage.setItem(V2_TOKEN_KEY, newToken)
      localStorage.setItem(V2_USER_KEY, JSON.stringify(newUser || null))
      // 双写兼容 legacy 老版 HTML 页面直接读 token
      localStorage.setItem(LEGACY_TOKEN_KEY, newToken)
    } catch {
      // localStorage 写失败静默降级，state 仍然有效
    }
  }

  /**
   * 启动时静默校验 · V0.9.2
   * 有 token 就试调 /auth/me：
   *   200 → 更新 user 信息
   *   401 → 静默清 localStorage（不跳转，由 router guard 统一处理）
   *   网络错误 → 保留 token（可能离线，用户可继续浏览已缓存页面）
   */
  async function initFromStorage() {
    if (!token.value) return
    try {
      const resp = await fetch('/auth/me', {
        headers: { Authorization: 'Bearer ' + token.value },
      })
      if (resp.status === 401) {
        logout({ silent: true })
        return
      }
      if (resp.ok) {
        const data = await resp.json()
        if (data.user) {
          user.value = data.user
          try {
            localStorage.setItem(V2_USER_KEY, JSON.stringify(data.user))
          } catch {
            /* ignore */
          }
        }
      }
      // 其它状态码（5xx / 网络）静默忽略 · 不清 token
    } catch {
      // 离线或 DNS 错 · 保留 token
    }
  }

  /**
   * 登出 + 清 storage + 路由跳登录
   * @param {Object} [opts]
   * @param {boolean} [opts.silent] 不跳 /login（用于 401 静默清理）
   * @param {string} [opts.redirectTo] 记忆重定向路径（回 /login 后登录完跳回来）
   */
  function logout({ silent = false, redirectTo = null } = {}) {
    token.value = null
    user.value = null
    try {
      localStorage.removeItem(V2_TOKEN_KEY)
      localStorage.removeItem(V2_USER_KEY)
      localStorage.removeItem(LEGACY_TOKEN_KEY)
      localStorage.removeItem(LEGACY_USER_KEY)
    } catch {
      /* ignore */
    }
    if (silent) return
    if (redirectTo) {
      try {
        localStorage.setItem('v2:__redirect_after_login', redirectTo)
      } catch {
        /* ignore */
      }
    }
    router.push({ name: 'login' })
  }

  return {
    token,
    user,
    isAuthenticated,
    setAuth,
    logout,
    initFromStorage,
  }
})
