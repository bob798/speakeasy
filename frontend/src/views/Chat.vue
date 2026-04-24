<script setup>
/**
 * Chat · 主战场 1 · Phase 2a 基础 + Phase 2b 增强
 *
 * Phase 2b 新增：
 *   - Alex 自动开场白（打字机效果）
 *   - 话题卡片（空状态引导）
 *   - 点击 AI 气泡 → ExplanationModal 抽屉
 *   - STT 通过 ChatInput 内嵌 MicButton
 *   - TTS 自动朗读（autoPlay 开关）
 *
 * Phase 2b keep-alive：<keep-alive include="Chat,Practice"> · onDeactivated 不 abort SSE（让 Alex 流完）
 */
import { ref, onMounted, onActivated, onDeactivated, nextTick, useTemplateRef } from 'vue'
import { RouterLink } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useChat } from '@/composables/useChat'
import { useTTS } from '@/composables/useTTS'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import HistorySidebar from '@/components/chat/HistorySidebar.vue'
import ExplanationModal from '@/components/ExplanationModal.vue'

defineOptions({ name: 'Chat' }) // keep-alive include 用

const chatStore = useChatStore()
const { sendMessage, streaming } = useChat()
const { enqueue: ttsEnqueue, clear: ttsClear } = useTTS()
const { authFetch } = useAuthFetch()

const sidebarOpen = ref(false)
const scrollBox = useTemplateRef('scrollBox')
const chatInputRef = useTemplateRef('chatInputRef')
const toast = ref({ show: false, text: '', type: 'info' })

// 解读抽屉
const explainOpen = ref(false)
const explainTarget = ref(null)

// 话题卡片（硬编码，Phase 6+ 可做动态）
const TOPICS = [
  { emoji: '☕', label: '早餐聊聊', prompt: "Let's talk about what I had for breakfast today." },
  { emoji: '💼', label: '工作', prompt: "I'd like to talk about my job and daily work." },
  { emoji: '✈️', label: '旅行', prompt: "Let's talk about a place I'd love to travel to." },
  { emoji: '📚', label: '学习', prompt: "I want to improve my English. Can you help?" },
  { emoji: '🎬', label: '电影', prompt: "Let's chat about a movie I recently watched." },
  { emoji: '🏃', label: '运动', prompt: "Let's talk about exercise and sports." },
]
const displayedTopics = ref([])

function pickTopics() {
  const shuffled = [...TOPICS].sort(() => Math.random() - 0.5)
  displayedTopics.value = shuffled.slice(0, 3)
}

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
  pickTopics()
  showToast('新对话已开始', 'info', 1500)
  await nextTick()
  scrollToBottom()
  alexOpening()
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

function onBubbleExplain(content) {
  explainTarget.value = {
    type: 'sentence',
    content,
    context: { source: 'chat', session_id: chatStore.sessionId },
  }
  explainOpen.value = true
}

function onBubbleTTS(content) {
  ttsEnqueue(content, { manual: true })
}

function onSTTError(msg) {
  showToast(msg, 'error')
}

function onTopicClick(topic) {
  onSend(topic.prompt)
}

// ── Alex 开场白（打字机效果）────────────────────────────────────
const OPENING = "Hey! I'm Alex 👋 What's on your mind today? Type or tap the mic to speak."

function alexOpening() {
  if (chatStore.messages.length > 0) return

  const msgId = chatStore.addMessage({
    role: 'assistant',
    content: '',
    streaming: true,
  })

  let i = 0
  const timer = setInterval(() => {
    i++
    chatStore.patchMessage(msgId, {
      content: OPENING.slice(0, i),
      streaming: i < OPENING.length,
    })
    if (i >= OPENING.length) {
      clearInterval(timer)
      // 开场白不进 history context（与老版行为一致）
    }
  }, 22)
}

function scrollToBottom() {
  const el = scrollBox.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

onMounted(() => {
  pickTopics()
  if (chatStore.messages.length === 0) {
    alexOpening()
  }
  scrollToBottom()
  // 自动聚焦输入框（桌面端友好 · 移动端不会弹键盘因为需要用户手势）
  nextTick(() => chatInputRef.value?.focus())
})

// keep-alive: Chat → Memory 切回来时不重建 state；但要清 TTS 队列（Architect SF4）
onActivated(() => {
  scrollToBottom()
  nextTick(() => chatInputRef.value?.focus())
})
onDeactivated(() => {
  ttsClear()
  // SSE 不 abort，让 Alex 流完（Architect Tradeoff 2 synthesis）
})
</script>

<template>
  <div class="chat-page">
    <header class="topbar">
      <button class="icon-btn" @click="sidebarOpen = true" aria-label="历史">☰</button>
      <RouterLink class="title" to="/" aria-label="回到首页">Speakeasy</RouterLink>
      <div class="top-right">
        <button class="icon-btn" @click="onNewChat" aria-label="新对话" title="新对话">＋</button>
        <button
          class="icon-btn"
          :class="{ on: chatStore.autoPlay }"
          @click="chatStore.toggleAutoPlay()"
          aria-label="自动朗读"
          :title="chatStore.autoPlay ? '自动朗读已开' : '自动朗读已关'"
        >
          {{ chatStore.autoPlay ? '🔊' : '🔇' }}
        </button>
      </div>
    </header>

    <div ref="scrollBox" class="messages">
      <ChatBubble
        v-for="m in chatStore.messages"
        :key="m.id"
        :role="m.role"
        :content="m.content"
        :streaming="m.streaming"
        @tts-request="onBubbleTTS"
        @explain-request="onBubbleExplain"
        @click="m.role === 'assistant' && m.content && !m.streaming ? onBubbleExplain(m.content) : null"
      />

      <!-- 话题卡片：无消息时显示 -->
      <div
        v-if="chatStore.messages.length <= 1 && !streaming"
        class="topic-cards"
      >
        <button
          v-for="t in displayedTopics"
          :key="t.label"
          class="topic-card"
          @click="onTopicClick(t)"
        >
          <span class="emoji">{{ t.emoji }}</span>
          <span>{{ t.label }}</span>
        </button>
      </div>
    </div>

    <ChatInput
      ref="chatInputRef"
      :disabled="streaming"
      :placeholder="streaming ? 'Alex 正在回复...' : '说点什么... (Shift+Enter 换行)'"
      @send="onSend"
      @stt-error="onSTTError"
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

    <ExplanationModal v-model:open="explainOpen" :target="explainTarget" />

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
  text-decoration: none;
}
.top-right {
  display: flex;
  gap: var(--space-1);
  align-items: center;
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
.topic-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--space-2);
  padding: var(--space-4);
  margin-top: var(--space-3);
}
.topic-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-1);
  font-size: 13px;
  transition: transform var(--duration) var(--ease);
}
.topic-card:active {
  transform: scale(0.96);
  background: var(--accent-soft);
}
.emoji {
  font-size: 22px;
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
