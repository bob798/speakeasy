<script setup>
/**
 * HistorySidebar · 历史会话列表
 * 迁移自 static/index.html:1155-1210 · 分页加载 + 点击切换
 * Phase 2a: 加载 + 点击触发 emit · Phase 2b 接入 session 切换 + keep-alive
 */
import { ref, onMounted } from 'vue'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API, CHAT } from '@/config'

const emit = defineEmits(['select', 'new-chat', 'close'])

const { authFetch } = useAuthFetch()
const sessions = ref([])
const loading = ref(false)
const activeId = defineModel('activeId', { type: String, default: '' })

let _offset = 0
let _total = 0

async function loadFirstPage() {
  loading.value = true
  _offset = 0
  try {
    const resp = await authFetch(`${API.HISTORY}?limit=${CHAT.HISTORY_PAGE_SIZE}&offset=0`)
    if (!resp.ok) throw new Error('加载历史失败')
    const data = await resp.json()
    sessions.value = data.sessions || []
    _offset = sessions.value.length
    _total = data.total || 0
  } catch {
    // 静默失败（未登录时 useAuthFetch 已跳转，不会到这里）
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loading.value || _offset >= _total) return
  loading.value = true
  try {
    const resp = await authFetch(
      `${API.HISTORY}?limit=${CHAT.HISTORY_PAGE_SIZE}&offset=${_offset}`
    )
    if (!resp.ok) return
    const data = await resp.json()
    sessions.value = [...sessions.value, ...(data.sessions || [])]
    _offset = sessions.value.length
    _total = data.total || 0
  } finally {
    loading.value = false
  }
}

function onScroll(e) {
  const el = e.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
    loadMore()
  }
}

function onSelect(sid) {
  activeId.value = sid
  emit('select', sid)
}

onMounted(loadFirstPage)

defineExpose({ refresh: loadFirstPage })
</script>

<template>
  <aside class="sidebar" @scroll="onScroll">
    <header class="top">
      <h3>历史</h3>
      <button class="close" @click="emit('close')" aria-label="关闭">×</button>
    </header>
    <button class="new-chat" @click="emit('new-chat')">
      <span>+</span>
      <span>新对话</span>
    </button>
    <ul class="list">
      <li
        v-for="s in sessions"
        :key="s.session_id"
        class="item"
        :class="{ active: s.session_id === activeId }"
        :data-sid="s.session_id"
        @click="onSelect(s.session_id)"
      >
        <div class="preview">{{ s.first_user_message || '(空会话)' }}</div>
        <div class="meta">
          <span>{{ s.turns || 0 }} 轮</span>
          <span>{{ formatTime(s.updated_at) }}</span>
        </div>
      </li>
      <li v-if="loading" class="loading-row">加载中...</li>
      <li v-else-if="sessions.length === 0" class="empty">暂无历史</li>
    </ul>
  </aside>
</template>

<script>
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffDay = Math.floor((now - d) / 86400000)
  if (diffDay === 0) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (diffDay === 1) return '昨天'
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  max-width: 85vw;
  height: 100%;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding-top: var(--safe-top);
}
.top {
  padding: var(--space-4);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg-elevated);
}
.top h3 {
  margin: 0;
  font-size: 14px;
  color: var(--text-2);
  font-weight: 600;
}
.close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 20px;
  color: var(--text-3);
}
.close:active {
  background: var(--bg);
}
.new-chat {
  margin: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--accent);
  font-weight: 500;
}
.new-chat:active {
  background: var(--accent-soft);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0 var(--space-2) var(--space-4);
}
.item {
  padding: var(--space-3);
  border-radius: var(--radius);
  cursor: pointer;
  margin-bottom: var(--space-1);
  transition: background var(--duration) var(--ease);
}
.item:active,
.item.active {
  background: var(--accent-soft);
}
.preview {
  font-size: 14px;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 4px;
}
.meta {
  display: flex;
  gap: var(--space-3);
  font-size: 11px;
  color: var(--text-3);
}
.loading-row,
.empty {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}
</style>
