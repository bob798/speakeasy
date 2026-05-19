<template>
  <div class="vocab-page">
    <header class="vocab-header">
      <h1>我的生词本</h1>
      <span class="vocab-count">已加载 {{ items.length }} 条</span>
    </header>

    <nav class="tag-chips">
      <button
        v-for="t in tabs"
        :key="t.value"
        :class="['chip', { active: currentTag === t.value }]"
        @click="switchTag(t.value)"
      >
        {{ t.label }}
      </button>
    </nav>

    <div v-if="loading" class="vocab-loading">加载中...</div>
    <div v-else-if="items.length === 0" class="vocab-empty">暂无条目</div>
    <ul v-else class="vocab-list">
      <li v-for="item in items" :key="item.id" class="vocab-item">
        <div class="vocab-head" @click="toggle(item.id)">
          <span class="vocab-text">{{ truncate(item.source_text, 80) }}</span>
          <span :class="['vocab-tag', `tag-${item.source_type}`]">{{ tagLabel(item.source_type) }}</span>
        </div>
        <div class="vocab-translated">{{ item.translated_text || '—' }}</div>
        <div class="vocab-meta">
          ⏱ {{ relativeTime(item.created_at) }}
          <span v-if="!item.explanation_json" class="vocab-pending">⚠ 解读生成中</span>
        </div>
        <div v-if="expandedId === item.id" class="vocab-detail">
          <template v-if="parsedExplanation(item)">
            <div v-if="parsedExplanation(item).phonetic" class="exp-row">
              <strong>音标：</strong>/{{ parsedExplanation(item).phonetic }}/
            </div>
            <div v-if="parsedExplanation(item).meaning" class="exp-row">
              <strong>含义：</strong>{{ parsedExplanation(item).meaning }}
            </div>
            <div v-if="parsedExplanation(item).grammar" class="exp-row">
              <strong>语法：</strong>{{ parsedExplanation(item).grammar }}
            </div>
            <div v-if="parsedExplanation(item).definitions?.length" class="exp-row">
              <strong>释义：</strong>
              <ul><li v-for="d in parsedExplanation(item).definitions" :key="d">{{ d }}</li></ul>
            </div>
            <div v-if="parsedExplanation(item).examples?.length" class="exp-row">
              <strong>例句：</strong>
              <ul><li v-for="e in parsedExplanation(item).examples" :key="e">{{ e }}</li></ul>
            </div>
            <div v-if="parsedExplanation(item).phrases?.length" class="exp-row">
              <strong>短语：</strong>
              <ul><li v-for="p in parsedExplanation(item).phrases" :key="JSON.stringify(p)">{{ typeof p === 'string' ? p : (p.phrase + ' — ' + p.meaning) }}</li></ul>
            </div>
            <div v-if="parsedExplanation(item).liaison?.length" class="exp-row">
              <strong>连读：</strong>
              <ul><li v-for="l in parsedExplanation(item).liaison" :key="JSON.stringify(l)">{{ typeof l === 'string' ? l : JSON.stringify(l) }}</li></ul>
            </div>
          </template>
          <template v-else>
            <!-- Task 15 接入 pending 重拉 -->
            <button class="exp-fetch" @click="fetchPending(item)">点击生成解读</button>
          </template>
        </div>
      </li>
    </ul>

    <div v-if="hasMore" class="vocab-loadmore">
      <button @click="loadMore">加载更多</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetch } = useAuthFetch()

const tabs = [
  { value: '', label: '全部' },
  { value: 'bbc_eaw', label: 'BBC' },
  { value: 'translate', label: '翻译收藏' },
]

const currentTag = ref('')
const items = ref([])
const loading = ref(false)
const expandedId = ref(null)
const offset = ref(0)
const PAGE_SIZE = 20
const hasMore = ref(false)

function tagLabel(source_type) {
  return tabs.find(t => t.value === source_type)?.label || source_type
}

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}

function relativeTime(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

async function fetchList(reset = false) {
  loading.value = true
  if (reset) {
    offset.value = 0
    items.value = []
  }
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset.value),
  })
  if (currentTag.value) params.set('source_type', currentTag.value)
  try {
    const resp = await authFetch(`${API.VOCAB}?${params}`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    const fetched = data.items || []
    items.value = reset ? fetched : [...items.value, ...fetched]
    hasMore.value = fetched.length === PAGE_SIZE
    offset.value += fetched.length
  } catch (err) {
    console.error('vocab list failed:', getErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

function switchTag(t) {
  currentTag.value = t
  fetchList(true)
}

function loadMore() {
  fetchList(false)
}

function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function parsedExplanation(item) {
  if (!item.explanation_json) return null
  try {
    return typeof item.explanation_json === 'string'
      ? JSON.parse(item.explanation_json)
      : item.explanation_json
  } catch {
    return null
  }
}

function fetchPending(item) {
  /* Task 15 实现 */
}

onMounted(() => fetchList(true))
</script>

<style scoped>
.vocab-page { padding: 16px; max-width: 720px; margin: 0 auto; }
.vocab-header { display: flex; align-items: baseline; gap: 12px; }
.vocab-count { color: #888; font-size: 14px; }
.tag-chips { display: flex; gap: 8px; margin: 12px 0; }
.chip { padding: 6px 14px; border-radius: 16px; border: 1px solid #ccc; background: transparent; cursor: pointer; }
.chip.active { background: var(--accent, #4a90e2); color: white; border-color: transparent; }
.vocab-list { list-style: none; padding: 0; }
.vocab-item { border-bottom: 1px solid #eee; padding: 12px 0; }
.vocab-head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.vocab-text { font-weight: 600; }
.vocab-tag { font-size: 12px; padding: 2px 8px; border-radius: 8px; background: #eee; }
.tag-bbc_eaw { background: #ffe9d6; }
.tag-translate { background: #d6f0ff; }
.vocab-translated { color: #555; margin: 4px 0; }
.vocab-meta { font-size: 12px; color: #888; }
.vocab-pending { color: #c97c00; margin-left: 8px; }
.vocab-loadmore { text-align: center; margin-top: 16px; }
.vocab-empty, .vocab-loading { padding: 24px; text-align: center; color: #888; }
.vocab-detail { padding: 12px 0 4px; border-top: 1px dashed #ddd; margin-top: 8px; }
.exp-row { margin: 6px 0; }
.exp-row ul { margin: 4px 0 4px 18px; }
.exp-fetch { padding: 6px 12px; border: 1px solid #4a90e2; color: #4a90e2; background: transparent; border-radius: 8px; cursor: pointer; }
</style>
