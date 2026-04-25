/**
 * useChat · 发消息核心流程
 *
 * 替代 static/js/app.js:139-216 的 sendMessage 函数。
 * SSE 流由 useSSE 驱动；流完后消息写入 chatStore，触发 TTS 队列。
 *
 * 注：后端 /chat/stream 返回的是 SSE 格式（`data: {...}\n\n`），不是 NDJSON。
 *    所以这里用 useSSE 的 text 模式自己切 SSE 分隔符。
 */

import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useSSE } from './useSSE'
import { useTTS } from './useTTS'
import { API, CHAT } from '@/config'

export function useChat() {
  const chatStore = useChatStore()
  const authStore = useAuthStore()
  const { stream: sseStream, abort: sseAbort, streaming } = useSSE()
  const { enqueue: ttsEnqueue } = useTTS()

  /**
   * @param {string} text 用户输入
   * @returns {Promise<{ ok: boolean, error?: string }>}
   */
  async function sendMessage(text) {
    const trimmed = text?.trim()
    if (!trimmed) return { ok: false, error: 'EMPTY_INPUT' }

    // 用户气泡
    chatStore.addMessage({ role: 'user', content: trimmed })

    // AI 气泡 · loading 态
    const aiId = chatStore.addMessage({ role: 'assistant', content: '', streaming: true })

    // 最近 N 轮上下文（不含刚加的 AI 空气泡）
    const history = chatStore.messages
      .filter((m) => m.id !== aiId && m.content)
      .slice(-CHAT.CONTEXT_TAIL_SIZE)
      .map(({ role, content }) => ({ role, content }))

    let full = ''
    let buf = ''

    try {
      await sseStream(
        API.CHAT_STREAM,
        {
          session_id: chatStore.sessionId,
          message: trimmed,
          history,
        },
        {
          mode: 'text',
          onDelta: (chunk) => {
            // 后端返回 SSE 格式（`data: {...}\n\n`），分隔后 JSON parse
            buf += chunk
            const parts = buf.split('\n\n')
            buf = parts.pop()
            for (const part of parts) {
              if (!part.startsWith('data: ')) continue
              let evt
              try {
                evt = JSON.parse(part.slice(6))
              } catch {
                continue
              }
              if (evt.type === 'delta' && evt.content != null) {
                full += evt.content
                chatStore.patchMessage(aiId, { content: full, streaming: true })
              } else if (evt.type === 'done') {
                chatStore.patchMessage(aiId, { content: full, streaming: false })
                if (chatStore.autoPlay) ttsEnqueue(full)
              } else if (evt.type === 'error') {
                chatStore.removeMessage(aiId)
                throw new Error(evt.message || 'AI 回复失败')
              }
            }
          },
          onError: (err) => {
            // 网络错误 · 清掉 AI 空气泡
            if (!full) chatStore.removeMessage(aiId)
            throw err
          },
        }
      )
      return { ok: true }
    } catch (err) {
      if (!full) chatStore.removeMessage(aiId)
      return { ok: false, error: err.message || '网络错误' }
    }
  }

  return {
    sendMessage,
    streaming,
    abortStream: sseAbort,
    isAuthenticated: () => authStore.isAuthenticated,
  }
}
