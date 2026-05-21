<script setup>
/**
 * TranslateResult · 右栏译文区
 * - 译文分词渲染（tokenize）+ hover IPA 浮层 + click WordCard
 * - loading / stale / error 状态
 * - event delegation（单 listener，通过 data-token-idx 路由）
 */
import { ref, computed, watch, nextTick } from 'vue'
import { tokenize } from './tokenize.js'
import WordCard from './WordCard.vue'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'

const props = defineProps({
  text: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  savedToVocab: { type: Boolean, default: false },
  isAuthenticated: { type: Boolean, default: false },
  stale: { type: Boolean, default: false },
  error: { type: String, default: '' },
  direction: { type: String, default: 'zh2en' },
})

const { authFetchJson } = useAuthFetch()

// ═══ Tokenization ═══
const tokens = computed(() => props.text ? tokenize(props.text) : [])

// ═══ Hover IPA state ═══
const hoverToken = ref(null)     // { text, index, phonetic, el }
let hoverTimer = null
const ipaCache = new Map()

// ═══ Click WordCard state ═══
const activeWord = ref(null)     // { text, index, phonetic, explanation, loading, el }
const explainCache = new Map()

// ═══ Float position ═══
const floatStyle = ref({})
const cardStyle = ref({})

function getTokenEl(idx) {
  const container = document.querySelector('.result-tokens')
  return container?.querySelector(`[data-token-idx="${idx}"]`)
}

function positionFloat(el, target) {
  if (!el) return {}
  const rect = el.getBoundingClientRect()
  const container = el.closest('.result-body')
  if (!container) return {}
  const cRect = container.getBoundingClientRect()
  return {
    position: 'absolute',
    left: `${rect.left - cRect.left}px`,
    top: `${rect.bottom - cRect.top + 4}px`,
  }
}

// ═══ Hover handlers (event delegation) ═══
function onTokenMouseEnter(e) {
  const el = e.target.closest('[data-token-idx]')
  if (!el || el.dataset.interactive !== 'true') return
  const idx = parseInt(el.dataset.tokenIdx)
  const token = tokens.value[idx]
  if (!token || !token.interactive) return

  clearTimeout(hoverTimer)
  hoverTimer = setTimeout(async () => {
    // Don't show hover if WordCard is active for this word
    if (activeWord.value?.index === idx) return

    const text = token.text
    let phonetic = ipaCache.get(text)
    if (phonetic === undefined) {
      try {
        const data = await authFetchJson(`${API.ARTICLES}/explain/phonetic`, { text })
        phonetic = data.phonetic || null
      } catch {
        phonetic = null
      }
      ipaCache.set(text, phonetic)
    }

    // Check still hovering the same token
    if (hoverToken.value?.index === idx || !el.matches(':hover')) {
      // Already showing or moved away
    }
    hoverToken.value = { text, index: idx, phonetic, el }
    floatStyle.value = positionFloat(el)
  }, 100)
}

function onTokenMouseLeave(e) {
  const related = e.relatedTarget
  // Sticky: don't dismiss if moving to the float itself
  if (related?.closest('.ipa-float')) return
  clearTimeout(hoverTimer)
  hoverToken.value = null
}

function onFloatMouseLeave(e) {
  const related = e.relatedTarget
  if (related?.closest('[data-token-idx]')) return
  hoverToken.value = null
}

// ═══ Click handlers ═══
async function onTokenClick(e) {
  const el = e.target.closest('[data-token-idx]')
  if (!el || el.dataset.interactive !== 'true') return
  const idx = parseInt(el.dataset.tokenIdx)
  const token = tokens.value[idx]
  if (!token?.interactive) return

  // Toggle: click same word closes it
  if (activeWord.value?.index === idx) {
    activeWord.value = null
    return
  }

  // Dismiss hover
  hoverToken.value = null

  const text = token.text
  const phonetic = ipaCache.get(text) || ''

  activeWord.value = {
    text,
    index: idx,
    phonetic,
    explanation: explainCache.get(text) || null,
    loading: !explainCache.has(text),
    el,
  }
  cardStyle.value = positionFloat(el)

  if (!explainCache.has(text)) {
    try {
      const data = await authFetchJson(`${API.ARTICLES}/explain`, {
        text,
        kind: 'word',
        context: props.text,
        refresh: false,
      })
      const exp = data.explanation || {}
      explainCache.set(text, exp)
      // Update if still active
      if (activeWord.value?.text === text) {
        activeWord.value = { ...activeWord.value, explanation: exp, loading: false }
      }
    } catch {
      if (activeWord.value?.text === text) {
        activeWord.value = { ...activeWord.value, loading: false }
      }
    }
  }
}

function onTokenKeydown(e) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    onTokenClick(e)
  } else if (e.key === 'Escape') {
    activeWord.value = null
    hoverToken.value = null
  }
}

function closeCard() {
  activeWord.value = null
}

// Close card on outside click
function onBodyClick(e) {
  if (!e.target.closest('.word-card') && !e.target.closest('[data-token-idx]')) {
    activeWord.value = null
  }
}

// Close on Escape
function onKeydownEsc(e) {
  if (e.key === 'Escape') {
    activeWord.value = null
    hoverToken.value = null
  }
}

// Reset state when text changes
watch(() => props.text, () => {
  activeWord.value = null
  hoverToken.value = null
})
</script>

<template>
  <div class="result-panel" @keydown="onKeydownEsc">
    <div class="panel-header">
      <span class="lang-badge">
        {{ direction === 'zh2en' ? 'English' : '中文' }}
      </span>
    </div>

    <div class="result-body" @click="onBodyClick">
      <!-- Loading state -->
      <div v-if="loading" class="state-placeholder loading" aria-live="polite">
        <span class="loading-dots">翻译中</span>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="state-placeholder error">
        {{ error }}
      </div>

      <!-- Stale indicator -->
      <div v-else-if="stale && text" class="stale-banner" role="status">
        已切换方向，结果仅供参考，请重新翻译
      </div>

      <!-- Tokenized result text -->
      <div
        v-if="text && !loading"
        class="result-tokens"
        :class="{ stale }"
        aria-label="译文"
        @mouseover="onTokenMouseEnter"
        @mouseout="onTokenMouseLeave"
        @click="onTokenClick"
        @keydown="onTokenKeydown"
      >
        <template v-for="t in tokens" :key="t.index">
          <span
            v-if="t.interactive"
            class="token interactive"
            :class="{ active: activeWord?.index === t.index }"
            :data-token-idx="t.index"
            data-interactive="true"
            tabindex="0"
            role="button"
          >{{ t.text }}</span>
          <span v-else class="token">{{ t.text }}</span>
        </template>
      </div>

      <!-- Empty placeholder -->
      <div v-if="!text && !loading && !error" class="state-placeholder empty">
        译文会显示在这里
      </div>

      <!-- IPA hover float -->
      <div
        v-if="hoverToken && hoverToken.phonetic"
        class="ipa-float"
        :style="floatStyle"
        @mouseleave="onFloatMouseLeave"
      >
        <span class="ipa-word">{{ hoverToken.text }}</span>
        <span class="ipa-text">/{{ hoverToken.phonetic }}/</span>
      </div>

      <!-- WordCard (click expand) -->
      <WordCard
        v-if="activeWord"
        :word="activeWord.text"
        :phonetic="activeWord.phonetic"
        :loading="activeWord.loading"
        :explanation="activeWord.explanation"
        :style="cardStyle"
        @close="closeCard"
      />
    </div>

    <!-- Footer -->
    <div v-if="text && !loading" class="footer">
      <span v-if="savedToVocab" class="vocab-saved">已自动加入生词本</span>
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  height: 100%;
  min-height: 320px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.lang-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.result-body {
  flex: 1;
  padding: var(--space-3);
  overflow-y: auto;
  position: relative;
}

/* Tokenized text */
.result-tokens {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-1);
  word-break: break-word;
}

.result-tokens.stale {
  opacity: 0.6;
}

.token.interactive {
  cursor: pointer;
  border-radius: 2px;
  transition: background 0.15s ease;
}

.token.interactive:hover {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
}

.token.interactive:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.token.interactive.active {
  background: color-mix(in srgb, var(--accent) 25%, transparent);
}

/* Disable hover effects on touch devices */
@media (hover: none) {
  .token.interactive:hover {
    background: transparent;
  }
}

/* IPA hover float */
.ipa-float {
  position: absolute;
  z-index: 50;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 4px 8px;
  pointer-events: auto;
  white-space: nowrap;
  font-size: 13px;
}

.ipa-word {
  font-weight: 600;
  color: var(--text-1);
  margin-right: 6px;
}

.ipa-text {
  color: var(--text-2);
}

/* States */
.state-placeholder {
  font-size: 14px;
  color: var(--text-3);
}

.state-placeholder.empty {
  font-style: italic;
}

.state-placeholder.loading {
  font-style: italic;
}

.loading-dots::after {
  content: '';
  animation: dots 1.2s steps(3, end) infinite;
}

@keyframes dots {
  0%   { content: ''; }
  33%  { content: '.'; }
  66%  { content: '..'; }
  100% { content: '...'; }
}

.state-placeholder.error {
  color: #c6463a;
}

.stale-banner {
  font-size: 12px;
  color: #e67e22;
  background: color-mix(in srgb, #e67e22 10%, transparent);
  border: 1px solid color-mix(in srgb, #e67e22 30%, transparent);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  margin-bottom: var(--space-2);
}

.footer {
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--border);
  background: var(--bg);
  min-height: 32px;
}

.vocab-saved {
  font-size: 12px;
  color: var(--accent);
}
</style>
