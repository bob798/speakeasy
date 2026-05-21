<script setup>
/**
 * Translate · V0.11 DeepL 风格重设计 — PR1
 *
 * PR1 覆盖：
 *   - 三栏布局（左输入 / 右译文 / 右侧 sidebar）
 *   - debounce 800ms + canonicalText + LRU cache + requestId stale 防御 + AbortController
 *   - swap 改为纯方向切换，不动文本
 *   - 方向自动检测（CJK 比例 ≥ 30% → zh2en）
 *   - Cmd/Ctrl+Enter 手动触发翻译
 *
 * PR2 (TODO): 译文单词分词 + hover/click 词卡
 * PR3 (TODO): sidebar 生词本接通 FSRS + 收藏闭环
 * PR4 (TODO): 移动端 bottom-sheet
 */

import { ref, computed, watch, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

import TopBar from '@/components/translate/TopBar.vue'
import TranslateInput from '@/components/translate/TranslateInput.vue'
import TranslateResult from '@/components/translate/TranslateResult.vue'
import TranslateSidebar from '@/components/translate/TranslateSidebar.vue'

const authStore = useAuthStore()
const { authFetchJson } = useAuthFetch()

// ═══ Layout state ═══
const sidebarOpen = ref(true)
const sheetOpen = ref(false)
const isMobile = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 1024
  if (isMobile.value) sidebarOpen.value = false
}
if (typeof window !== 'undefined') {
  checkMobile()
  window.addEventListener('resize', checkMobile)
}

// ═══ Translation state ═══
const direction = ref('zh2en')
const source = ref('')
const translated = ref('')
const translating = ref(false)
const error = ref('')
const savedToVocab = ref(false)
/** stale=true when direction was swapped but source/translated not retranslated */
const stale = ref(false)

const MAX_LEN = 1000
const canSubmit = computed(
  () => source.value.trim() && source.value.length <= MAX_LEN && !translating.value
)

// ═══ LRU cache (session-level, 100 entries) ═══
const cache = new Map()
const CACHE_MAX = 100

// ═══ Debounce + concurrency control ═══
let requestId = 0
let abortCtrl = null
let debounceTimer = null
let lastCanonical = ''

/**
 * Detect language direction based on CJK character ratio.
 * >= 30% CJK → zh2en (source is Chinese), else en2zh
 * @param {string} text
 * @returns {'zh2en' | 'en2zh'}
 */
function detectDirection(text) {
  if (!text) return direction.value
  const cjkCount = (text.match(/[\u4e00-\u9fff]/g) || []).length
  return cjkCount / text.length >= 0.3 ? 'zh2en' : 'en2zh'
}

// Track last manual swap time to suppress auto-detect for 5 seconds
let lastManualSwapAt = 0

/**
 * Core translate function with requestId stale defense.
 * @param {string} canonicalText
 * @param {string} dir
 */
function doTranslate(canonicalText, dir) {
  const myId = ++requestId
  abortCtrl?.abort()
  abortCtrl = new AbortController()
  const cacheKey = JSON.stringify([canonicalText, dir])

  // Cache hit
  if (cache.has(cacheKey)) {
    if (myId === requestId) {
      translated.value = cache.get(cacheKey)
      savedToVocab.value = false
      stale.value = false
      error.value = ''
    }
    return
  }

  translating.value = true
  error.value = ''

  authFetchJson(
    `${API.TRANSLATE}/text`,
    { text: canonicalText, direction: dir },
    { signal: abortCtrl.signal },
  )
    .then((data) => {
      if (myId !== requestId) return
      const result = data.translated_text || ''
      cache.set(cacheKey, result)
      if (cache.size > CACHE_MAX) {
        cache.delete(cache.keys().next().value)
      }
      translated.value = result
      savedToVocab.value = !!data.saved_to_vocab
      stale.value = false
    })
    .catch((err) => {
      if (err.name === 'AbortError' || myId !== requestId) return
      error.value = getErrorMessage(err, '翻译失败')
    })
    .finally(() => {
      if (myId === requestId) translating.value = false
    })
}

// ═══ Watch source for debounce auto-translate ═══
watch(source, (val) => {
  clearTimeout(debounceTimer)
  const canonical = val.trim()

  if (!canonical) {
    translated.value = ''
    savedToVocab.value = false
    stale.value = false
    error.value = ''
    lastCanonical = ''
    return
  }

  if (canonical.length > MAX_LEN) return

  // Auto-detect direction if user hasn't manually swapped in last 5s
  if (Date.now() - lastManualSwapAt > 5000) {
    const detected = detectDirection(canonical)
    if (detected !== direction.value) {
      direction.value = detected
    }
  }

  // Skip if canonical text unchanged (only whitespace changed)
  if (canonical === lastCanonical) return

  debounceTimer = setTimeout(() => {
    lastCanonical = canonical
    doTranslate(canonical, direction.value)
  }, 800)
})

// ═══ Watch direction change: retranslate if there's content ═══
watch(direction, () => {
  const canonical = source.value.trim()
  if (canonical && canonical.length <= MAX_LEN) {
    lastCanonical = canonical
    doTranslate(canonical, direction.value)
  }
})

// ═══ Manual translate (button + Cmd/Ctrl+Enter) ═══
function onTranslate() {
  if (!canSubmit.value) return
  const canonical = source.value.trim()
  clearTimeout(debounceTimer)
  lastCanonical = canonical
  doTranslate(canonical, direction.value)
}

// ═══ Swap direction (fix: only switch direction, do NOT move text) ═══
function onSwap() {
  lastManualSwapAt = Date.now()
  direction.value = direction.value === 'zh2en' ? 'en2zh' : 'zh2en'
  // Mark as stale — user sees translated text is now for the old direction
  if (translated.value) {
    stale.value = true
  }
}

// ═══ Keyboard shortcut: Cmd/Ctrl+Enter ═══
function onKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    onTranslate()
  }
}

// ═══ Toast ═══
const toast = ref({ show: false, text: '', type: 'info' })
function _toast(text, type = 'info', duration = 1800) {
  toast.value = { show: true, text, type }
  setTimeout(() => (toast.value.show = false), duration)
}

// ═══ Cleanup ═══
onUnmounted(() => {
  clearTimeout(debounceTimer)
  abortCtrl?.abort()
  if (typeof window !== 'undefined') window.removeEventListener('resize', checkMobile)
})
</script>

<template>
  <div class="translate-page" @keydown="onKeydown">
    <TopBar
      :direction="direction"
      :sidebar-open="sidebarOpen"
      @swap="onSwap"
      @toggle-sidebar="sidebarOpen = !sidebarOpen"
    />

    <main class="translate-body">
      <div class="translate-layout" :class="{ 'no-sidebar': !sidebarOpen }">
        <!-- Left: input -->
        <TranslateInput
          v-model="source"
          :direction="direction"
          :max-len="MAX_LEN"
        />

        <!-- Center-right: result -->
        <div class="result-col">
          <TranslateResult
            :text="translated"
            :loading="translating"
            :saved-to-vocab="savedToVocab"
            :is-authenticated="authStore.isAuthenticated"
            :stale="stale"
            :error="error"
            :direction="direction"
          />

          <!-- Translate button -->
          <button
            class="translate-btn"
            :disabled="!canSubmit"
            @click="onTranslate"
            title="翻译 (Cmd/Ctrl+Enter)"
          >
            {{ translating ? '翻译中…' : '翻译' }}
          </button>

          <!-- Vocab hint -->
          <p class="vocab-hint">
            收藏的译文可在
            <RouterLink to="/vocabulary" class="vocab-link">生词本</RouterLink>
            中查看与复习
          </p>
        </div>

        <!-- Right: sidebar (desktop) -->
        <TranslateSidebar v-if="!isMobile" :open="sidebarOpen" />
      </div>
    </main>

    <!-- Mobile FAB + bottom sheet -->
    <button v-if="isMobile" class="fab" @click="sheetOpen = true" aria-label="打开生词本">
      📖
    </button>

    <Teleport to="body">
      <Transition name="sheet">
        <div v-if="sheetOpen" class="sheet-overlay" @click.self="sheetOpen = false">
          <div class="sheet-container" role="dialog" aria-label="生词本">
            <div class="sheet-grip" />
            <button class="sheet-close" @click="sheetOpen = false" aria-label="关闭">✕</button>
            <TranslateSidebar :open="true" />
          </div>
        </div>
      </Transition>
    </Teleport>

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

.translate-body {
  flex: 1;
  overflow: auto;
}

/* Three-column grid layout */
.translate-layout {
  display: grid;
  grid-template-columns: 1fr 1fr 320px;
  gap: var(--space-4);
  padding: var(--space-4);
  max-width: 1400px;
  margin: 0 auto;
  /* Allow full height use */
  min-height: calc(100vh - 64px);
  align-items: start;
}

.translate-layout.no-sidebar {
  grid-template-columns: 1fr 1fr;
}

.result-col {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.translate-btn {
  width: 100%;
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-weight: 500;
  font-size: 15px;
  transition: background var(--duration) var(--ease);
}

.translate-btn:hover:not(:disabled) {
  background: var(--accent-hover, color-mix(in srgb, var(--accent) 85%, black));
}

.translate-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.translate-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.vocab-hint {
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}

.vocab-link {
  color: var(--accent);
  text-decoration: underline;
}

/* Tablet: two-column (sidebar hidden) */
@media (max-width: 1024px) {
  .translate-layout,
  .translate-layout.no-sidebar {
    grid-template-columns: 1fr 1fr;
  }

  /* Hide sidebar via grid — TranslateSidebar won't show at this breakpoint anyway */
}

/* Mobile: single column */
@media (max-width: 768px) {
  .translate-layout,
  .translate-layout.no-sidebar {
    grid-template-columns: 1fr;
    padding: var(--space-3);
    gap: var(--space-3);
  }
}

/* Toast */
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
  white-space: nowrap;
}

.toast.error {
  background: #c6463a;
}

.toast.success {
  background: var(--accent);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}

/* Mobile FAB */
.fab {
  position: fixed;
  bottom: calc(var(--safe-bottom) + var(--space-4));
  right: var(--space-4);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 40;
}
.fab:active { transform: scale(0.92); }

/* Bottom sheet overlay */
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: var(--z-modal, 200);
  display: flex;
  align-items: flex-end;
}
.sheet-container {
  width: 100%;
  max-height: min(60vh, calc(100vh - var(--safe-top, 0px) - 48px));
  background: var(--bg);
  border-radius: var(--radius) var(--radius) 0 0;
  overflow-y: auto;
  position: relative;
  padding-bottom: var(--safe-bottom, 0px);
}
.sheet-grip {
  width: 36px;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin: 8px auto;
}
.sheet-close {
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 18px;
  color: var(--text-3);
  z-index: 1;
}
.sheet-close:hover { color: var(--text-1); }

/* Sheet transitions */
.sheet-enter-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.sheet-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.sheet-enter-from { opacity: 0; }
.sheet-enter-from .sheet-container { transform: translateY(100%); }
.sheet-leave-to { opacity: 0; }
.sheet-leave-to .sheet-container { transform: translateY(100%); }
</style>
