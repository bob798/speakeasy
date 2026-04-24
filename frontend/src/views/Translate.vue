<script setup>
/**
 * Translate · 次战场 (Phase 4 壳化)
 * 迁移自 static/translate.html · 双向翻译 + 生词本
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetch, authFetchJson } = useAuthFetch()

const direction = ref('zh2en') // zh2en | en2zh
const source = ref('')
const translated = ref('')
const translating = ref(false)
const error = ref('')
const vocab = ref([])
const vocabLoading = ref(false)

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
    translated.value = data.translated_text || data.translation || data.translated || ''
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
      target_text: translated.value,
      direction: direction.value,
    })
    await loadVocab()
  } catch (err) {
    error.value = err.message
  }
}

async function loadVocab() {
  vocabLoading.value = true
  try {
    const resp = await authFetch(`${API.TRANSLATE}/vocabulary?limit=100`)
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
  } catch (err) {
    error.value = err.message
  }
}

function swapDirection() {
  direction.value = direction.value === 'zh2en' ? 'en2zh' : 'zh2en'
  source.value = translated.value
  translated.value = ''
}

onMounted(loadVocab)
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
          <button
            class="save"
            v-if="translated"
            @click="onSave"
            aria-label="加入生词本"
          >
            ⭐ 收藏
          </button>
        </div>
      </section>

      <button class="primary" :disabled="!canSubmit" @click="onTranslate">
        {{ translating ? '...' : '翻译' }}
      </button>
      <p v-if="error" class="err">{{ error }}</p>

      <section class="vocab">
        <h3>生词本 ({{ vocab.length }})</h3>
        <ul v-if="vocab.length">
          <li v-for="v in vocab" :key="v.id" class="vocab-item">
            <div class="vocab-text">
              <div>{{ v.source_text }}</div>
              <div class="target">{{ v.target_text }}</div>
            </div>
            <button class="del" @click="onDeleteVocab(v.id)" aria-label="删除">×</button>
          </li>
        </ul>
        <p v-else-if="vocabLoading" class="empty">加载中...</p>
        <p v-else class="empty">还没收藏词条</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.translate-page {
  display: flex;
  flex-direction: column;
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
  padding: var(--space-1) var(--space-3);
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.primary {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-weight: 500;
}
.primary:disabled {
  opacity: 0.5;
}
.err {
  color: #c6463a;
  font-size: 13px;
  margin-top: var(--space-2);
}
.vocab {
  margin-top: var(--space-6);
}
.vocab h3 {
  margin: 0 0 var(--space-3);
  font-size: 14px;
  color: var(--text-2);
}
.vocab ul {
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
}
.vocab-text {
  flex: 1;
  font-size: 14px;
}
.target {
  color: var(--text-2);
  font-size: 13px;
  margin-top: 2px;
}
.del {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 18px;
  color: var(--text-3);
}
.del:active {
  background: var(--bg);
  color: #c6463a;
}
.empty {
  color: var(--text-3);
  font-size: 13px;
}
@media (max-width: 768px) {
  .pair {
    grid-template-columns: 1fr;
  }
}
</style>
