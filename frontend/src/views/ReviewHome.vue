<script setup>
/**
 * Review Dashboard · V0.10
 *
 * 「今日待复习」统一入口：
 *   - BBC 文章 (GET /articles/due)
 *   - 生词条目 (GET /vocab?due=true)
 *
 * 文章 → /bbc-review/:slug
 * 生词 → 内联评分（FSRS 推进）
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { useVoiceCommand } from '@/composables/useVoiceCommand'
import { API } from '@/config'

const router = useRouter()
const { authFetch, authFetchJson } = useAuthFetch()

const articles = ref([])
const vocab = ref([])
const polishCards = ref([])
const loading = ref(true)
const error = ref('')
const toast = ref('')

const totalDue = computed(
  () => articles.value.length + vocab.value.length + polishCards.value.length
)
const focusVocab = computed(() => vocab.value[0] || null)

const POLISH_CATEGORY_LABEL = {
  grammar: '语法',
  word_choice: '用词',
  style: '风格',
  structure: '结构',
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [a, v, p] = await Promise.all([
      authFetch(`${API.BASE}/articles/due`).then((r) => (r.ok ? r.json() : { items: [] })),
      authFetch(`${API.VOCAB}?due=true&limit=200`).then((r) => (r.ok ? r.json() : { items: [] })),
      authFetch(`${API.POLISH}/due`).then((r) => (r.ok ? r.json() : { items: [] })),
    ])
    articles.value = a.items || []
    vocab.value = v.items || []
    polishCards.value = p.items || []
  } catch (err) {
    error.value = getErrorMessage(err, '加载失败')
  } finally {
    loading.value = false
  }
}

async function ratePolish(id, rating) {
  try {
    await authFetchJson(`${API.POLISH}/cards/${id}/rate`, { rating })
    polishCards.value = polishCards.value.filter((c) => c.id !== id)
    showToast(`已记录 · ${rating}`)
  } catch (err) {
    showToast(getErrorMessage(err, '评分失败'))
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

// ── 语音控制 demo（V0.10 P8）────────────────────────────────
// 命令直接打到「焦点条目」（vocab 列表第一项）
// 评完后第一项被移除，下一项自动成为焦点
function rateFocus(rating) {
  if (!focusVocab.value) {
    showToast('没有待复习的生词了')
    return
  }
  rateVocab(focusVocab.value.id, rating)
}

function reviewFirstArticle() {
  if (!articles.value.length) {
    showToast('没有待复习的文章')
    return
  }
  reviewArticle(articles.value[0].slug)
}

const voice = useVoiceCommand({
  commands: {
    again: () => rateFocus('again'),
    hard:  () => rateFocus('hard'),
    good:  () => rateFocus('good'),
    easy:  () => rateFocus('easy'),
    skip:  () => rateFocus('good'),    // 跳过 = good（FSRS 略推）
    review: () => reviewFirstArticle(),
    back:  () => router.push('/'),
  },
  aliases: {
    // 中文 again
    '再来':   'again',
    '不会':   'again',
    '错了':   'again',
    '重来':   'again',
    // hard
    '难':     'hard',
    '有点难': 'hard',
    '困难':   'hard',
    // good
    '好的':   'good',
    '可以':   'good',
    '会了':   'good',
    '记得':   'good',
    '对':     'good',
    // easy
    '简单':   'easy',
    '太容易': 'easy',
    '熟':     'easy',
    // skip
    '跳过':   'skip',
    '下一个': 'skip',
    '下一':   'skip',
    // review
    '复习':   'review',
    '开始复习': 'review',
    // back
    '返回':   'back',
    '退出':   'back',
    '回去':   'back',
  },
  onMatched: (cmd, text) => {
    showToast(`听到「${text}」→ ${cmd}`, 1500)
  },
  onUnmatched: (text) => {
    showToast(`没听懂「${text}」`, 1500)
  },
  onError: (err) => {
    if (err.type === 'PERMISSION_DENIED') {
      showToast('请允许麦克风权限')
    } else if (err.type === 'UNSUPPORTED') {
      showToast(err.message || '当前环境不支持语音')
    } else {
      showToast(`语音错误：${err.type}`)
    }
  },
})

function toggleVoice() {
  if (voice.active.value) voice.stop()
  else voice.start()
}

onBeforeUnmount(() => {
  voice.stop()
})

onMounted(loadAll)
</script>

<template>
  <div class="rev-home">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">今日复习</div>
      <button
        class="voice-btn"
        :class="{ on: voice.active.value, listening: voice.listening.value }"
        @click="toggleVoice"
        :title="voice.active.value ? '语音控制开启 · 再点关闭' : '语音控制 · 用「Again/Hard/Good/Easy/跳过/复习/返回」操控'"
      >
        🎤
      </button>
    </header>

    <!-- 语音状态条 -->
    <div v-if="voice.active.value" class="voice-banner" @click="toggleVoice">
      <span class="vb-dot" :class="{ active: voice.listening.value }"></span>
      <span class="vb-text">
        <template v-if="voice.listening.value">听中…</template>
        <template v-else-if="voice.lastHeard.value">
          上次：{{ voice.lastHeard.value }}
          <span v-if="voice.lastCommand.value" class="vb-cmd">→ {{ voice.lastCommand.value }}</span>
        </template>
        <template v-else>语音模式开启</template>
      </span>
      <span class="vb-stop">点击关闭</span>
    </div>

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

        <section v-if="polishCards.length" class="block">
          <h3>✍️ 写作卡片 · {{ polishCards.length }}</h3>
          <ul class="polish-list">
            <li v-for="c in polishCards" :key="c.id" class="polish-item">
              <div class="pi-head">
                <span v-if="c.category" class="pi-cat">{{ POLISH_CATEGORY_LABEL[c.category] || c.category }}</span>
                <span class="pi-rev-cnt">复习 {{ c.review_count }}×</span>
              </div>
              <div class="pi-diff">
                <span class="pi-from">{{ c.original }}</span>
                <span class="pi-arrow">→</span>
                <span class="pi-to">{{ c.polished }}</span>
              </div>
              <p v-if="c.explanation" class="pi-expl">{{ c.explanation }}</p>
              <div class="rate-row">
                <button class="rate again" @click="ratePolish(c.id, 'again')">Again</button>
                <button class="rate hard"  @click="ratePolish(c.id, 'hard')">Hard</button>
                <button class="rate good"  @click="ratePolish(c.id, 'good')">Good</button>
                <button class="rate easy"  @click="ratePolish(c.id, 'easy')">Easy</button>
              </div>
            </li>
          </ul>
        </section>

        <section v-if="vocab.length" class="block">
          <h3>📒 生词条目 · {{ vocab.length }}</h3>
          <ul class="vocab-list">
            <li
              v-for="(v, idx) in vocab"
              :key="v.id"
              class="vocab-item"
              :class="{ focus: voice.active.value && idx === 0 }"
            >
              <div class="vi-head">
                <span class="vi-type">{{ TYPE_LABEL[v.item_type] || v.item_type }}</span>
                <span v-if="voice.active.value && idx === 0" class="vi-focus-tag">语音焦点</span>
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
.voice-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text-3);
  flex-shrink: 0;
  transition: all var(--duration) var(--ease);
}
.voice-btn:active { transform: scale(0.92); }
.voice-btn.on {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.voice-btn.listening {
  animation: voice-pulse 1.4s ease-in-out infinite;
}
@keyframes voice-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-soft); }
  50% { box-shadow: 0 0 0 8px transparent; }
}

.voice-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-4);
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  user-select: none;
}
.voice-banner:active { opacity: 0.7; }
.vb-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-3);
  flex-shrink: 0;
}
.vb-dot.active {
  background: var(--accent);
  animation: vb-blink 1s ease-in-out infinite;
}
@keyframes vb-blink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.4); }
}
.vb-text { flex: 1; word-break: break-word; }
.vb-cmd {
  margin-left: var(--space-2);
  padding: 2px 8px;
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}
.vb-stop {
  font-size: 11px;
  color: var(--text-3);
  padding: 2px 8px;
  background: var(--bg-elevated);
  border-radius: 999px;
  flex-shrink: 0;
}
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

.polish-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.polish-item {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.pi-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}
.pi-cat {
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  border-radius: 999px;
}
.pi-rev-cnt {
  font-size: 11px;
  color: var(--text-3);
  margin-left: auto;
}
.pi-diff {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  line-height: 1.4;
  margin-bottom: 4px;
}
.pi-from {
  text-decoration: line-through;
  color: #c6463a;
  background: rgba(198, 70, 58, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
}
.pi-to {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.pi-arrow { color: var(--text-3); }
.pi-expl {
  margin: 4px 0 8px;
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.5;
}

.vocab-item {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color var(--duration) var(--ease), box-shadow var(--duration) var(--ease);
}
.vocab-item.focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}
.vi-focus-tag {
  padding: 2px 8px;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 10px;
  border-radius: 999px;
  font-weight: 500;
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
