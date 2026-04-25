/**
 * useAuthFetch 单测 · 4 分支覆盖（200/401/500/network）
 * Plan P1-T1 完成判据
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthFetch } from '../useAuthFetch'
import { useAuthStore } from '@/stores/auth'

// Mock router（useAuthStore.logout 会调 router.push）
vi.mock('@/router', () => ({
  default: { push: vi.fn() },
}))

describe('useAuthFetch', () => {
  let fetchMock

  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock = vi.fn()
    global.fetch = fetchMock
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('200 路径: 附加 Authorization 头 + 返回 Response', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('test-token-123', { email: 'a@b.com' })

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    )

    const { authFetch } = useAuthFetch()
    const resp = await authFetch('/api/foo', { method: 'GET' })

    expect(resp.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/foo',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token-123' }),
      })
    )
  })

  it('401 路径: 自动 logout() 并抛错', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('stale-token', { email: 'x@y.com' })
    const logoutSpy = vi.spyOn(authStore, 'logout')

    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 401 }))

    const { authFetch } = useAuthFetch()
    await expect(authFetch('/api/protected')).rejects.toThrow('未登录或登录已过期')
    expect(logoutSpy).toHaveBeenCalledWith(expect.objectContaining({ redirectTo: expect.any(String) }))
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('500 路径: authFetchJson 解析 error detail', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: '服务器内部错误' }), { status: 500 })
    )

    const { authFetchJson } = useAuthFetch()
    await expect(authFetchJson('/api/boom', { x: 1 })).rejects.toThrow('服务器内部错误')
  })

  it('network 错误路径: 透传 fetch 抛出的错误', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const { authFetch } = useAuthFetch()
    await expect(authFetch('/api/offline')).rejects.toThrow('Failed to fetch')
  })

  it('无 token 时不附加 Authorization 头', async () => {
    fetchMock.mockResolvedValueOnce(new Response('ok', { status: 200 }))
    const { authFetch } = useAuthFetch()
    await authFetch('/public', {})
    const [, options] = fetchMock.mock.calls[0]
    expect(options.headers).not.toHaveProperty('Authorization')
  })

  it('authFetchJson 序列化 body 并发 POST', async () => {
    const authStore = useAuthStore()
    authStore.setAuth('t', null)

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, echo: 'hi' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const { authFetchJson } = useAuthFetch()
    const result = await authFetchJson('/echo', { msg: 'hi' })
    expect(result).toEqual({ ok: true, echo: 'hi' })

    const [, options] = fetchMock.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(options.body)).toEqual({ msg: 'hi' })
  })
})
