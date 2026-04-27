<script setup>
/**
 * Memory · 次战场 (Phase 4 壳化)
 * 迁移自 static/memory.html · profile + facts + cards 三 Tab
 */
import { ref, onMounted } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetch, authFetchJson } = useAuthFetch()

const tab = ref('profile') // profile | facts | cards
const profile = ref(null)
const facts = ref([])
const cards = ref([])
const factsOffset = ref(0)
const factsTotal = ref(0)
const cardsLoading = ref(false)
const toast = ref('')

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

onMounted(async () => {
  await loadProfile()
  await loadFacts()
  await loadCards()
})
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
