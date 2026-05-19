<script setup>
/**
 * Home · V0.9 重设计 · 方案 B 聊天中心化
 * 迁移自占位版本。Alex 形象 + 大输入框 + 话题卡片 + 次级导航
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useStats } from '@/composables/useStats'

const router = useRouter()
const auth = useAuthStore()
const { stats, fetchToday } = useStats()

const text = ref('')
const textareaEl = ref(null)

const greeting = computed(() => {
  const h = new Date().getHours()
  const name = auth.user?.display_name || auth.user?.email?.split('@')[0] || 'there'
  if (h < 6) return `Still up, ${name}?`
  if (h < 12) return `Morning, ${name}`
  if (h < 18) return `Hey ${name}`
  if (h < 22) return `Evening, ${name}`
  return `Late night, ${name}`
})

const TOPICS = [
  { emoji: '☕', label: '早餐', prompt: "Let's talk about what I had for breakfast today." },
  { emoji: '💼', label: '工作', prompt: "I'd like to talk about my job and daily work." },
  { emoji: '✈️', label: '旅行', prompt: "Let's talk about a place I'd love to travel to." },
  { emoji: '📚', label: '学习', prompt: "I want to improve my English. Can you help?" },
  { emoji: '🎬', label: '电影', prompt: "Let's chat about a movie I recently watched." },
  { emoji: '🎧', label: '音乐', prompt: "Let's chat about the music I like." },
  { emoji: '🏃', label: '运动', prompt: "Let's talk about exercise and sports." },
  { emoji: '🍜', label: '美食', prompt: "Let's talk about food and recipes." },
]

const displayed = computed(() => {
  const shuffled = [...TOPICS].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 6)
})

function autoGrow() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    start()
  }
}

function start() {
  const prefill = text.value.trim()
  if (prefill) {
    router.push({ path: '/chat', query: { prefill } })
  } else {
    router.push('/chat')
  }
}

function onTopic(prompt) {
  router.push({ path: '/chat', query: { prefill: prompt } })
}

onMounted(() => {
  fetchToday()
  // 桌面端自动聚焦；移动端不弹键盘（需用户主动点）
  if (window.matchMedia('(min-width: 768px)').matches) {
    textareaEl.value?.focus()
  }
})
</script>

<template>
  <main class="home">
    <!-- 顶部状态栏 -->
    <header class="topbar">
      <span class="logo">Speakeasy</span>
      <RouterLink class="history-link" to="/chat" title="历史对话" aria-label="历史对话">
        <span class="mi">📜</span>
      </RouterLink>
    </header>

    <!-- 数据条 · V0.9.1 -->
    <div v-if="stats" class="stats-band">
      <div class="chip" :class="{ hot: stats.streak_days >= 3 }">
        🔥 <span>{{ stats.streak_days }} 天连续</span>
      </div>
      <div v-if="stats.today_message_count > 0" class="chip">
        💬 <span>今日 {{ stats.today_message_count }} 条</span>
      </div>
      <RouterLink v-if="stats.due_cards > 0" to="/articles" class="chip cta">
        📝 <span>{{ stats.due_cards }} 张待复习</span>
      </RouterLink>
    </div>

    <!-- Hero · Alex 问候 -->
    <section class="hero">
      <div class="alex">
        <div class="avatar">🤖</div>
        <div class="speech">
          <h1>{{ greeting }}</h1>
          <p class="tagline">Alex 在这 · 说点什么开始今天的对话</p>
        </div>
      </div>
    </section>

    <!-- 主输入框 · V0.9 方案 B 核心 -->
    <section class="prompt-box">
      <textarea
        ref="textareaEl"
        v-model="text"
        placeholder="你今天想聊什么？(Shift+Enter 换行)"
        rows="2"
        @keydown="onKey"
        @input="autoGrow"
      ></textarea>
      <button class="start-btn" :disabled="false" @click="start" aria-label="开始聊天">
        <span v-if="text.trim()">开始聊天 →</span>
        <span v-else>随便聊聊 →</span>
      </button>
    </section>

    <!-- 话题卡片 -->
    <section class="topics">
      <p class="topics-hint">没头绪？试试这些 ↓</p>
      <div class="topics-grid">
        <button
          v-for="t in displayed"
          :key="t.label"
          class="topic-card"
          @click="onTopic(t.prompt)"
        >
          <span class="emoji">{{ t.emoji }}</span>
          <span class="label">{{ t.label }}</span>
        </button>
      </div>
    </section>

    <!-- 次级功能导航 -->
    <nav class="secondary">
      <RouterLink to="/articles" class="sec-item">
        <span class="ico">🎧</span>
        <span class="name">文章学习</span>
      </RouterLink>
      <RouterLink to="/translate" class="sec-item">
        <span class="ico">🌐</span>
        <span class="name">翻译</span>
      </RouterLink>
      <RouterLink to="/vocabulary" class="sec-item">
        <span class="ico">📖</span>
        <span class="name">生词本</span>
      </RouterLink>
      <RouterLink to="/polish" class="sec-item">
        <span class="ico">✍️</span>
        <span class="name">写作教练</span>
      </RouterLink>
      <RouterLink to="/review" class="sec-item">
        <span class="ico">📝</span>
        <span class="name">今日复习</span>
      </RouterLink>
      <RouterLink to="/memory" class="sec-item">
        <span class="ico">🧠</span>
        <span class="name">记忆管理</span>
      </RouterLink>
    </nav>
  </main>
</template>

<style scoped>
.home {
  max-width: 640px;
  margin: 0 auto;
  min-height: 100dvh;
  padding: 0 var(--space-5);
  padding-top: calc(var(--safe-top) + var(--space-3));
  padding-bottom: calc(var(--safe-bottom) + var(--space-5));
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
}
.logo {
  font-size: 15px;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.3px;
}
.history-link {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--text-2);
}
.history-link:active {
  background: var(--bg-elevated);
}

.stats-band {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  scrollbar-width: none;
  padding: var(--space-1) 0;
  margin: 0;
}
.stats-band::-webkit-scrollbar {
  display: none;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
  flex-shrink: 0;
  text-decoration: none;
}
.chip.hot {
  background: rgba(255, 156, 68, 0.1);
  border-color: rgba(255, 156, 68, 0.25);
  color: #c87020;
}
.chip.cta {
  background: var(--accent-soft);
  border-color: transparent;
  color: var(--accent);
  font-weight: 500;
}
.chip.cta:active {
  background: var(--accent);
  color: var(--text-inverse);
}

.hero {
  padding: var(--space-4) 0;
}
.alex {
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
}
.avatar {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  background: var(--accent-soft);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}
.speech {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border-bottom-left-radius: var(--radius-sm);
  flex: 1;
}
.speech h1 {
  margin: 0 0 var(--space-1);
  font-size: 22px;
  color: var(--accent);
}
.tagline {
  margin: 0;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.5;
}

.prompt-box {
  position: relative;
  background: var(--bg-elevated);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  transition: border-color var(--duration) var(--ease),
    box-shadow var(--duration) var(--ease);
}
.prompt-box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
textarea {
  width: 100%;
  min-height: 56px;
  max-height: 180px;
  padding: var(--space-4) var(--space-4);
  font-size: 16px;
  line-height: 1.5;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--text-1);
  font-family: inherit;
}
.start-btn {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--accent);
  color: var(--text-inverse);
  font-weight: 500;
  font-size: 15px;
  border-bottom-left-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-lg);
  transition: background var(--duration) var(--ease);
}
.start-btn:active {
  background: var(--accent-hover);
}

.topics-hint {
  margin: 0 0 var(--space-2);
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
}
.topics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}
.topic-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--text-1);
  transition: transform var(--duration) var(--ease),
    background var(--duration) var(--ease);
}
.topic-card:active {
  transform: scale(0.96);
  background: var(--accent-soft);
}
.topic-card .emoji {
  font-size: 24px;
}
.topic-card .label {
  font-size: 12px;
  color: var(--text-2);
}

.secondary {
  margin-top: auto;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}
.sec-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3);
  border-radius: var(--radius);
  color: var(--text-2);
  font-size: 11px;
  transition: background var(--duration) var(--ease);
}
.sec-item:active {
  background: var(--bg-elevated);
  color: var(--accent);
}
.sec-item .ico {
  font-size: 22px;
}

@media (min-width: 768px) {
  .home {
    max-width: 680px;
    padding-top: var(--space-6);
  }
  .speech h1 {
    font-size: 26px;
  }
  .topics-grid {
    grid-template-columns: repeat(6, 1fr);
  }
}
</style>
