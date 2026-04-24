/**
 * chatStore · 当前会话 + 消息历史 + 偏好
 *
 * 替代 static/js/app.js 的全局变量（sessionId / chatHistory / autoPlay / _roundCount）
 * keep-alive 策略下 store 持久化 · Chat.vue 切 Memory 再回来，消息不丢
 *
 * 注意 Pass 3 B4：不启用 pinia-plugin-persistedstate · 刷新后由后端 /history 拉取
 *
 * @typedef {{ role: 'user' | 'assistant' | 'system', content: string, streaming?: boolean, id?: string }} ChatMessage
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function newSessionId() {
  return (
    's-' +
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).slice(2, 8)
  )
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref(newSessionId())
  /** @type {import('vue').Ref<ChatMessage[]>} */
  const messages = ref([])
  const autoPlay = ref(false)
  const handsFree = ref(false)
  const ttsProvider = ref('edge') // edge | doubao | webspeech
  const ttsSpeed = ref('+0%') // -40% -20% +0% +20%
  const sttStatus = ref('idle') // idle | recording | processing | degraded | error
  const sttStatusHint = ref('')

  const userMessageCount = computed(() => messages.value.filter((m) => m.role === 'user').length)
  const roundCount = computed(() => messages.value.filter((m) => m.role === 'assistant').length)

  let _msgSeq = 0

  function _nextId() {
    return 'm-' + ++_msgSeq
  }

  /**
   * @param {Omit<ChatMessage, 'id'>} msg
   * @returns {string} message id
   */
  function addMessage(msg) {
    const id = _nextId()
    messages.value.push({ ...msg, id })
    return id
  }

  /**
   * 就地更新一条消息的 content / streaming 状态
   * @param {string} id
   * @param {Partial<ChatMessage>} patch
   */
  function patchMessage(id, patch) {
    const idx = messages.value.findIndex((m) => m.id === id)
    if (idx >= 0) {
      messages.value[idx] = { ...messages.value[idx], ...patch }
    }
  }

  function removeMessage(id) {
    messages.value = messages.value.filter((m) => m.id !== id)
  }

  function newSession() {
    sessionId.value = newSessionId()
    messages.value = []
    _msgSeq = 0
  }

  function loadSession(sid, msgs) {
    sessionId.value = sid
    messages.value = (msgs || []).map((m, i) => ({ ...m, id: 'h-' + i }))
    _msgSeq = messages.value.length
  }

  function setSTTStatus(status, hint = '') {
    sttStatus.value = status
    sttStatusHint.value = hint
  }

  function toggleAutoPlay() {
    autoPlay.value = !autoPlay.value
  }

  function toggleHandsFree() {
    handsFree.value = !handsFree.value
    // hands-free 打开时顺带开自动朗读（否则循环断链）
    if (handsFree.value) autoPlay.value = true
  }

  return {
    sessionId,
    messages,
    autoPlay,
    handsFree,
    ttsProvider,
    ttsSpeed,
    sttStatus,
    sttStatusHint,
    userMessageCount,
    roundCount,
    addMessage,
    patchMessage,
    removeMessage,
    newSession,
    loadSession,
    setSTTStatus,
    toggleAutoPlay,
    toggleHandsFree,
  }
})
