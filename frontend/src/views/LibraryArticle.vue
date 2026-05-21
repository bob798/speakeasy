<template>
  <div class="article-page">
    <!-- Top bar -->
    <header class="article-topbar">
      <button class="back-btn" @click="goBack">← 返回</button>
      <h1 class="article-topbar-title">{{ article?.title || '加载中...' }}</h1>
      <button v-if="article" class="delete-btn" @click="confirmDelete">删除</button>
    </header>

    <div v-if="loading" class="article-loading">加载中...</div>
    <div v-else-if="!article" class="article-error">文章不存在或已删除</div>

    <div v-else class="article-layout">
      <!-- Main reading area -->
      <main class="article-content" ref="contentRef" @mouseup="onMouseUp">
        <div class="markdown-body" v-html="renderedMarkdown"></div>

        <!-- Floating bubble for word click / selection -->
        <div
          v-if="bubble.visible"
          class="float-bubble"
          :style="{ top: bubble.top + 'px', left: bubble.left + 'px' }"
        >
          <!-- Word click bubble: show IPA + expand button -->
          <template v-if="bubble.mode === 'word'">
            <span class="bubble-ipa">{{ bubble.ipa || '...' }}</span>
            <button class="bubble-btn" @click="expandExplain(bubble.text, 'word')">展开解读</button>
          </template>
          <!-- Selection bubble: translate button -->
          <template v-else-if="bubble.mode === 'selection'">
            <button class="bubble-btn" @click="expandExplain(bubble.text, 'sentence')">翻译</button>
          </template>
        </div>
      </main>

      <!-- Right sidebar: 本文沉淀 -->
      <aside :class="['article-sidebar', { open: sidebarOpen }]">
        <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">
          本文沉淀 ({{ vocabItems.length }})
        </button>
        <div class="sidebar-body">
          <div v-if="vocabLoading" class="sidebar-loading">加载中...</div>
          <div v-else-if="vocabItems.length === 0" class="sidebar-empty">暂无沉淀语言点</div>
          <ul v-else class="vocab-list">
            <li
              v-for="item in vocabItems"
              :key="item.id"
              :class="['vocab-item', { expanded: expandedVocabId === item.id }]"
            >
              <div class="vocab-head" @click="toggleVocab(item)">
                <span class="vocab-text">{{ truncate(item.source_text, 50) }}</span>
                <span :class="['vocab-badge', item.explanation_json ? 'ready' : 'pending']">
                  {{ item.explanation_json ? 'ready' : 'pending' }}
                </span>
              </div>
              <div v-if="expandedVocabId === item.id" class="vocab-detail">
                <template v-if="parsedExp(item)">
                  <div v-if="parsedExp(item).phonetic" class="exp-row">
                    <strong>/{{ parsedExp(item).phonetic }}/</strong>
                  </div>
                  <div v-if="parsedExp(item).meaning" class="exp-row">{{ parsedExp(item).meaning }}</div>
                  <div v-if="parsedExp(item).grammar" class="exp-row exp-minor">{{ parsedExp(item).grammar }}</div>
                  <div v-if="parsedExp(item).definitions?.length" class="exp-row">
                    <ul><li v-for="d in parsedExp(item).definitions" :key="d">{{ d }}</li></ul>
                  </div>
                  <div v-if="parsedExp(item).examples?.length" class="exp-row">
                    <ul><li v-for="e in parsedExp(item).examples" :key="e">{{ e }}</li></ul>
                  </div>
                </template>
                <template v-else>
                  <button
                    class="exp-fetch-btn"
                    :disabled="item._fetching"
                    @click="fetchPending(item)"
                  >
                    {{ item._fetching ? '生成中...' : '点击生成解读' }}
                  </button>
                  <p v-if="item._fetchError" class="exp-error">{{ item._fetchError }}</p>
                </template>
              </div>
            </li>
          </ul>
        </div>
      </aside>
    </div>

    <!-- Explanation detail modal/overlay (for expanded explain) -->
    <div v-if="explainModal.visible" class="explain-overlay" @click.self="explainModal.visible = false">
      <div class="explain-box">
        <div class="explain-header">
          <strong>{{ explainModal.text }}</strong>
          <button @click="explainModal.visible = false">×</button>
        </div>
        <div v-if="explainModal.loading" class="explain-loading">解读中...</div>
        <div v-else-if="explainModal.error" class="explain-error">{{ explainModal.error }}</div>
        <div v-else class="explain-body">
          <div v-if="explainModal.data?.phonetic" class="exp-row">
            <strong>/{{ explainModal.data.phonetic }}/</strong>
          </div>
          <div v-if="explainModal.data?.meaning" class="exp-row">{{ explainModal.data.meaning }}</div>
          <div v-if="explainModal.data?.grammar" class="exp-row exp-minor">{{ explainModal.data.grammar }}</div>
          <div v-if="explainModal.data?.definitions?.length" class="exp-row">
            <ul><li v-for="d in explainModal.data.definitions" :key="d">{{ d }}</li></ul>
          </div>
          <div v-if="explainModal.data?.examples?.length" class="exp-row">
            <ul><li v-for="e in explainModal.data.examples" :key="e">{{ e }}</li></ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const router = useRouter()
const route = useRoute()
const { authFetch, authFetchJson } = useAuthFetch()

const articleId = computed(() => Number(route.params.id))

// Article state
const article = ref(null)
const loading = ref(true)

// Sidebar state
const sidebarOpen = ref(true)
const vocabItems = ref([])
const vocabLoading = ref(false)
const expandedVocabId = ref(null)

// Floating bubble state
const contentRef = ref(null)
const bubble = ref({ visible: false, top: 0, left: 0, text: '', ipa: '', mode: 'word' })

// Explain modal state
const explainModal = ref({ visible: false, text: '', loading: false, error: '', data: null })

// ── Markdown renderer (simple, no external deps) ──────────

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMarkdown(md) {
  if (!md) return ''
  const lines = md.split('\n')
  const result = []
  let inCode = false
  let codeLang = ''
  let codeLines = []
  let inList = false

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Code block
    if (line.startsWith('```')) {
      if (!inCode) {
        inCode = true
        codeLang = line.slice(3).trim()
        codeLines = []
        if (inList) { result.push('</ul>'); inList = false }
      } else {
        inCode = false
        const escaped = codeLines.map(escapeHtml).join('\n')
        result.push(`<pre><code${codeLang ? ` class="language-${escapeHtml(codeLang)}"` : ''}>${escaped}</code></pre>`)
        codeLines = []
        codeLang = ''
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    // Headings
    const hMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (hMatch) {
      if (inList) { result.push('</ul>'); inList = false }
      const level = hMatch[1].length
      result.push(`<h${level}>${inlineFormat(hMatch[2])}</h${level}>`)
      continue
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim()) || /^\*\*\*+$/.test(line.trim())) {
      if (inList) { result.push('</ul>'); inList = false }
      result.push('<hr>')
      continue
    }

    // Unordered list
    const liMatch = line.match(/^[\s]*[-*+]\s+(.+)$/)
    if (liMatch) {
      if (!inList) { result.push('<ul>'); inList = true }
      result.push(`<li>${inlineFormat(liMatch[1])}</li>`)
      continue
    }

    // Close list if needed
    if (inList && line.trim() === '') {
      result.push('</ul>')
      inList = false
    }

    // Blank line = paragraph break
    if (line.trim() === '') {
      result.push('<br>')
      continue
    }

    // Paragraph
    if (inList) { result.push('</ul>'); inList = false }
    result.push(`<p>${inlineFormat(line)}</p>`)
  }

  if (inList) result.push('</ul>')
  if (inCode && codeLines.length) {
    result.push(`<pre><code>${codeLines.map(escapeHtml).join('\n')}</code></pre>`)
  }

  return result.join('')
}

function inlineFormat(text) {
  // Bold **...**
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic *...*
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Inline code `...`
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Links [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  return text
}

const renderedMarkdown = computed(() => {
  if (!article.value?.markdown) return ''
  return renderMarkdown(article.value.markdown)
})

// ── Data loading ───────────────────────────────────────────

async function loadArticle() {
  loading.value = true
  try {
    article.value = await authFetchJson(`${API.LIBRARY}/articles/${articleId.value}`)
  } catch (err) {
    article.value = null
  } finally {
    loading.value = false
  }
}

async function loadVocab() {
  vocabLoading.value = true
  try {
    const resp = await authFetch(
      `${API.VOCAB}?source_type=library&source_ref=${articleId.value}&limit=200`
    )
    if (!resp.ok) throw new Error('load failed')
    const data = await resp.json()
    vocabItems.value = (data.items || []).map(it => ({ ...it, _fetching: false, _fetchError: '' }))
  } catch (err) {
    console.error('vocab load failed:', err)
  } finally {
    vocabLoading.value = false
  }
}

// ── Navigation ─────────────────────────────────────────────

function goBack() {
  router.push({ name: 'library' })
}

async function confirmDelete() {
  if (!confirm('确定删除这篇文章？（已沉淀的生词不受影响）')) return
  try {
    await authFetchJson(`${API.LIBRARY}/articles/${articleId.value}`, null, { method: 'DELETE' })
    router.push({ name: 'library' })
  } catch (err) {
    alert(getErrorMessage(err, '删除失败'))
  }
}

// ── Word click / selection interaction ─────────────────────

function isInsideCode(node) {
  let el = node
  while (el) {
    if (el.tagName === 'PRE' || el.tagName === 'CODE') return true
    el = el.parentElement
  }
  return false
}

function getWordAtPoint(x, y) {
  const range = document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y) : null
  if (!range || !range.startContainer || range.startContainer.nodeType !== Node.TEXT_NODE) return null
  if (isInsideCode(range.startContainer)) return null

  const text = range.startContainer.textContent || ''
  const offset = range.startOffset

  // Expand left and right to word boundaries
  let start = offset
  let end = offset
  while (start > 0 && /\w/.test(text[start - 1])) start--
  while (end < text.length && /\w/.test(text[end])) end++
  const word = text.slice(start, end).trim()
  return word || null
}

async function onMouseUp(e) {
  await nextTick()
  const selection = window.getSelection()
  const selectedText = selection ? selection.toString().trim() : ''

  if (selectedText.length >= 2) {
    // Selection mode
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    const containerRect = contentRef.value.getBoundingClientRect()
    bubble.value = {
      visible: true,
      top: rect.top - containerRect.top - 44,
      left: Math.max(0, rect.left - containerRect.left),
      text: selectedText,
      ipa: '',
      mode: 'selection',
    }
    return
  }

  // Word click
  const word = getWordAtPoint(e.clientX, e.clientY)
  if (!word) {
    bubble.value.visible = false
    return
  }

  const containerRect = contentRef.value.getBoundingClientRect()
  bubble.value = {
    visible: true,
    top: e.clientY - containerRect.top - 44,
    left: Math.max(0, e.clientX - containerRect.left - 40),
    text: word,
    ipa: '...',
    mode: 'word',
  }

  // Fetch IPA
  try {
    const data = await authFetchJson(
      `${API.LIBRARY}/articles/${articleId.value}/explain/phonetic`,
      { text: word, item_type: 'word' },
    )
    if (bubble.value.text === word) {
      bubble.value.ipa = data.phonetic || ''
    }
  } catch (err) {
    if (bubble.value.text === word) bubble.value.ipa = ''
  }
}

function closeBubble() {
  bubble.value.visible = false
}

async function expandExplain(text, kind) {
  closeBubble()
  explainModal.value = { visible: true, text, loading: true, error: '', data: null }

  try {
    const result = await authFetchJson(
      `${API.LIBRARY}/articles/${articleId.value}/explain`,
      { text, kind },
    )
    explainModal.value.data = result.explanation || null
    explainModal.value.loading = false
    // Refresh vocab sidebar
    loadVocab()
  } catch (err) {
    explainModal.value.error = getErrorMessage(err, '解读失败，请重试')
    explainModal.value.loading = false
  }
}

// ── Vocab sidebar ──────────────────────────────────────────

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}

function parsedExp(item) {
  if (!item.explanation_json) return null
  try {
    return JSON.parse(item.explanation_json)
  } catch {
    return null
  }
}

function toggleVocab(item) {
  expandedVocabId.value = expandedVocabId.value === item.id ? null : item.id
}

async function fetchPending(item) {
  item._fetching = true
  item._fetchError = ''
  try {
    const result = await authFetchJson(
      `${API.LIBRARY}/articles/${articleId.value}/explain`,
      { text: item.source_text, kind: item.item_type === 'sentence' ? 'sentence' : 'word' },
    )
    const idx = vocabItems.value.findIndex(v => v.id === item.id)
    if (idx !== -1) {
      vocabItems.value[idx] = {
        ...vocabItems.value[idx],
        explanation_json: JSON.stringify(result.explanation || {}),
        _fetching: false,
        _fetchError: '',
      }
    }
  } catch (err) {
    item._fetching = false
    item._fetchError = getErrorMessage(err, '生成失败，请稍后重试')
  }
}

// ── Click outside to close bubble ─────────────────────────

function onDocClick(e) {
  if (bubble.value.visible) {
    const floatEl = document.querySelector('.float-bubble')
    if (floatEl && !floatEl.contains(e.target)) {
      bubble.value.visible = false
    }
  }
}

onMounted(async () => {
  await loadArticle()
  loadVocab()
  document.addEventListener('click', onDocClick, true)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick, true)
})
</script>

<style scoped>
.article-page {
  min-height: 100vh;
  background: var(--color-bg, #f5f0eb);
  font-family: var(--font-sans, system-ui, sans-serif);
}

/* Top bar */
.article-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  background: var(--color-surface, #fff);
  border-bottom: 1px solid var(--color-border, #e8e0d8);
  position: sticky;
  top: 0;
  z-index: 10;
}

.back-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary, #c8845c);
  font-size: 0.9rem;
  white-space: nowrap;
  padding: 4px 8px;
}

.article-topbar-title {
  flex: 1;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text, #2d2320);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn {
  background: none;
  border: 1px solid #d44;
  color: #d44;
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
}

/* Layout */
.article-loading,
.article-error {
  text-align: center;
  color: var(--color-text-muted, #8a7d75);
  padding: 48px;
}

.article-layout {
  display: flex;
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  align-items: flex-start;
  position: relative;
}

/* Main content */
.article-content {
  flex: 1;
  min-width: 0;
  max-width: 720px;
  background: var(--color-surface, #fff);
  border-radius: 12px;
  padding: 32px;
  position: relative;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* Markdown styles */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  color: var(--color-text, #2d2320);
  margin: 1.2em 0 0.5em;
  line-height: 1.3;
}

.markdown-body :deep(h1) { font-size: 1.5rem; }
.markdown-body :deep(h2) { font-size: 1.25rem; }
.markdown-body :deep(h3) { font-size: 1.1rem; }

.markdown-body :deep(p) {
  margin: 0.7em 0;
  line-height: 1.7;
  color: var(--color-text, #2d2320);
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.3em 0;
  line-height: 1.6;
}

.markdown-body :deep(pre) {
  background: #f4f4f4;
  border-radius: 6px;
  padding: 12px 16px;
  overflow-x: auto;
  margin: 1em 0;
  user-select: text;
}

.markdown-body :deep(code) {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 0.88em;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-body :deep(a) {
  color: var(--color-primary, #c8845c);
  text-decoration: none;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border, #e8e0d8);
  margin: 1.5em 0;
}

/* Floating bubble */
.float-bubble {
  position: absolute;
  background: #2d2320;
  color: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 50;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.25);
  white-space: nowrap;
  pointer-events: auto;
}

.bubble-ipa {
  font-style: italic;
  opacity: 0.85;
}

.bubble-btn {
  background: var(--color-primary, #c8845c);
  border: none;
  color: #fff;
  border-radius: 5px;
  padding: 3px 10px;
  font-size: 0.8rem;
  cursor: pointer;
}

/* Sidebar */
.article-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--color-surface, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.sidebar-toggle {
  width: 100%;
  padding: 14px 16px;
  background: none;
  border: none;
  border-bottom: 1px solid var(--color-border, #e8e0d8);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text, #2d2320);
  cursor: pointer;
  text-align: left;
}

.sidebar-body {
  padding: 8px 0;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}

.sidebar-loading,
.sidebar-empty {
  padding: 16px;
  color: var(--color-text-muted, #8a7d75);
  font-size: 0.85rem;
  text-align: center;
}

.vocab-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.vocab-item {
  border-bottom: 1px solid var(--color-border, #e8e0d8);
}

.vocab-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  gap: 8px;
}

.vocab-head:hover {
  background: var(--color-bg, #f5f0eb);
}

.vocab-text {
  font-size: 0.88rem;
  color: var(--color-text, #2d2320);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vocab-badge {
  font-size: 0.72rem;
  border-radius: 4px;
  padding: 1px 5px;
  font-weight: 500;
  flex-shrink: 0;
}

.vocab-badge.ready {
  background: #e6f4e6;
  color: #2a6e2a;
}

.vocab-badge.pending {
  background: #fff3e0;
  color: #9a6000;
}

.vocab-detail {
  padding: 8px 16px 12px;
  background: var(--color-bg, #f5f0eb);
  border-top: 1px solid var(--color-border, #e8e0d8);
}

.exp-row {
  font-size: 0.85rem;
  color: var(--color-text, #2d2320);
  margin: 4px 0;
  line-height: 1.5;
}

.exp-minor {
  color: var(--color-text-muted, #8a7d75);
}

.exp-row ul {
  margin: 4px 0;
  padding-left: 1.2em;
}

.exp-row li {
  margin: 2px 0;
}

.exp-fetch-btn {
  padding: 6px 12px;
  background: var(--color-primary, #c8845c);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
}

.exp-fetch-btn:disabled {
  opacity: 0.6;
}

.exp-error {
  color: #d44;
  font-size: 0.8rem;
  margin: 4px 0 0;
}

/* Explain modal */
.explain-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 200;
  padding: 0;
}

@media (min-width: 640px) {
  .explain-overlay {
    align-items: center;
  }
}

.explain-box {
  background: var(--color-surface, #fff);
  border-radius: 16px 16px 0 0;
  width: 100%;
  max-width: 540px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 20px 24px 32px;
}

@media (min-width: 640px) {
  .explain-box {
    border-radius: 16px;
    max-height: 60vh;
  }
}

.explain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.explain-header strong {
  font-size: 1.05rem;
}

.explain-header button {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--color-text-muted, #8a7d75);
}

.explain-loading,
.explain-error {
  padding: 16px 0;
  color: var(--color-text-muted, #8a7d75);
  font-size: 0.9rem;
}

.explain-error {
  color: #d44;
}

.explain-body .exp-row {
  margin: 6px 0;
}

/* Responsive */
@media (max-width: 1280px) {
  .article-sidebar {
    width: 240px;
  }
}

@media (max-width: 900px) {
  .article-layout {
    flex-direction: column;
    padding: 16px;
  }

  .article-sidebar {
    width: 100%;
  }

  .article-content {
    max-width: 100%;
  }
}
</style>
