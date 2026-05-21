<template>
  <div class="library-page">
    <header class="library-header">
      <div class="library-header-inner">
        <div class="library-title-row">
          <h1>我的文章库</h1>
          <button class="btn-add" @click="showModal = true">+ 添加文章</button>
        </div>
      </div>
    </header>

    <main class="library-main">
      <div v-if="loading" class="library-loading">加载中...</div>
      <div v-else-if="articles.length === 0" class="library-empty">
        <p>暂无文章，点击右上角「添加文章」导入第一篇</p>
      </div>
      <ul v-else class="article-list">
        <li
          v-for="article in articles"
          :key="article.id"
          class="article-card"
          @click="goToArticle(article.id)"
        >
          <h2 class="article-title">{{ article.title }}</h2>
          <div class="article-meta">
            <span v-if="article.source_url" class="article-host">{{ hostOf(article.source_url) }}</span>
            <span class="article-words">{{ article.word_count.toLocaleString() }} 词</span>
            <span class="article-time">~{{ readingMinutes(article.word_count) }} 分钟读</span>
          </div>
          <div class="article-footer">
            <span class="article-age">{{ relativeTime(article.created_at) }}</span>
            <span v-if="article.vocab_count > 0" class="article-vocab">
              已沉淀 {{ article.vocab_count }} 个词
            </span>
          </div>
        </li>
      </ul>

      <div v-if="hasMore" class="library-loadmore">
        <button @click="loadMore" :disabled="loadingMore">
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </main>

    <!-- 添加文章模态框 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal-box">
        <div class="modal-header">
          <h2>添加文章</h2>
          <button class="modal-close" @click="closeModal">×</button>
        </div>

        <div class="modal-tabs">
          <button
            :class="['tab-btn', { active: importMode === 'url' }]"
            @click="importMode = 'url'"
          >粘贴 URL</button>
          <button
            :class="['tab-btn', { active: importMode === 'markdown' }]"
            @click="importMode = 'markdown'"
          >粘贴正文</button>
        </div>

        <!-- URL 模式 -->
        <div v-if="importMode === 'url'" class="modal-body">
          <label class="field-label">文章 URL</label>
          <input
            v-model="urlInput"
            class="field-input"
            type="url"
            placeholder="https://..."
            @keydown.enter="doImport"
          />
          <p v-if="importError" class="import-error">{{ importError }}</p>
          <p v-if="fetchFailHint" class="import-hint">{{ fetchFailHint }}</p>
        </div>

        <!-- Markdown 模式 -->
        <div v-if="importMode === 'markdown'" class="modal-body">
          <label class="field-label">标题（必填）</label>
          <input
            v-model="titleInput"
            class="field-input"
            type="text"
            placeholder="文章标题"
          />
          <label class="field-label">正文（Markdown）</label>
          <textarea
            v-model="markdownInput"
            class="field-textarea"
            placeholder="粘贴 Markdown 或纯文本正文..."
            rows="8"
          ></textarea>
          <p v-if="importError" class="import-error">{{ importError }}</p>
        </div>

        <div class="modal-footer">
          <button class="btn-cancel" @click="closeModal">取消</button>
          <button
            class="btn-import"
            :disabled="importing || !canImport"
            @click="doImport"
          >
            {{ importing ? '导入中...' : '导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const router = useRouter()
const { authFetchJson } = useAuthFetch()

// List state
const articles = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const hasMore = ref(false)

// Modal state
const showModal = ref(false)
const importMode = ref('url')
const urlInput = ref('')
const titleInput = ref('')
const markdownInput = ref('')
const importing = ref(false)
const importError = ref('')
const fetchFailHint = ref('')

const canImport = computed(() => {
  if (importMode.value === 'url') return urlInput.value.trim().length > 0
  return titleInput.value.trim().length > 0 && markdownInput.value.trim().length > 0
})

function hostOf(url) {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

function readingMinutes(wordCount) {
  return Math.max(1, Math.round(wordCount / 200))
}

function relativeTime(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 2) return '昨天'
  return `${Math.floor(diff / 86400)} 天前`
}

async function fetchArticles(reset = false) {
  if (reset) {
    loading.value = true
    page.value = 1
    articles.value = []
  } else {
    loadingMore.value = true
  }
  try {
    const data = await authFetchJson(`${API.LIBRARY}/articles?page=${page.value}&page_size=${PAGE_SIZE}`)
    const fetched = data.articles || []
    articles.value = reset ? fetched : [...articles.value, ...fetched]
    hasMore.value = fetched.length === PAGE_SIZE
    page.value++
  } catch (err) {
    console.error('library list failed:', getErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  await fetchArticles(false)
}

function goToArticle(id) {
  router.push({ name: 'library-article', params: { id } })
}

function closeModal() {
  showModal.value = false
  importError.value = ''
  fetchFailHint.value = ''
  urlInput.value = ''
  titleInput.value = ''
  markdownInput.value = ''
  importMode.value = 'url'
}

async function doImport() {
  if (!canImport.value || importing.value) return
  importing.value = true
  importError.value = ''
  fetchFailHint.value = ''

  const body = {}
  if (importMode.value === 'url') {
    body.url = urlInput.value.trim()
  } else {
    body.markdown = markdownInput.value.trim()
    body.title = titleInput.value.trim()
  }

  try {
    const data = await authFetchJson(`${API.LIBRARY}/articles`, body)
    closeModal()
    if (data.existing) {
      // Navigate directly to existing article
      router.push({ name: 'library-article', params: { id: data.id } })
    } else {
      // Reload list and navigate
      await fetchArticles(true)
      router.push({ name: 'library-article', params: { id: data.id } })
    }
  } catch (err) {
    const msg = err?.detail || err?.message || ''
    if (typeof err?.detail === 'object' && err.detail?.error === 'fetch_failed') {
      fetchFailHint.value = err.detail.hint || '抓取失败，请改用粘贴正文模式'
      importMode.value = 'markdown'
      importError.value = '该页面无法自动抓取'
    } else {
      importError.value = getErrorMessage(err, '导入失败，请重试')
    }
  } finally {
    importing.value = false
  }
}

onMounted(() => {
  fetchArticles(true)
})
</script>

<style scoped>
.library-page {
  min-height: 100vh;
  background: var(--color-bg, #f5f0eb);
  font-family: var(--font-sans, system-ui, sans-serif);
}

.library-header {
  background: var(--color-surface, #fff);
  border-bottom: 1px solid var(--color-border, #e8e0d8);
  padding: 16px 24px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.library-header-inner {
  max-width: 800px;
  margin: 0 auto;
}

.library-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.library-title-row h1 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text, #2d2320);
  margin: 0;
}

.btn-add {
  padding: 8px 16px;
  background: var(--color-primary, #c8845c);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-add:hover {
  opacity: 0.9;
}

.library-main {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}

.library-loading,
.library-empty {
  text-align: center;
  color: var(--color-text-muted, #8a7d75);
  padding: 48px 0;
}

.article-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.article-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e8e0d8);
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
  transition: box-shadow 0.15s;
}

.article-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.article-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text, #2d2320);
  margin: 0 0 6px;
  line-height: 1.4;
}

.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.82rem;
  color: var(--color-text-muted, #8a7d75);
  margin-bottom: 8px;
}

.article-host {
  color: var(--color-primary, #c8845c);
}

.article-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--color-text-muted, #8a7d75);
}

.article-vocab {
  color: var(--color-primary, #c8845c);
}

.library-loadmore {
  text-align: center;
  margin-top: 24px;
}

.library-loadmore button {
  padding: 8px 24px;
  border: 1px solid var(--color-border, #e8e0d8);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  color: var(--color-text, #2d2320);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 16px;
}

.modal-box {
  background: var(--color-surface, #fff);
  border-radius: 16px;
  width: 100%;
  max-width: 480px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}

.modal-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
  color: var(--color-text, #2d2320);
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
  color: var(--color-text-muted, #8a7d75);
  line-height: 1;
  padding: 4px;
}

.modal-tabs {
  display: flex;
  gap: 0;
  padding: 16px 24px 0;
  border-bottom: 1px solid var(--color-border, #e8e0d8);
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--color-text-muted, #8a7d75);
  font-size: 0.9rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.tab-btn.active {
  color: var(--color-primary, #c8845c);
  border-bottom-color: var(--color-primary, #c8845c);
  font-weight: 500;
}

.modal-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text, #2d2320);
}

.field-input,
.field-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border, #e8e0d8);
  border-radius: 8px;
  font-size: 0.9rem;
  font-family: inherit;
  box-sizing: border-box;
  background: var(--color-bg, #f5f0eb);
  color: var(--color-text, #2d2320);
}

.field-textarea {
  resize: vertical;
  min-height: 120px;
}

.import-error {
  color: #d44;
  font-size: 0.85rem;
  margin: 0;
}

.import-hint {
  color: var(--color-primary, #c8845c);
  font-size: 0.85rem;
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 0 24px 20px;
}

.btn-cancel {
  padding: 9px 18px;
  border: 1px solid var(--color-border, #e8e0d8);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  color: var(--color-text, #2d2320);
  font-size: 0.9rem;
}

.btn-import {
  padding: 9px 18px;
  background: var(--color-primary, #c8845c);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-import:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
