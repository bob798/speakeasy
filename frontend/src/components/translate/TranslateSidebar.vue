<script setup>
/**
 * TranslateSidebar · 右侧生词本侧边栏 — PR3: FSRS + 收藏闭环
 *
 * - 加载 GET /vocab?limit=500 + 本地过滤 source_type=translate
 * - 4 档评分（again/hard/good/easy）→ POST /vocab/{id}/rate
 * - item_type chip 过滤（全部/单词/句子）
 * - due 倒计时
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const props = defineProps({
  open: { type: Boolean, default: true },
})

const { authFetchJson, authFetch } = useAuthFetch()

const items = ref([])
const loading = ref(false)
const filterType = ref('all') // 'all' | 'word' | 'sentence'

const filtered = computed(() => {
  let list = items.value.filter(v => v.source_type === 'translate' && v.status === 'active')
  if (filterType.value !== 'all') {
    list = list.filter(v => v.item_type === filterType.value)
  }
  return list
})

const dueCount = computed(() => filtered.value.filter(v => v.is_due).length)

async function loadVocab() {
  loading.value = true
  try {
    const resp = await authFetch(`${API.VOCAB}?limit=500`, { method: 'GET' })
    if (resp.ok) {
      const data = await resp.json()
      items.value = data.items || []
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function rateItem(id, rating) {
  try {
    const data = await authFetchJson(`${API.VOCAB}/${id}/rate`, { rating })
    // 用返回的 item 替换列表中的条目
    if (data.item) {
      const idx = items.value.findIndex(v => v.id === id)
      if (idx !== -1) items.value[idx] = data.item
    }
  } catch { /* ignore */ }
}

function dueLabel(due) {
  if (!due) return '待复习'
  const diff = new Date(due) - Date.now()
  if (diff <= 0) return '待复习'
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return `${Math.ceil(diff / 60000)}分钟后`
  if (hours < 24) return `${hours}小时后`
  return `${Math.floor(hours / 24)}天后`
}

onMounted(() => { if (props.open) loadVocab() })
watch(() => props.open, (v) => { if (v) loadVocab() })
</script>

<template>
  <aside v-if="open" class="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">📖 生词本</span>
      <span v-if="dueCount > 0" class="due-badge">{{ dueCount }} 待复习</span>
    </div>

    <!-- Type filter chips -->
    <div class="filter-bar">
      <button
        v-for="t in [{key:'all',label:'全部'},{key:'word',label:'单词'},{key:'sentence',label:'句子'}]"
        :key="t.key"
        class="chip"
        :class="{ active: filterType === t.key }"
        @click="filterType = t.key"
      >{{ t.label }}</button>
    </div>

    <div class="sidebar-body">
      <div v-if="loading" class="placeholder-text">加载中...</div>
      <div v-else-if="!filtered.length" class="placeholder-text">
        翻译内容会自动出现在这里
      </div>
      <div v-else class="vocab-list">
        <div v-for="item in filtered" :key="item.id" class="vocab-item" :class="{ due: item.is_due }">
          <div class="item-text">{{ item.source_text }}</div>
          <div v-if="item.translated_text" class="item-trans">{{ item.translated_text }}</div>
          <div class="item-meta">
            <span class="item-type">{{ item.item_type === 'word' ? '词' : '句' }}</span>
            <span class="item-due">{{ dueLabel(item.due) }}</span>
          </div>
          <div v-if="item.is_due" class="rate-buttons">
            <button class="rate again" @click="rateItem(item.id, 'again')">Again</button>
            <button class="rate hard" @click="rateItem(item.id, 'hard')">Hard</button>
            <button class="rate good" @click="rateItem(item.id, 'good')">Good</button>
            <button class="rate easy" @click="rateItem(item.id, 'easy')">Easy</button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  min-height: 320px;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.sidebar-title { font-size: 13px; font-weight: 600; color: var(--text-1); }
.due-badge {
  font-size: 11px;
  background: var(--accent);
  color: var(--text-inverse);
  padding: 1px 6px;
  border-radius: 10px;
}
.filter-bar {
  display: flex;
  gap: 4px;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
}
.chip {
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg);
  color: var(--text-2);
  cursor: pointer;
}
.chip.active {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}
.placeholder-text {
  font-size: 13px;
  color: var(--text-3);
  text-align: center;
  padding: var(--space-4);
}
.vocab-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.vocab-item {
  padding: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
}
.vocab-item.due {
  border-left: 3px solid var(--accent);
}
.item-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-1);
  margin-bottom: 2px;
}
.item-trans {
  font-size: 12px;
  color: var(--text-2);
  margin-bottom: 4px;
}
.item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-3);
}
.item-type {
  background: var(--bg-elevated);
  padding: 0 4px;
  border-radius: 2px;
}
.rate-buttons {
  display: flex;
  gap: 4px;
  margin-top: var(--space-1);
}
.rate {
  flex: 1;
  font-size: 11px;
  padding: 3px 0;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text-2);
  cursor: pointer;
}
.rate:hover { background: var(--bg-elevated); }
.rate.again:hover { color: #c6463a; border-color: #c6463a; }
.rate.hard:hover { color: #e67e22; border-color: #e67e22; }
.rate.good:hover { color: var(--accent); border-color: var(--accent); }
.rate.easy:hover { color: #2ecc71; border-color: #2ecc71; }
</style>
