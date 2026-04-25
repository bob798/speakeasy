/**
 * useSSE · fetch() 流式读取封装（POST JSON + 返回 NDJSON/SSE line-delimited）
 *
 * 替代 static/js/app.js:172-216 的 SSE 实现。关键修复（Architect Tradeoff 2 + R3）：
 * - 每次 start 新建 AbortController
 * - Vue 组件 unmount 时自动 abort（防内存泄漏）
 * - Chat.vue 用 keep-alive 时，onDeactivated 不 abort（让 Alex 回复流完 —— Architect synthesis）
 *
 * 用法：
 *   const { stream, abort, streaming } = useSSE()
 *   await stream('/chat', { session_id, message }, {
 *     onDelta: (chunk) => { ... },
 *     onDone:  (fullText) => { ... },
 *     onError: (err) => { ... },
 *   })
 *
 * @typedef {Object} SSECallbacks
 * @property {(chunk: string) => void} onDelta
 * @property {(full: string) => void} [onDone]
 * @property {(err: Error) => void} [onError]
 * @property {(evt: any) => void} [onEvent] · NDJSON 模式：拿到完整 JSON 对象
 */

import { ref, onBeforeUnmount } from 'vue'
import { useAuthFetch } from './useAuthFetch'

export function useSSE() {
  const streaming = ref(false)
  let _controller = null

  /**
   * 流式读取 · 支持两种模式：
   *   mode=text: 按字符拼接（老版 /chat 返回 plain-text 流）
   *   mode=ndjson: 按行 parse JSON（V0.7 /practice/explain/stream）
   *
   * @param {string} url
   * @param {any} body
   * @param {SSECallbacks & { mode?: 'text' | 'ndjson', method?: string }} cb
   */
  async function stream(url, body, cb) {
    abort() // 清理旧连接
    _controller = new AbortController()
    streaming.value = true

    const { authFetch } = useAuthFetch()
    const mode = cb.mode || 'text'
    let full = ''

    try {
      const resp = await authFetch(url, {
        method: cb.method || 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body == null ? undefined : JSON.stringify(body),
        signal: _controller.signal,
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`SSE 失败: HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        if (mode === 'ndjson') {
          buffer += chunk
          let nl = buffer.indexOf('\n')
          while (nl !== -1) {
            const line = buffer.slice(0, nl).trim()
            buffer = buffer.slice(nl + 1)
            nl = buffer.indexOf('\n')
            if (!line) continue
            try {
              const obj = JSON.parse(line)
              cb.onEvent?.(obj)
            } catch {
              // 忽略不完整行
            }
          }
        } else {
          full += chunk
          cb.onDelta?.(chunk)
        }
      }

      // NDJSON 尾部残留
      if (mode === 'ndjson' && buffer.trim()) {
        try {
          cb.onEvent?.(JSON.parse(buffer.trim()))
        } catch {
          /* ignore */
        }
      }

      cb.onDone?.(full)
    } catch (err) {
      if (err.name === 'AbortError') {
        // 主动中断不算错误
      } else {
        cb.onError?.(err)
      }
    } finally {
      streaming.value = false
      _controller = null
    }
  }

  function abort() {
    if (_controller) {
      _controller.abort()
      _controller = null
    }
    streaming.value = false
  }

  onBeforeUnmount(() => {
    abort()
  })

  return {
    streaming,
    stream,
    abort,
  }
}
