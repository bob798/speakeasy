/**
 * useStats · 获取首页 dashboard 数据 (/stats/today)
 * V0.9.1
 */

import { ref } from 'vue'
import { useAuthFetch, getErrorMessage } from './useAuthFetch'
import { API } from '@/config'

export function useStats() {
  const stats = ref(null)
  const loading = ref(false)
  const error = ref('')
  const { authFetch } = useAuthFetch()

  async function fetchToday() {
    loading.value = true
    error.value = ''
    try {
      const resp = await authFetch(`${API.BASE}/stats/today`)
      if (!resp.ok) throw new Error('加载失败')
      stats.value = await resp.json()
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  return { stats, loading, error, fetchToday }
}
