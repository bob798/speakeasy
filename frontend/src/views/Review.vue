<script setup>
/**
 * Review · 次战场 (Phase 4 壳化)
 * 迁移自 static/review.html · 对话复盘 · 按需触发 /chat/summary 生成
 */
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'

const route = useRoute()
const sessionId = ref(route.params.sessionId)
const { authFetch, authFetchJson } = useAuthFetch()

const review = ref(null)
const loading = ref(true)
const error = ref('')
const summarizing = ref(false)
const rated = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const resp = await authFetch(`${API.REVIEW}/${sessionId.value}`)
    if (resp.status === 404) {
      review.value = null
      return
    }
    if (!resp.ok) throw new Error('加载失败')
    review.value = await resp.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function generateSummary() {
  summarizing.value = true
  error.value = ''
  try {
    await authFetchJson(API.CHAT_SUMMARY, { session_id: sessionId.value })
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    summarizing.value = false
  }
}

async function onRate(rating) {
  try {
    await authFetchJson(`${API.REVIEW}/${sessionId.value}/rate`, { rating })
    rated.value = true
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="review-page">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">对话复盘</div>
      <span />
    </header>

    <main class="body">
      <div v-if="loading" class="empty">加载中...</div>
      <div v-else-if="error" class="err">{{ error }}</div>

      <template v-else-if="!review">
        <div class="no-review">
          <p>这个对话还没有复盘</p>
          <button class="primary" :disabled="summarizing" @click="generateSummary">
            {{ summarizing ? '生成中...' : '生成复盘' }}
          </button>
        </div>
      </template>

      <template v-else>
        <section v-if="review.summary" class="block">
          <h3>整体评价</h3>
          <p>{{ review.summary }}</p>
        </section>
        <section v-if="review.highlights?.length" class="block">
          <h3>亮点</h3>
          <ul>
            <li v-for="(h, i) in review.highlights" :key="i">{{ h }}</li>
          </ul>
        </section>
        <section v-if="review.improvements?.length" class="block">
          <h3>改进方向</h3>
          <ul>
            <li v-for="(imp, i) in review.improvements" :key="i">{{ imp }}</li>
          </ul>
        </section>
        <section v-if="review.grammar_errors?.length" class="block">
          <h3>语法点</h3>
          <ul class="errors">
            <li v-for="(e, i) in review.grammar_errors" :key="i">
              <div class="err-text">❌ {{ e.error_text }}</div>
              <div class="fix-text">✅ {{ e.correction }}</div>
              <div v-if="e.explanation" class="expl">{{ e.explanation }}</div>
            </li>
          </ul>
        </section>
        <section v-if="review.suggestion" class="block">
          <h3>Alex 的建议</h3>
          <p>{{ review.suggestion }}</p>
        </section>

        <section class="rate-box">
          <p v-if="!rated">这次复盘对你有用吗？</p>
          <p v-else class="thanks">感谢你的反馈 ❤️</p>
          <div v-if="!rated" class="rate-row">
            <button @click="onRate('up')">👍 有用</button>
            <button @click="onRate('down')">👎 不太行</button>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.review-page {
  min-height: 100dvh;
  background: var(--bg);
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-overlay);
  border-bottom: 1px solid var(--border);
}
.title {
  font-weight: 600;
  color: var(--accent);
}
.back {
  color: var(--text-2);
}
.body {
  padding: var(--space-4);
  max-width: 720px;
  margin: 0 auto;
}
.empty,
.err {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
}
.err {
  color: #c6463a;
}
.no-review {
  text-align: center;
  padding: var(--space-6);
}
.no-review p {
  color: var(--text-2);
  margin-bottom: var(--space-4);
}
.primary {
  padding: var(--space-3) var(--space-5);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-weight: 500;
}
.primary:disabled {
  opacity: 0.6;
}
.block {
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.block h3 {
  margin: 0 0 var(--space-2);
  font-size: 14px;
  color: var(--accent);
}
.block p,
.block li {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-1);
}
ul {
  margin: 0;
  padding-left: var(--space-4);
}
.errors {
  list-style: none;
  padding: 0;
}
.errors li {
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border);
}
.err-text {
  color: #c6463a;
}
.fix-text {
  color: var(--accent);
  margin-top: 2px;
}
.expl {
  color: var(--text-2);
  font-size: 13px;
  margin-top: 2px;
}
.rate-box {
  margin-top: var(--space-5);
  padding: var(--space-4);
  background: var(--accent-soft);
  border-radius: var(--radius);
  text-align: center;
}
.thanks {
  color: var(--accent);
  margin: 0;
}
.rate-row {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  margin-top: var(--space-2);
}
.rate-row button {
  padding: var(--space-2) var(--space-4);
  background: var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 14px;
}
.rate-row button:active {
  background: var(--accent);
  color: var(--text-inverse);
}
</style>
