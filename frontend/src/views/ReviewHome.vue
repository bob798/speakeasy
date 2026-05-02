<script setup>
/**
 * Review Dashboard · V0.10
 *
 * 「今日待复习」统一入口：
 *   - BBC 文章 (GET /bbc-eaw/due)
 *   - 生词条目 (GET /vocab?due=true)
 *
 * 文章 → /bbc-review/:slug
 * 生词 → 内联评分（FSRS 推进）
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const router = useRouter()
const { authFetch, authFetchJson } = useAuthFetch()

const articles = ref([])
const vocab = ref([])
const loading = ref(true)
const error = ref('')
const toast = ref('')

const totalDue = computed(() => articles.value.length + vocab.value.length)

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [a, v] = await Promise.all([
      authFetch(`${API.BASE}/bbc-eaw/due`).then((r) => (r.ok ? r.json() : { items: [] })),
      authFetch(`${API.VOCAB}?due=true&limit=200`).then((r) => (r.ok ? r.json() : { items: [] })),
    ])
    articles.value = a.items || []
    vocab.value = v.items || []
  } catch (err) {
    error.value = getErrorMessage(err, '加载失败')
  } finally {
    loading.value = false
  }
}

function showToast(text, ms = 1200) {
  toast.value = text
  setTimeout(() => (toast.value = ''), ms)
}

async function rateVocab(id, rating) {
  try {
    await authFetchJson(`${API.VOCAB}/${id}/rate`, { rating })
    vocab.value = vocab.value.filter((v) => v.id !== id)
    showToast(`已记录 · ${rating}`)
  } catch (err) {
    showToast(getErrorMessage(err, '评分失败'))
  }
}

function reviewArticle(slug) {
  router.push({ name: 'bbc-review', params: { slug } })
}

const TYPE_LABEL = { word: '词', phrase: '短语', sentence: '句' }

onMounted(loadAll)
</script>

<template>
  <div class="rev-home">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">今日复习</div>
      <span />
    </header>

    <main class="body">
      <div v-if="loading" class="state">加载中…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>
      <div v-else-if="totalDue === 0" class="state empty">
        <div class="big">✨</div>
        <p>今日无待复习项</p>
        <p class="hint">去解读页加 ⭐ 收藏新词，或开始一篇 BBC 文章</p>
      </div>

      <template v-else>
        <section v-if="articles.length" class="block">
          <h3>📚 BBC 文章 · {{ articles.length }}</h3>
          <ul class="article-list">
            <li v-for="a in articles" :key="a.id" class="article-item" @click="reviewArticle(a.slug)">
              <div class="ai-main">
                <div class="ai-title">{{ a.title || a.slug }}</div>
                <div v-if="a.topic" class="ai-topic">{{ a.topic }}</div>
              </div>
              <div class="ai-meta">
                <span class="rev-cnt">复习 {{ a.review_count }}×</span>
                <span class="chev">›</span>
              </div>
            </li>
          </ul>
        </section>

        <section v-if="vocab.length" class="block">
          <h3>📒 生词条目 · {{ vocab.length }}</h3>
          <ul class="vocab-list">
            <li v-for="v in vocab" :key="v.id" class="vocab-item">
              <div class="vi-head">
                <span class="vi-type">{{ TYPE_LABEL[v.item_type] || v.item_type }}</span>
                <span class="vi-text">{{ v.source_text }}</span>
              </div>
              <div v-if="v.translated_text" class="vi-trans">{{ v.translated_text }}</div>
              <div v-if="v.context" class="vi-ctx">📍 {{ v.context }}</div>
              <div class="rate-row">
                <button class="rate again" @click="rateVocab(v.id, 'again')">Again</button>
                <button class="rate hard"  @click="rateVocab(v.id, 'hard')">Hard</button>
                <button class="rate good"  @click="rateVocab(v.id, 'good')">Good</button>
                <button class="rate easy"  @click="rateVocab(v.id, 'easy')">Easy</button>
              </div>
            </li>
          </ul>
        </section>
      </template>
    </main>

    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.rev-home {
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
.back { color: var(--text-2); }
.title { font-weight: 600; color: var(--accent); }
.body {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-4);
}
.state {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
}
.state.error { color: #b0403a; }
.state.empty .big { font-size: 48px; margin-bottom: var(--space-3); }
.state.empty .hint { font-size: 12px; margin-top: var(--space-2); }

.block {
  margin-bottom: var(--space-5);
}
.block h3 {
  margin: 0 0 var(--space-3);
  font-size: 14px;
  color: var(--accent);
}
.article-list,
.vocab-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.article-item {
  display: flex;
  align-items: center;
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  gap: var(--space-3);
}
.article-item:active { background: var(--accent-soft); }
.ai-main { flex: 1; min-width: 0; }
.ai-title {
  font-weight: 500;
  color: var(--text-1);
  word-break: break-word;
}
.ai-topic {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
}
.ai-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-3);
}
.chev { font-size: 18px; }

.vocab-item {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.vi-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.vi-type {
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  border-radius: 999px;
  flex-shrink: 0;
}
.vi-text {
  font-size: 14px;
  color: var(--text-1);
  flex: 1;
  word-break: break-word;
}
.vi-trans {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-2);
  padding-left: 38px;
}
.vi-ctx {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
  font-style: italic;
  padding-left: 38px;
}
.rate-row {
  margin-top: var(--space-3);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.rate {
  flex: 1;
  min-width: 60px;
  padding: 6px 10px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.rate.again { background: rgba(198, 70, 58, 0.12); color: #c6463a; }
.rate.hard  { background: rgba(176, 121, 26, 0.12); color: #b0791a; }
.rate.good  { background: var(--accent-soft); color: var(--accent); }
.rate.easy  { background: rgba(61, 107, 79, 0.18); color: var(--accent); }

.toast {
  position: fixed;
  bottom: calc(var(--safe-bottom) + var(--space-5));
  left: 50%;
  transform: translateX(-50%);
  background: var(--text-1);
  color: var(--text-inverse);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  font-size: 13px;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.toast-enter-from,
.toast-leave-to { opacity: 0; }
</style>
