<script setup>
/**
 * Chat · 主战场 1 · Phase 2a 基础结构
 * 交付：登录 → 发送 → SSE → 回复 → 历史
 *
 * Phase 2b 追加：hands-free / STT 接入 / TTS 自动朗读 / AskDrawer / ExplanationModal / VoiceSettings
 * Phase 2b keep-alive 决策：<keep-alive include="Chat,Practice"> · onDeactivated 清理 ttsQueue
 */
import { ref, onMounted, nextTick, useTemplateRef } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useChat } from '@/composables/useChat'
import { useTTS } from '@/composables/useTTS'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import HistorySidebar from '@/components/chat/HistorySidebar.vue'

defineOptions({ name: 'Chat' }) // keep-alive include 用

const chatStore = useChatStore()
const { sendMessage, streaming } = useChat()
const { enqueue: ttsEnqueue } = useTTS()
const { authFetch } = useAuthFetch()

const sidebarOpen = ref(false)
const scrollBox = useTemplateRef('scrollBox')
const toast = ref({ show: false, text: '', type: 'info' })

function showToast(text, type = 'info', duration = 2500) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

async function onSend(text) {
  const result = await sendMessage(text)
  if (!result.ok) {
    showToast(result.error || '发送失败', 'error')
  }
  await nextTick()
  scrollToBottom()
}

async function onNewChat() {
  chatStore.newSession()
  sidebarOpen.value = false
  showToast('新对话已开始', 'info', 1500)
  await nextTick()
  scrollToBottom()
}

async function onSelectSession(sid) {
  try {
    const resp = await authFetch(`${API.HISTORY}/${sid}/messages`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    chatStore.loadSession(sid, data.messages || [])
    sidebarOpen.value = false
    await nextTick()
    scrollToBottom()
  } catch (err) {
    showToast(err.message, 'error')
  }
}

function scrollToBottom() {
  const el = scrollBox.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div class="chat-page">
    <header class="topbar">
      <button class="icon-btn" @click="sidebarOpen = true" aria-label="历史">☰</button>
      <div class="title">Speakeasy</div>
      <button
        class="icon-btn"
        :class="{ on: chatStore.autoPlay }"
        @click="chatStore.toggleAutoPlay()"
        aria-label="自动朗读"
        :title="chatStore.autoPlay ? '自动朗读已开' : '自动朗读已关'"
      >
        {{ chatStore.autoPlay ? '🔊' : '🔇' }}
      </button>
    </header>

    <div ref="scrollBox" class="messages">
      <div v-if="chatStore.messages.length === 0" class="empty">
        <p>👋 Hey, I'm Alex. Type a message to start.</p>
        <p class="hint">Phase 2b 会在此加回话题卡片和自动开场白</p>
      </div>
      <ChatBubble
        v-for="m in chatStore.messages"
        :key="m.id"
        :role="m.role"
        :content="m.content"
        :streaming="m.streaming"
        @tts-request="ttsEnqueue($event, { manual: true })"
      />
    </div>

    <ChatInput
      :disabled="streaming"
      :placeholder="streaming ? 'Alex 正在回复...' : '说点什么... (Shift+Enter 换行)'"
      @send="onSend"
    />

    <Transition name="slide">
      <div v-if="sidebarOpen" class="drawer-overlay" @click.self="sidebarOpen = false">
        <HistorySidebar
          v-model:active-id="chatStore.sessionId"
          @select="onSelectSession"
          @new-chat="onNewChat"
          @close="sidebarOpen = false"
        />
      </div>
    </Transition>

    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.text }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  background: var(--bg);
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-overlay);
  backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}
.title {
  font-weight: 600;
  color: var(--accent);
}
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 18px;
  color: var(--text-2);
}
.icon-btn:active {
  background: var(--bg);
}
.icon-btn.on {
  color: var(--accent);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) 0;
  -webkit-overflow-scrolling: touch;
}
.empty {
  text-align: center;
  padding: var(--space-6) var(--space-4);
  color: var(--text-3);
}
.empty p {
  margin: 0 0 var(--space-2);
}
.hint {
  font-size: 12px;
  opacity: 0.6;
}
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: var(--z-drawer);
  display: flex;
}
.slide-enter-active,
.slide-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.slide-enter-active > :deep(.sidebar),
.slide-leave-active > :deep(.sidebar) {
  transition: transform var(--duration) var(--ease);
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
}
.slide-enter-from > :deep(.sidebar),
.slide-leave-to > :deep(.sidebar) {
  transform: translateX(-100%);
}
.toast {
  position: fixed;
  bottom: calc(var(--safe-bottom) + 88px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--text-1);
  color: var(--text-inverse);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  font-size: 13px;
  z-index: var(--z-toast);
}
.toast.error {
  background: #c6463a;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>
