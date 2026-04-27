/**
 * useAskThread · 通用追问 thread 管理
 *
 * 迁移自 static/js/ask-panel.js 的业务逻辑部分（DOM 渲染部分由 AskPanel.vue 重写）。
 * 保留 V0.7 的 API 契约：scope + ref_type + ref_id + context_payload
 *
 * 用法：
 *   const { messages, busy, error, loadExisting, ask } = useAskThread({
 *     scope: 'practice_explain', refType: 'explanation', refId: 'abc123',
 *     contextPayload: { sentence: '...' },
 *   })
 *
 * @typedef {{ role: 'user'|'assistant', content: string, pending?: boolean }} AskMessage
 * @typedef {Object} UseAskThreadOptions
 * @property {string} scope
 * @property {string} refType
 * @property {string|number} refId
 * @property {Object} [contextPayload]
 */

import { ref } from 'vue'
import { useAuthFetch, getErrorMessage } from './useAuthFetch'
import { API } from '@/config'

/**
 * @param {UseAskThreadOptions} opts
 */
export function useAskThread(opts) {
  const { scope, refType, refId, contextPayload = {} } = opts
  if (!scope || !refType || !refId) {
    throw new Error('useAskThread: scope/refType/refId 必填')
  }

  const { authFetch } = useAuthFetch()
  /** @type {import('vue').Ref<AskMessage[]>} */
  const messages = ref([])
  const busy = ref(false)
  const error = ref('')
  const threadId = ref(null)

  /**
   * 加载同 refId 已有 thread，若无则保持空状态
   */
  async function loadExisting() {
    if (threadId.value != null) return
    try {
      const listResp = await authFetch(
        `${API.ASK}/threads?scope=${encodeURIComponent(scope)}` +
          `&ref_type=${encodeURIComponent(refType)}` +
          `&ref_id=${encodeURIComponent(refId)}&limit=1`
      )
      if (!listResp.ok) return
      const listData = await listResp.json()
      if (!listData.items || !listData.items.length) return

      const existing = listData.items[0]
      const threadResp = await authFetch(`${API.ASK}/threads/${existing.id}`)
      if (!threadResp.ok) return
      const thread = await threadResp.json()

      threadId.value = thread.id
      messages.value = (thread.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
      }))
    } catch {
      // 静默失败，允许用户开启新 thread
    }
  }

  /**
   * @param {string} question
   */
  async function ask(question) {
    const q = (question || '').trim()
    if (!q || busy.value) return
    busy.value = true
    error.value = ''

    messages.value.push({ role: 'user', content: q })
    const pendingIdx = messages.value.length
    messages.value.push({ role: 'assistant', content: '思考中…', pending: true })

    try {
      let resp
      if (threadId.value == null) {
        resp = await authFetch(`${API.ASK}/threads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scope,
            ref_type: refType,
            ref_id: String(refId),
            context: contextPayload,
            question: q,
          }),
        })
      } else {
        resp = await authFetch(`${API.ASK}/threads/${threadId.value}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q }),
        })
      }

      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`)

      if (threadId.value == null) {
        threadId.value = data.thread_id
        // 首轮返回 messages 数组，第 1 条是 assistant 回答
        const answer = data.messages?.[1]?.content || ''
        messages.value[pendingIdx] = { role: 'assistant', content: answer }
      } else {
        messages.value[pendingIdx] = { role: 'assistant', content: data.answer || '' }
      }
    } catch (err) {
      // 回滚 pending
      messages.value.splice(pendingIdx, 1)
      error.value = getErrorMessage(err, '追问失败')
    } finally {
      busy.value = false
    }
  }

  function reset() {
    threadId.value = null
    messages.value = []
    error.value = ''
  }

  return {
    threadId,
    messages,
    busy,
    error,
    loadExisting,
    ask,
    reset,
  }
}
