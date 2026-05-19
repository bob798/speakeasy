<script setup>
/**
 * Translate · V0.9.4 重设计
 *
 * 修:
 *   - target_text → translated_text（字段名对齐后端 VocabularyCreate）
 *   - 移除内嵌生词本面板，生词本功能移至 /vocabulary 独立页
 */
import { ref, computed } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetchJson } = useAuthFetch()

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
    error.value = getErrorMessage(err, '翻译失败')
  } finally {
    translating.value = false
  }
}

async function onSave() {
  if (!translated.value.trim()) return
  try {
    await authFetchJson(`${API.TRANSLATE}/vocabulary`, {
      source_text: source.value,
      translated_text: translated.value,
      direction: direction.value,
    })
    _toast('⭐ 已加入生词本', 'success')
  } catch (err) {
    const msg = getErrorMessage(err)
    error.value = msg
    if (msg) _toast(msg, 'error')
  }
}

function swapDirection() {
  direction.value = direction.value === 'zh2en' ? 'en2zh' : 'zh2en'
  source.value = translated.value
  translated.value = ''
}

// ═══ Toast ═══
const toast = ref({ show: false, text: '', type: 'info' })
function _toast(text, type = 'info', duration = 1800) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}
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

      <p class="vocab-hint">
        收藏的译文可在
        <RouterLink to="/vocabulary" class="vocab-link">生词本</RouterLink>
        中查看与复习
      </p>
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

.vocab-hint {
  margin-top: var(--space-4);
  font-size: 13px;
  color: var(--text-3);
  text-align: center;
}
.vocab-link {
  color: var(--accent);
  text-decoration: underline;
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
}
</style>
