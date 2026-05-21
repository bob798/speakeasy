<script setup>
/**
 * Memory · 次战场 (Phase 4 壳化)
 * 迁移自 static/memory.html · profile + facts + cards 三 Tab
 */
import { ref, onMounted } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetch, authFetchJson } = useAuthFetch()

const tab = ref('profile') // profile | facts | cards | vocab
const profile = ref(null)
const facts = ref([])
const cards = ref([])
const factsOffset = ref(0)
const factsTotal = ref(0)
const cardsLoading = ref(false)
const toast = ref('')

// ── V0.10 生词本 ─────────────────────────────────────────
const vocab = ref([])
const vocabFilter = ref('all') // all | word | phrase | sentence | due
const vocabLoading = ref(false)
const vocabExpandedId = ref(null)

const SOURCE_LABEL = {
  translate: '解读',
  article: '文章',
  practice: '练习',
  chat: '对话',
}
const SERIES_LABEL = {
  bbc_eaw: 'BBC',
  voa: 'VOA',
}

const TYPE_LABEL = { word: '词', phrase: '短语', sentence: '句' }

async function loadVocab() {
  vocabLoading.value = true
  try {
    const params = new URLSearchParams({ limit: '500' })
    if (vocabFilter.value === 'due') {
      params.set('due', 'true')
    } else if (vocabFilter.value !== 'all') {
      params.set('item_type', vocabFilter.value)
    }
    const resp = await authFetch(`${API.VOCAB}?${params.toString()}`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    vocab.value = data.items || []
  } catch (err) {
    toast.value = getErrorMessage(err)
  } finally {
    vocabLoading.value = false
  }
}

async function rateVocab(id, rating) {
  try {
    await authFetchJson(`${API.VOCAB}/${id}/rate`, { rating })
    toast.value = `已记录 · ${rating}`
    setTimeout(() => (toast.value = ''), 1200)
    // due 列表评完移除；其它列表更新 due 字段
    if (vocabFilter.value === 'due') {
      vocab.value = vocab.value.filter((v) => v.id !== id)
    } else {
      await loadVocab()
    }
  } catch (err) {
    toast.value = getErrorMessage(err, '评分失败')
  }
}

async function deleteVocab(id) {
  if (!confirm('确定删除？')) return
  try {
    const resp = await authFetch(`${API.VOCAB}/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('删除失败')
    vocab.value = vocab.value.filter((v) => v.id !== id)
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

function toggleExpand(id) {
  vocabExpandedId.value = vocabExpandedId.value === id ? null : id
}

function dueRelative(due) {
  if (!due) return ''
  const dt = new Date(due)
  const now = Date.now()
  const diff = dt.getTime() - now
  if (diff <= 0) return '到期'
  const days = Math.round(diff / 86400000)
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  if (days < 30) return `${days} 天后`
  return dt.toISOString().slice(0, 10)
}

async function loadProfile() {
  try {
    const resp = await authFetch(`${API.MEMORY}/profile`)
    if (!resp.ok) throw new Error('加载失败')
    profile.value = await resp.json()
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

async function saveProfile() {
  try {
    await authFetchJson(`${API.MEMORY}/profile`, profile.value, { method: 'PUT' })
    toast.value = '已保存'
    setTimeout(() => (toast.value = ''), 2000)
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

async function loadFacts(offset = 0) {
  try {
    const resp = await authFetch(`${API.MEMORY}/facts?limit=50&offset=${offset}`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    if (offset === 0) {
      facts.value = data.items || []
    } else {
      facts.value = [...facts.value, ...(data.items || [])]
    }
    factsOffset.value = facts.value.length
    factsTotal.value = data.total || 0
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

async function deleteFact(id) {
  try {
    const resp = await authFetch(`${API.MEMORY}/facts/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('删除失败')
    facts.value = facts.value.filter((f) => f.id !== id)
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

async function loadCards() {
  cardsLoading.value = true
  try {
    const resp = await authFetch(`${API.MEMORY}/cards`)
    if (!resp.ok) throw new Error('加载失败')
    const data = await resp.json()
    cards.value = data.cards || data.items || []
  } catch (err) {
    toast.value = getErrorMessage(err)
  } finally {
    cardsLoading.value = false
  }
}

async function deleteCard(id) {
  try {
    const resp = await authFetch(`${API.MEMORY}/cards/${id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('删除失败')
    cards.value = cards.value.filter((c) => c.id !== id)
  } catch (err) {
    toast.value = getErrorMessage(err)
  }
}

import { watch } from 'vue'

onMounted(async () => {
  await loadProfile()
  await loadFacts()
  await loadCards()
  await loadVocab()
})

watch(vocabFilter, () => loadVocab())
</script>

<template>
  <div class="memory-page">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">记忆管理</div>
      <span />
    </header>

    <nav class="tabs">
      <button :class="{ active: tab === 'profile' }" @click="tab = 'profile'">画像</button>
      <button :class="{ active: tab === 'facts' }" @click="tab = 'facts'">
        事实 ({{ facts.length }})
      </button>
      <button :class="{ active: tab === 'cards' }" @click="tab = 'cards'">
        语法卡 ({{ cards.length }})
      </button>
      <button :class="{ active: tab === 'vocab' }" @click="tab = 'vocab'">
        生词本 ({{ vocab.length }})
      </button>
    </nav>

    <main class="body">
      <!-- Profile Tab -->
      <section v-show="tab === 'profile'" v-if="profile" class="profile">
        <label>
          <span>CEFR 等级</span>
          <select v-model="profile.cefr_level">
            <option value="A1">A1 入门</option>
            <option value="A2">A2 初级</option>
            <option value="B1">B1 中级</option>
            <option value="B2">B2 中高</option>
            <option value="C1">C1 高级</option>
            <option value="C2">C2 精通</option>
          </select>
        </label>
        <label>
          <span>职业/身份</span>
          <input v-model="profile.occupation" placeholder="如：软件工程师" />
        </label>
        <label>
          <span>学习目标</span>
          <textarea v-model="profile.goal" rows="3"></textarea>
        </label>
        <label>
          <span>对话风格偏好</span>
          <textarea v-model="profile.style" rows="2" placeholder="如：口语化、直接、避免教条"></textarea>
        </label>
        <button class="primary" @click="saveProfile">保存画像</button>
      </section>
      <div v-else-if="tab === 'profile'" class="empty">画像加载中...</div>

      <!-- Facts Tab -->
      <section v-show="tab === 'facts'" class="facts">
        <ul v-if="facts.length">
          <li v-for="f in facts" :key="f.id" class="fact">
            <div class="fact-content">{{ f.content || f.text }}</div>
            <div class="fact-meta">
              <span>{{ f.created_at?.slice(0, 10) }}</span>
              <button class="del" @click="deleteFact(f.id)">×</button>
            </div>
          </li>
        </ul>
        <p v-else class="empty">暂无事实记忆</p>
        <button
          v-if="factsOffset < factsTotal"
          class="load-more"
          @click="loadFacts(factsOffset)"
        >
          加载更多（{{ factsOffset }}/{{ factsTotal }})
        </button>
      </section>

      <!-- Vocab Tab (V0.10) -->
      <section v-show="tab === 'vocab'" class="vocab">
        <div class="filter-bar">
          <button :class="{ on: vocabFilter === 'all' }" @click="vocabFilter = 'all'">全部</button>
          <button :class="{ on: vocabFilter === 'word' }" @click="vocabFilter = 'word'">词</button>
          <button :class="{ on: vocabFilter === 'phrase' }" @click="vocabFilter = 'phrase'">短语</button>
          <button :class="{ on: vocabFilter === 'sentence' }" @click="vocabFilter = 'sentence'">句</button>
          <button :class="{ on: vocabFilter === 'due' }" @click="vocabFilter = 'due'">今日复习</button>
        </div>
        <div v-if="vocabLoading" class="empty">加载中...</div>
        <ul v-else-if="vocab.length">
          <li v-for="v in vocab" :key="v.id" class="vocab-item" :class="{ expanded: vocabExpandedId === v.id }">
            <div class="v-head" @click="toggleExpand(v.id)">
              <span class="v-type">{{ TYPE_LABEL[v.item_type] || v.item_type }}</span>
              <span class="v-text">{{ v.source_text }}</span>
              <span class="v-due" :class="{ overdue: v.is_due }">{{ dueRelative(v.due) }}</span>
            </div>
            <div v-if="v.translated_text" class="v-translation">{{ v.translated_text }}</div>
            <div v-if="vocabExpandedId === v.id" class="v-detail">
              <div v-if="v.context" class="v-context">📍 {{ v.context }}</div>
              <div class="v-meta">
                <span class="v-source">来源：{{ v.series ? (SERIES_LABEL[v.series] || v.series) : (SOURCE_LABEL[v.source_type] || v.source_type) }}</span>
                <span v-if="v.created_at">{{ v.created_at.slice(0, 10) }}</span>
              </div>
              <div class="rate-row">
                <button class="rate again" @click="rateVocab(v.id, 'again')">Again</button>
                <button class="rate hard" @click="rateVocab(v.id, 'hard')">Hard</button>
                <button class="rate good" @click="rateVocab(v.id, 'good')">Good</button>
                <button class="rate easy" @click="rateVocab(v.id, 'easy')">Easy</button>
                <button class="del-btn" @click.stop="deleteVocab(v.id)">删除</button>
              </div>
            </div>
          </li>
        </ul>
        <p v-else class="empty">
          {{ vocabFilter === 'due' ? '今日没有待复习的条目 ✨' : '生词本还是空的，去解读页加 ⭐ 收藏吧' }}
        </p>
      </section>

      <!-- Cards Tab -->
      <section v-show="tab === 'cards'" class="cards">
        <div v-if="cardsLoading" class="empty">加载中...</div>
        <ul v-else-if="cards.length">
          <li v-for="c in cards" :key="c.id" class="card">
            <div class="card-head">
              <span class="type">{{ c.card_type || c.type || '语法' }}</span>
              <span class="state" :class="`state-${c.status || 'active'}`">{{ c.status || 'active' }}</span>
              <button class="del" @click="deleteCard(c.id)">×</button>
            </div>
            <div class="card-error">{{ c.error_text || c.text }}</div>
            <div v-if="c.correction" class="card-correction">→ {{ c.correction }}</div>
            <div v-if="c.explanation" class="card-note">{{ c.explanation }}</div>
          </li>
        </ul>
        <p v-else class="empty">暂无语法卡</p>
      </section>
    </main>

    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.memory-page {
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
  border-bottom: 1px solid var(--border);
}
.title {
  font-weight: 600;
  color: var(--accent);
}
.back {
  color: var(--text-2);
}
.tabs {
  display: flex;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border);
}
.tabs button {
  flex: 1;
  padding: var(--space-3);
  font-size: 13px;
  color: var(--text-2);
  border-bottom: 2px solid transparent;
}
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.body {
  padding: var(--space-4);
  max-width: 720px;
  margin: 0 auto;
}
.profile {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.profile label {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: 13px;
  color: var(--text-2);
}
input,
select,
textarea {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  font-size: 14px;
  outline: none;
}
input:focus,
select:focus,
textarea:focus {
  border-color: var(--accent);
}
textarea {
  resize: vertical;
  font-family: inherit;
}
.primary {
  padding: var(--space-3);
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-weight: 500;
  align-self: flex-start;
  min-width: 120px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.fact,
.card {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.fact {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: flex-start;
}
.fact-content {
  flex: 1;
  font-size: 14px;
  line-height: 1.5;
}
.fact-meta {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  font-size: 11px;
  color: var(--text-3);
  flex-shrink: 0;
}
.del {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 16px;
  color: var(--text-3);
}
.del:active {
  color: #c6463a;
}
.card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.type {
  padding: 2px 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  border-radius: 999px;
}
.state {
  font-size: 11px;
  color: var(--text-3);
}
.state-active {
  color: var(--accent);
}
.state-pending {
  color: #b07a1a;
}
.card-head .del {
  margin-left: auto;
}
.card-error {
  font-size: 14px;
  color: var(--text-1);
}
.card-correction {
  color: var(--accent);
  font-weight: 500;
  margin-top: 2px;
}
.card-note {
  font-size: 12px;
  color: var(--text-2);
  margin-top: var(--space-1);
}
.load-more {
  margin: var(--space-3) auto 0;
  padding: var(--space-2) var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-2);
  font-size: 13px;
  display: block;
}
.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-3);
}
.vocab .filter-bar {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.vocab .filter-bar button {
  padding: 4px 12px;
  font-size: 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-2);
}
.vocab .filter-bar button.on {
  background: var(--accent);
  color: var(--text-inverse);
  border-color: var(--accent);
}
.vocab-item {
  padding: var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
}
.vocab-item.expanded {
  border-color: var(--accent);
}
.v-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.v-type {
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  border-radius: 999px;
  flex-shrink: 0;
}
.v-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-1);
  word-break: break-word;
}
.v-due {
  font-size: 11px;
  color: var(--text-3);
  flex-shrink: 0;
}
.v-due.overdue {
  color: #c89b3c;
  font-weight: 500;
}
.v-translation {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-2);
  padding-left: 38px;
}
.v-detail {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.v-context {
  font-size: 12px;
  color: var(--text-2);
  font-style: italic;
}
.v-meta {
  display: flex;
  gap: var(--space-3);
  font-size: 11px;
  color: var(--text-3);
}
.rate-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.rate {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.rate.again { background: rgba(198, 70, 58, 0.12); color: #c6463a; }
.rate.hard  { background: rgba(176, 121, 26, 0.12); color: #b0791a; }
.rate.good  { background: var(--accent-soft); color: var(--accent); }
.rate.easy  { background: rgba(61, 107, 79, 0.18); color: var(--accent); }
.del-btn {
  margin-left: auto;
  padding: 6px 10px;
  font-size: 11px;
  color: var(--text-3);
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
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>
