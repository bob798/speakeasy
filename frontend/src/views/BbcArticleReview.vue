<script setup>
/**
 * BBC 文章复习 · V0.10
 *
 * 流程：
 *   1. start (POST /bbc-eaw/:slug/start) 确保卡存在
 *   2. review (GET  /bbc-eaw/:slug/review) 取题
 *   3. 用户做完所有题 → 评分弹窗（Again/Hard/Good/Easy）
 *   4. POST /bbc-eaw/:slug/rate · wrong_segments 联动入生词本
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const route = useRoute()
const router = useRouter()
const { authFetch, authFetchJson } = useAuthFetch()

const slug = computed(() => route.params.slug)

const loading = ref(true)
const error = ref('')
const article = ref(null)
const card = ref(null)
const questions = ref([])
const currentIdx = ref(0)
const answers = ref([])              // 用户每题作答
const wrongSegments = ref(new Set()) // segIdx 集合
const showRatePanel = ref(false)
const showAnswer = ref(false)
const submitting = ref(false)
const finalResult = ref(null)
const toast = ref('')

const currentQ = computed(() => questions.value[currentIdx.value])
const totalQ = computed(() => questions.value.length)
const isLast = computed(() => currentIdx.value >= totalQ.value - 1)

function showToast(text, ms = 1800) {
  toast.value = text
  setTimeout(() => (toast.value = ''), ms)
}

async function bootstrap() {
  loading.value = true
  error.value = ''
  try {
    const articleResp = await authFetch(`${API.BASE}/bbc-eaw/episodes/${slug.value}`)
    if (!articleResp.ok) throw new Error('加载文章失败')
    article.value = await articleResp.json()

    card.value = await authFetchJson(
      `${API.BASE}/bbc-eaw/${slug.value}/start`,
      {},
      { method: 'POST' },
    )

    const reviewResp = await authFetch(`${API.BASE}/bbc-eaw/${slug.value}/review`)
    if (!reviewResp.ok) {
      const detail = (await reviewResp.json().catch(() => ({}))).detail
      throw new Error(detail || '题目加载失败')
    }
    const data = await reviewResp.json()
    questions.value = data.questions || []
    answers.value = questions.value.map(() => '')
  } catch (err) {
    error.value = getErrorMessage(err, '加载失败')
  } finally {
    loading.value = false
  }
}

function markWrong() {
  // 把当前题对应的 transcript 句标记为错
  const q = currentQ.value
  if (q && typeof q.segment_idx === 'number') {
    wrongSegments.value.add(q.segment_idx)
  }
  showToast('已标记为错，进入下一题')
  next()
}

function markRight() {
  // 把这题从 wrong 集合里去掉（防止用户切回又切走）
  const q = currentQ.value
  if (q && typeof q.segment_idx === 'number') {
    wrongSegments.value.delete(q.segment_idx)
  }
  next()
}

function next() {
  showAnswer.value = false
  if (isLast.value) {
    showRatePanel.value = true
  } else {
    currentIdx.value += 1
  }
}

function prev() {
  if (currentIdx.value > 0) {
    showAnswer.value = false
    currentIdx.value -= 1
  }
}

function buildWrongPayload() {
  if (!article.value?.segments) return []
  const out = []
  for (const idx of wrongSegments.value) {
    const seg = article.value.segments[idx]
    if (!seg) continue
    out.push({
      text: seg.content,
      segment_idx: idx,
      context: article.value.title || '',
    })
  }
  return out
}

async function submitRating(rating) {
  submitting.value = true
  try {
    const result = await authFetchJson(`${API.BASE}/bbc-eaw/${slug.value}/rate`, {
      rating,
      wrong_segments: buildWrongPayload(),
    })
    finalResult.value = result
  } catch (err) {
    showToast(getErrorMessage(err, '提交失败'))
  } finally {
    submitting.value = false
  }
}

function backToList() {
  router.push('/practice')
}

function backToMemory() {
  router.push('/memory')
}

onMounted(bootstrap)
</script>

<template>
  <div class="bbc-review">
    <header class="topbar">
      <button class="back" @click="router.back()">← 返回</button>
      <div class="title">
        {{ article?.title || 'BBC 复习' }}
        <span v-if="totalQ" class="prog">{{ currentIdx + 1 }}/{{ totalQ }}</span>
      </div>
      <span />
    </header>

    <main class="body">
      <div v-if="loading" class="state">加载中…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <!-- 完成态 -->
      <div v-else-if="finalResult" class="done">
        <div class="done-emoji">✨</div>
        <h2>本轮复习完成</h2>
        <p class="done-stats">
          错题 {{ finalResult.wrong_saved }} 句 已自动加入生词本
        </p>
        <p class="done-due">下次复习：{{ (finalResult.due || '').slice(0, 16) || '—' }}</p>
        <div class="done-actions">
          <button class="primary" @click="backToMemory">看生词本</button>
          <button class="secondary" @click="backToList">回到练习页</button>
        </div>
      </div>

      <!-- 评分态 -->
      <div v-else-if="showRatePanel" class="rate-panel">
        <h3>给整篇打分</h3>
        <p class="rate-hint">
          根据你做题的整体表现选一档；标错的 {{ wrongSegments.size }} 句会自动入生词本
        </p>
        <div class="rate-grid">
          <button class="rate again" :disabled="submitting" @click="submitRating('again')">
            <strong>Again</strong><span>没掌握 · 明天再来</span>
          </button>
          <button class="rate hard" :disabled="submitting" @click="submitRating('hard')">
            <strong>Hard</strong><span>有点难 · 几天内</span>
          </button>
          <button class="rate good" :disabled="submitting" @click="submitRating('good')">
            <strong>Good</strong><span>掌握中 · 一周</span>
          </button>
          <button class="rate easy" :disabled="submitting" @click="submitRating('easy')">
            <strong>Easy</strong><span>很熟 · 拉长</span>
          </button>
        </div>
        <button class="link-btn" :disabled="submitting" @click="showRatePanel = false">
          ← 再回去看一题
        </button>
      </div>

      <!-- 答题态 -->
      <div v-else-if="currentQ" class="quiz">
        <div class="qtype">
          <span v-if="currentQ.qtype === 'cloze'">📝 听并补全</span>
          <span v-else-if="currentQ.qtype === 'back_translate'">🔁 回译</span>
          <span v-else>🎙️ 复述提示</span>
        </div>
        <pre class="prompt">{{ currentQ.prompt }}</pre>

        <textarea
          v-model="answers[currentIdx]"
          rows="4"
          placeholder="把答案写在这里…"
          class="answer-input"
        />

        <div class="answer-actions">
          <button class="link-btn" @click="showAnswer = !showAnswer">
            {{ showAnswer ? '隐藏答案' : '查看参考答案' }}
          </button>
        </div>
        <div v-if="showAnswer" class="answer-box">
          <strong>参考：</strong>{{ currentQ.answer || '（开放题，无标准答案）' }}
        </div>

        <div class="nav">
          <button class="secondary" :disabled="currentIdx === 0" @click="prev">← 上一题</button>
          <button class="wrong" @click="markWrong">标错 · 入生词本</button>
          <button class="primary" @click="markRight">
            {{ isLast ? '完成 → 评分' : '会了 · 下一题' }}
          </button>
        </div>
      </div>

      <div v-else class="state">没有题目可用</div>
    </main>

    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.bbc-review {
  min-height: 100dvh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  padding-top: calc(var(--safe-top) + var(--space-3));
  background: var(--bg-overlay);
  border-bottom: 1px solid var(--border);
}
.back {
  color: var(--text-2);
  font-size: 14px;
}
.title {
  font-weight: 600;
  color: var(--accent);
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.prog {
  font-size: 12px;
  color: var(--text-3);
  font-weight: 400;
}
.body {
  flex: 1;
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  padding: var(--space-4);
}
.state {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
}
.state.error {
  color: #b0403a;
}
.qtype {
  font-size: 12px;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 4px 10px;
  border-radius: 999px;
  display: inline-block;
  margin-bottom: var(--space-3);
}
.prompt {
  white-space: pre-wrap;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-4);
  font-size: 16px;
  line-height: 1.7;
  color: var(--text-1);
  font-family: inherit;
}
.answer-input {
  width: 100%;
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}
.answer-input:focus {
  border-color: var(--accent);
  outline: none;
}
.answer-actions {
  margin-top: var(--space-2);
  text-align: right;
}
.link-btn {
  font-size: 12px;
  color: var(--accent);
  background: transparent;
}
.answer-box {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--accent-soft);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-1);
  line-height: 1.5;
}
.nav {
  margin-top: var(--space-4);
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.nav button {
  flex: 1;
  min-width: 100px;
  padding: var(--space-3);
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
}
.primary {
  background: var(--accent);
  color: var(--text-inverse);
}
.secondary {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-1);
}
.wrong {
  background: rgba(198, 70, 58, 0.12);
  color: #c6463a;
}
.rate-panel {
  text-align: center;
}
.rate-panel h3 {
  margin: var(--space-4) 0 var(--space-2);
}
.rate-hint {
  color: var(--text-2);
  font-size: 13px;
  margin-bottom: var(--space-4);
}
.rate-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.rate-grid .rate {
  padding: var(--space-4);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-weight: 500;
  text-align: left;
}
.rate-grid .rate strong {
  font-size: 16px;
}
.rate-grid .rate span {
  font-size: 11px;
  color: var(--text-3);
}
.rate.again { background: rgba(198, 70, 58, 0.12); color: #c6463a; }
.rate.hard  { background: rgba(176, 121, 26, 0.12); color: #b0791a; }
.rate.good  { background: var(--accent-soft); color: var(--accent); }
.rate.easy  { background: rgba(61, 107, 79, 0.18); color: var(--accent); }
.done {
  text-align: center;
  padding: var(--space-6) var(--space-4);
}
.done-emoji {
  font-size: 56px;
  margin-bottom: var(--space-3);
}
.done h2 {
  margin: 0 0 var(--space-2);
}
.done-stats,
.done-due {
  color: var(--text-2);
  font-size: 14px;
  margin: var(--space-1) 0;
}
.done-actions {
  margin-top: var(--space-5);
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}
.done-actions button {
  min-width: 140px;
  padding: var(--space-3);
  border-radius: var(--radius);
  font-weight: 500;
}
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
.toast-leave-to {
  opacity: 0;
}
</style>
