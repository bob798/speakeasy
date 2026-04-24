/**
 * useAuthFetch · 带鉴权的 fetch 封装
 *
 * 迁移自 static/js/auth.js:40-50 的 authFetch，语义保持：
 * - 自动附加 Authorization: Bearer {token}
 * - 401 自动触发 authStore.logout()（由 store 触发路由跳转，本 composable 不依赖 router）
 *
 * 两种用法：
 *   const { authFetch } = useAuthFetch()
 *   const resp = await authFetch('/chat', { method: 'POST', body: JSON.stringify(...) })
 *
 * 为防止 composable ↔ router 循环依赖，logout 由 authStore 内部调用 router.push。
 */

import { useAuthStore } from '@/stores/auth'

/**
 * @typedef {Object} AuthFetchOptions
 * @property {string} [method]
 * @property {Record<string, string>} [headers]
 * @property {any} [body]
 * @property {AbortSignal} [signal]
 * @property {RequestCredentials} [credentials]
 */

export function useAuthFetch() {
  const authStore = useAuthStore()

  /**
   * @param {string} url
   * @param {AuthFetchOptions} [options]
   * @returns {Promise<Response>}
   */
  async function authFetch(url, options = {}) {
    const token = authStore.token
    const headers = { ...(options.headers || {}) }
    if (token) headers['Authorization'] = 'Bearer ' + token

    const resp = await fetch(url, { ...options, headers })
    if (resp.status === 401) {
      // 记忆当前路径让登录后跳回来
      const currentPath =
        typeof window !== 'undefined' ? window.location.pathname + window.location.search : null
      authStore.logout({ redirectTo: currentPath })
      throw new Error('未登录或登录已过期')
    }
    return resp
  }

  /**
   * 便捷 JSON 封装：带鉴权 + JSON 序列化 + 返回解析结果
   * @param {string} url
   * @param {any} body
   * @param {AuthFetchOptions} [options]
   * @returns {Promise<any>}
   */
  async function authFetchJson(url, body, options = {}) {
    const resp = await authFetch(url, {
      method: options.method || 'POST',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      body: body == null ? undefined : JSON.stringify(body),
    })
    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`
      try {
        const err = await resp.json()
        detail = err.detail || err.error || detail
      } catch {
        /* ignore parse error */
      }
      throw new Error(detail)
    }
    return resp.json()
  }

  return {
    authFetch,
    authFetchJson,
  }
}
