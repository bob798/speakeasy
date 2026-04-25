<script setup>
/**
 * Translate · V0.9.4 重设计
 *
 * 修:
 *   - target_text → translated_text（字段名对齐后端 VocabularyCreate）
 *
 * 生词本重设计:
 *   Tab 1 列表：朗读 / 复制 / 删除 / 搜索 / 标记掌握（localStorage）
 *   Tab 2 翻牌复习：随机抽未掌握的条目，show 源，tap 翻牌，打分
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { useTTS } from '@/composables/useTTS'
import { API } from '@/config'

const { authFetch, authFetchJson } = useAuthFetch()
const { enqueue: ttsEnqueue } = useTTS()

// ═══ 翻译区 ═══
const direction = ref('zh2en')
const source = ref('')
const translated = ref('')
const translating = ref(false)
const error = ref('')

const MAX_LEN = 1000
const canSubmit = computed(
  () => source.value.trim() && source.value.length <= MAX_LEN && !translating.value
)

async function onTranslate() {
  if (!canSubmit.value) return
  translating.value = true
  error.value = ''
  translated.value = ''
  try {
    const data = await authFetchJson(`${API.TRANSLATE}/text`, {
      text: source.value,
      direction: direction.value,
    })
    translated.value = data.translated_text || ''
  } catch (err) {
    error.value = err.message || '翻译失败'
  } finally {
    translating.value = false
  }
}

async function onSave() {
  if (!translated.value.trim()) return
  try {
    await authFetchJson(`${API.TRANSLATE}/vocabulary`, {
      source_text: source.value,
      translated_text: translated.value,   // ✨ 修：字段名
      direction: direction.value,
    })
    await loadVocab()
    _toast('⭐ 已加入生词本', 'success')
  } catch (err) {
    error.value = err.message
    _toast(err.message, 'error')
  }
}

function swapDirection() {
  direction.value = direction.value === 'zh2en' ? 'en2zh' : 'zh2en'
  source.value = translated.value
  translated.value = ''
}

// ═══ 生词本 ═══
const vocab = ref([])
const vocabLoading = ref(false)
const tab = ref('list')     // list | flashcard
const search = ref('')
const masteredIds = ref(new Set())
const MASTERED_KEY = 'v2:vocab.mastered'

function _loadMastered() {
  try {
    const raw = localStorage.getItem(MASTERED_KEY)
    if (raw) masteredIds.value = new Set(JSON.parse(raw))
  } catch {
    /* ignore */
  }
}
function _saveMastered() {
  try {
    localStorage.setItem(MASTERED_KEY, JSON.stringify([...masteredIds.value]))
  } catch {
    /* ignore */
  }
}
function toggleMastered(id) {
  const s = new Set(masteredIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  masteredIds.value = s
  _saveMastered()
}

const filteredVocab = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return vocab.value
  return vocab.value.filter(
    (v) =>
      (v.source_text || '').toLowerCase().includes(q) ||
      (v.translated_text || '').toLowerCase().includes(q)
  )
})

async function loadVocab() {
  vocabLoading.value = true
  try {
    const resp = await authFetch(`${API.TRANSLATE}/vocabulary?limit=200`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    vocab.value = data.items || []
  } catch {
    /* 静默 */
  } finally {
    vocabLoading.value = false
  }
}

async function onDeleteVocab(id) {
  try {
    const resp = await authFetch(`${API.TRANSLATE}/vocabulary/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('删除失败')
    vocab.value = vocab.value.filter((v) => v.id !== id)
    masteredIds.value.delete(id)
    _saveMastered()
    _toast('已删除', 'info')
  } catch (err) {
    _toast(err.message, 'error')
  }
}

function copyText(text) {
  if (!text) return
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(
      () => _toast('已复制', 'info'),
      () => _toast('复制失败', 'error')
    )
  } else {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      _toast('已复制', 'info')
    } catch {
      _toast('复制失败', 'error')
    }
    document.body.removeChild(ta)
  }
}

// ═══ 翻牌复习 ═══
const flashIdx = ref(0)
const flashRevealed = ref(false)
const flashPool = computed(() =>
  vocab.value.filter((v) => !masteredIds.value.has(v.id))
)
const flashCurrent = computed(() => flashPool.value[flashIdx.value] || null)

function flashReveal() {
  flashRevealed.value = true
  // 朗读英文（两侧的英文）
  const item = flashCurrent.value
  if (!item) return
  const enText = item.direction === 'zh2en' ? item.translated_text : item.source_text
  if (enText) ttsEnqueue(enText, { manual: true })
}

function flashNext() {
  flashRevealed.value = false
  if (flashIdx.value + 1 < flashPool.value.length) {
    flashIdx.value++
  } else {
    flashIdx.value = 0  // 循环
  }
}

function flashMaster() {
  if (!flashCurrent.value) return
  toggleMastered(flashCurrent.value.id)
  _toast('✓ 已掌握，移出复习池', 'success')
  // 当前池已变，无需 ++idx
  if (flashIdx.value >= flashPool.value.length) flashIdx.value = 0
  flashRevealed.value = false
}

// ═══ Toast ═══
const toast = ref({ show: false, text: '', type: 'info' })
function _toast(text, type = 'info', duration = 1800) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

onMounted(() => {
  _loadMastered()
  loadVocab()
})
</script>

<template>
  <div class="translate-page">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">翻译</div>
      <button class="swap" @click="swapDirection" aria-label="切换方向">
        {{ direction === 'zh2en' ? '中→英' : '英→中' }} ⇄
      </button>
    </header>

    <main class="body">
      <!-- 翻译区 -->
      <section class="pair">
        <div class="col">
          <textarea
            v-model="source"
            :placeholder="direction === 'zh2en' ? '输入中文' : 'Enter English'"
            :maxlength="MAX_LEN"
          ></textarea>
          <div class="counter">{{ source.length }} / {{ MAX_LEN }}</div>
        </div>
        <div class="col">
          <div class="result" :class="{ loading: translating }">
            {{ translated || (translating ? '翻译中...' : '译文会显示在这里') }}
          </div>
          <button v-if="translated" class="save" @click="onSave">⭐ 收藏到生词本</button>
        </div>
      </section>

      <button class="primary" :disabled="!canSubmit" @click="onTranslate">
        {{ translating ? '...' : '翻译' }}
      </button>
      <p v-if="error" class="err">{{ error }}</p>

      <!-- 生词本 · 双 Tab -->
      <section class="vocab">
        <header class="vocab-head">
          <h3>生词本 · {{ vocab.length }} 条 · 已掌握 {{ masteredIds.size }}</h3>
          <nav class="tabs">
            <button :class="{ active: tab === 'list' }" @click="tab = 'list'">列表</button>
            <button
              :class="{ active: tab === 'flashcard' }"
              :disabled="flashPool.length === 0"
              @click="tab = 'flashcard'"
            >
              翻牌复习 ({{ flashPool.length }})
            </button>
          </nav>
        </header>

        <!-- ═══ List Tab ═══ -->
        <template v-if="tab === 'list'">
          <input
            v-if="vocab.length > 5"
            v-model="search"
            class="search"
            placeholder="搜索..."
          />
          <ul v-if="filteredVocab.length" class="list">
            <li
              v-for="v in filteredVocab"
              :key="v.id"
              class="vocab-item"
              :class="{ mastered: masteredIds.has(v.id) }"
            >
              <div class="vocab-text">
                <div class="source">{{ v.source_text }}</div>
                <div class="target">{{ v.translated_text }}</div>
              </div>
              <div class="actions">
                <button
                  class="icon-btn"
                  @click="ttsEnqueue(v.direction === 'zh2en' ? v.translated_text : v.source_text, { manual: true })"
                  aria-label="朗读英文"
                  title="朗读英文"
                >
                  🔊
                </button>
                <button
                  class="icon-btn"
                  @click="copyText(v.translated_text)"
                  aria-label="复制译文"
                  title="复制译文"
                >
                  📋
                </button>
                <button
                  class="icon-btn master-btn"
                  :class="{ on: masteredIds.has(v.id) }"
                  @click="toggleMastered(v.id)"
                  aria-label="标记掌握"
                  :title="masteredIds.has(v.id) ? '已掌握 · 再点移回' : '标记掌握'"
                >
                  ✓
                </button>
                <button
                  class="icon-btn del"
                  @click="onDeleteVocab(v.id)"
                  aria-label="删除"
                  title="删除"
                >
                  ×
                </button>
              </div>
            </li>
          </ul>
          <p v-else-if="vocabLoading" class="empty">加载中...</p>
          <p v-else-if="search" class="empty">没有匹配的条目</p>
          <p v-else class="empty">翻译后点 ⭐ 收藏到生词本</p>
        </template>

        <!-- ═══ Flashcard Tab ═══ -->
        <template v-else>
          <div v-if="!flashCurrent" class="empty">全部已掌握 🎉</div>
          <div v-else class="flashcard">
            <div class="card-count">
              {{ flashIdx + 1 }} / {{ flashPool.length }}
            </div>
            <div class="card" :class="{ flipped: flashRevealed }" @click="flashReveal">
              <div class="card-side front">
                <div class="card-label">{{ flashCurrent.direction === 'zh2en' ? '中文' : '英文' }}</div>
                <div class="card-text">{{ flashCurrent.source_text }}</div>
                <div class="card-tap">点我翻牌</div>
              </div>
              <div class="card-side back">
                <div class="card-label">{{ flashCurrent.direction === 'zh2en' ? '英文' : '中文' }}</div>
                <div class="card-text">{{ flashCurrent.translated_text }}</div>
              </div>
            </div>
            <div v-if="flashRevealed" class="card-actions">
              <button class="flash-btn primary" @click="flashMaster">
                ✓ 已掌握
              </button>
              <button class="flash-btn" @click="flashNext">
                下一个 →
              </button>
            </div>
            <p v-if="!flashRevealed" class="card-hint">
              心里说一遍译文，然后点卡片核对
            </p>
          </div>
        </template>
      </section>
    </main>

    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.text }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.translate-page {
  display: flex;
  flex-direction: column;
  min-height: var(--app-vh, 100dvh);
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
}
.title {
  font-weight: 600;
  color: var(--accent);
}
.back,
.swap {
  color: var(--text-2);
  font-size: 14px;
}
.body {
  padding: var(--space-4);
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
  flex: 1;
}
.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.col {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
textarea,
.result {
  width: 100%;
  min-height: 180px;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  font-size: 15px;
  line-height: 1.6;
  outline: none;
}
textarea:focus {
  border-color: var(--accent);
}
textarea {
  resize: vertical;
  font-family: inherit;
}
.result {
  white-space: pre-wrap;
  color: var(--text-1);
}
.result.loading {
  color: var(--text-3);
  font-style: italic;
}
.counter {
  font-size: 11px;
  color: var(--text-3);
  text-align: right;
}
.save {
  align-self: flex-start;
  padding: 6px var(--space-3);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--duration) var(--ease);
}
.save:active {
  background: var(--accent);
  color: var(--text-inverse);
  transform: scale(0.96);
}
.primary {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-weight: 500;
  transition: background var(--duration) var(--ease);
}
.primary:active {
  background: var(--accent-hover);
}
.primary:disabled {
  opacity: 0.5;
}
.err {
  color: #c6463a;
  font-size: 13px;
  margin-top: var(--space-2);
}

/* ═══ 生词本区 ═══ */
.vocab {
  margin-top: var(--space-6);
}
.vocab-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}
.vocab h3 {
  margin: 0;
  font-size: 14px;
  color: var(--text-2);
  font-weight: 500;
}
.tabs {
  display: flex;
  gap: 3px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  padding: 3px;
}
.tabs button {
  padding: 6px var(--space-3);
  font-size: 13px;
  color: var(--text-2);
  border-radius: calc(var(--radius-sm) - 3px);
  transition: background var(--duration) var(--ease);
}
.tabs button.active {
  background: var(--bg-elevated);
  color: var(--accent);
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.tabs button:disabled {
  opacity: 0.4;
}
.search {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  margin-bottom: var(--space-3);
  background: var(--bg-elevated);
  outline: none;
}
.search:focus {
  border-color: var(--accent);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.vocab-item {
  display: flex;
  justify-content: space-between;
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  gap: var(--space-2);
  transition: opacity var(--duration) var(--ease);
}
.vocab-item.mastered {
  opacity: 0.55;
  background: var(--bg);
}
.vocab-text {
  flex: 1;
  min-width: 0;
}
.source {
  font-size: 14px;
  color: var(--text-1);
  font-weight: 500;
  word-break: break-word;
}
.target {
  color: var(--text-2);
  font-size: 13px;
  margin-top: 3px;
  word-break: break-word;
}
.actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  align-items: center;
}
.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  font-size: 14px;
  color: var(--text-3);
  background: transparent;
  transition: background var(--duration) var(--ease);
  touch-action: manipulation;
}
.icon-btn:active {
  background: var(--bg);
}
.icon-btn.master-btn.on {
  background: var(--accent-soft);
  color: var(--accent);
}
.icon-btn.del:active {
  color: #c6463a;
  background: rgba(198, 70, 58, 0.1);
}

/* ═══ 翻牌 ═══ */
.flashcard {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) 0;
}
.card-count {
  font-size: 12px;
  color: var(--text-3);
}
.card {
  width: 100%;
  max-width: 400px;
  min-height: 180px;
  position: relative;
  perspective: 1000px;
  cursor: pointer;
  touch-action: manipulation;
}
.card-side {
  position: absolute;
  inset: 0;
  background: var(--bg-elevated);
  border: 2px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: var(--space-2);
  backface-visibility: hidden;
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.card-side.back {
  transform: rotateY(180deg);
  background: var(--accent-soft);
  border-color: var(--accent);
}
.card.flipped .card-side.front {
  transform: rotateY(-180deg);
}
.card.flipped .card-side.back {
  transform: rotateY(0);
}
.card-label {
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.card-text {
  font-size: 20px;
  text-align: center;
  color: var(--text-1);
  font-weight: 500;
  line-height: 1.5;
}
.card-tap {
  position: absolute;
  bottom: var(--space-3);
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.3px;
}
.card-hint {
  color: var(--text-3);
  font-size: 12px;
  margin: 0;
}
.card-actions {
  display: flex;
  gap: var(--space-2);
  width: 100%;
  max-width: 400px;
}
.flash-btn {
  flex: 1;
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  color: var(--text-1);
  font-weight: 500;
  transition: all var(--duration) var(--ease);
  touch-action: manipulation;
}
.flash-btn:active {
  transform: scale(0.96);
  background: var(--bg);
}
.flash-btn.primary {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.flash-btn.primary:active {
  background: var(--accent-hover);
}

.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
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
  z-index: var(--z-toast);
}
.toast.error { background: #c6463a; }
.toast.success { background: var(--accent); }
.toast-enter-active,
.toast-leave-active { transition: opacity var(--duration) var(--ease); }
.toast-enter-from,
.toast-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .pair { grid-template-columns: 1fr; }
  .vocab-head { flex-direction: column; align-items: flex-start; }
}
</style>
