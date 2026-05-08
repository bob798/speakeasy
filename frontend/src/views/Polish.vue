<script setup>
/**
 * Polish · 写作教练 · V0.11 P0
 *
 * 流程：
 *   粘贴英文 → POST /polish/text → 显示 polished + 逐处 diff + 解释
 *   ↓
 *   多轮 chat（更口语 / 更正式 / 更简洁）→ POST /polish/chat
 *   ↓
 *   收藏当前 segment 为 polish_card（POST /polish/cards）
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'
import AskPanel from '@/components/AskPanel.vue'

const { authFetch, authFetchJson } = useAuthFetch()

const original = ref('')
const polished = ref('')
const segments = ref([])
const overallNote = ref('')
const polishing = ref(false)
const polishError = ref('')

// chat 多轮
const chatHistory = ref([])  // [{role: 'user'|'assistant', content}]
const chatInput = ref('')
const chatBusy = ref(false)
const chatSummary = ref('')

// 收藏状态：每个 segment 一个 saving/saved 标记
const savingMap = ref({})        // idx → 'saving' | 'saved'
const cards = ref([])            // 已保存列表

const askOpen = ref(false)
const toast = ref('')

const hasResult = computed(() => !!polished.value)
const refId = computed(() => `polish:${(original.value || '').slice(0, 60)}`)

const QUICK_INSTRUCTIONS = [
  { label: '更口语', value: '改得更口语化、更自然' },
  { label: '更正式', value: '改得更正式、更书面' },
  { label: '更简洁', value: '在不丢信息的前提下更简洁' },
  { label: '更有力', value: '语气更有力、更主动' },
]

const CATEGORY_LABEL = {
  grammar: '语法',
  word_choice: '用词',
  style: '风格',
  structure: '结构',
}

function showToast(msg, ms = 1600) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), ms)
}

async function doPolish() {
  if (!original.value.trim()) {
    polishError.value = '请先粘贴英文文本'
    return
  }
  polishing.value = true
  polishError.value = ''
  segments.value = []
  polished.value = ''
  chatHistory.value = []
  chatSummary.value = ''
  savingMap.value = {}
  try {
    const resp = await authFetchJson(`${API.POLISH}/text`, { text: original.value })
    polished.value = resp.polished || original.value
    segments.value = resp.segments || []
    overallNote.value = resp.overall_note || ''
  } catch (err) {
    polishError.value = getErrorMessage(err, '润色失败')
  } finally {
    polishing.value = false
  }
}

async function applyQuickInstruction(text) {
  chatInput.value = text
  await sendChat()
}

async function sendChat() {
  const instr = chatInput.value.trim()
  if (!instr || chatBusy.value) return
  chatBusy.value = true
  chatHistory.value.push({ role: 'user', content: instr })
  chatInput.value = ''
  try {
    const resp = await authFetchJson(`${API.POLISH}/chat`, {
      original: original.value,
      current_polished: polished.value,
      instruction: instr,
      history: chatHistory.value.slice(0, -1),
    })
    polished.value = resp.polished || polished.value
    chatSummary.value = resp.summary || ''
    chatHistory.value.push({
      role: 'assistant',
      content: resp.summary || '已更新',
    })
  } catch (err) {
    showToast(getErrorMessage(err, 'chat 失败'))
    // 回滚 user 消息以免 UI 错位
    chatHistory.value.pop()
  } finally {
    chatBusy.value = false
  }
}

async function saveSegment(idx) {
  const seg = segments.value[idx]
  if (!seg) return
  savingMap.value[idx] = 'saving'
  try {
    const card = await authFetchJson(`${API.POLISH}/cards`, {
      original: seg.original,
      polished: seg.replacement,
      explanation: seg.explanation || '',
      context: original.value,
      category: seg.category || '',
    })
    cards.value.unshift(card)
    savingMap.value[idx] = 'saved'
    showToast('已加入写作卡片')
  } catch (err) {
    delete savingMap.value[idx]
    showToast(getErrorMessage(err, '收藏失败'))
  }
}

async function saveWhole() {
  if (!polished.value || polished.value === original.value) {
    showToast('整体没改动，无需保存')
    return
  }
  try {
    const card = await authFetchJson(`${API.POLISH}/cards`, {
      original: original.value,
      polished: polished.value,
      explanation: overallNote.value || chatSummary.value || '',
      context: '',
      category: '',
    })
    cards.value.unshift(card)
    showToast('已保存整体对比')
  } catch (err) {
    showToast(getErrorMessage(err, '收藏失败'))
  }
}

async function loadCards() {
  try {
    const resp = await authFetch(`${API.POLISH}/cards?limit=50`)
    if (resp.ok) {
      cards.value = (await resp.json()).items || []
    }
  } catch {
    /* ignore */
  }
}

async function deleteCard(id) {
  try {
    const resp = await authFetch(`${API.POLISH}/cards/${id}`, { method: 'DELETE' })
    if (resp.ok) {
      cards.value = cards.value.filter((c) => c.id !== id)
    }
  } catch (err) {
    showToast(getErrorMessage(err, '删除失败'))
  }
}

function reset() {
  original.value = ''
  polished.value = ''
  segments.value = []
  overallNote.value = ''
  chatHistory.value = []
  chatSummary.value = ''
  savingMap.value = {}
  polishError.value = ''
}

onMounted(loadCards)
</script>

<template>
  <div class="polish-page">
    <header class="topbar">
      <RouterLink class="back" to="/">← 返回</RouterLink>
      <div class="title">写作教练</div>
      <button v-if="hasResult" class="reset-btn" @click="reset">重新开始</button>
      <span v-else />
    </header>

    <main class="body">
      <!-- ── 输入区 ── -->
      <section class="input-block">
        <textarea
          v-model="original"
          placeholder="粘贴或输入你写的英文（最多 2000 字）..."
          rows="6"
          :disabled="polishing"
        />
        <div class="input-foot">
          <span class="char-count" :class="{ over: original.length > 2000 }">
            {{ original.length }} / 2000
          </span>
          <button class="primary" :disabled="polishing || !original.trim()" @click="doPolish">
            {{ polishing ? '润色中…' : (hasResult ? '重新润色' : '开始润色') }}
          </button>
        </div>
        <p v-if="polishError" class="err">{{ polishError }}</p>
      </section>

      <!-- ── 结果区 ── -->
      <section v-if="hasResult" class="result-block">
        <div class="block-head">
          <h3>润色结果</h3>
          <button class="link-btn" @click="saveWhole">⭐ 保存整体对比</button>
        </div>

        <div class="polished-text">{{ polished }}</div>

        <p v-if="overallNote" class="overall-note">💬 {{ overallNote }}</p>

        <!-- 逐处 diff -->
        <div v-if="segments.length" class="segments">
          <h4>逐处变更 · {{ segments.length }} 项</h4>
          <ul>
            <li v-for="(s, i) in segments" :key="i" class="seg-item">
              <div class="seg-head">
                <span v-if="s.category" class="cat-tag">{{ CATEGORY_LABEL[s.category] || s.category }}</span>
                <button
                  class="seg-save"
                  :class="{ saved: savingMap[i] === 'saved', saving: savingMap[i] === 'saving' }"
                  :disabled="savingMap[i] === 'saving' || savingMap[i] === 'saved'"
                  @click="saveSegment(i)"
                >
                  {{ savingMap[i] === 'saved' ? '★ 已存' : (savingMap[i] === 'saving' ? '⏳' : '☆ 收藏') }}
                </button>
              </div>
              <div class="seg-diff">
                <span class="seg-from">{{ s.original }}</span>
                <span class="seg-arrow">→</span>
                <span class="seg-to">{{ s.replacement }}</span>
              </div>
              <p v-if="s.explanation" class="seg-expl">{{ s.explanation }}</p>
            </li>
          </ul>
        </div>
        <p v-else class="no-changes">✨ 这段已经写得不错，没什么需要改的。</p>

        <!-- ── Chat 多轮 ── -->
        <div class="chat-block">
          <h4>继续优化</h4>
          <div class="quick-row">
            <button
              v-for="q in QUICK_INSTRUCTIONS"
              :key="q.label"
              class="quick"
              :disabled="chatBusy"
              @click="applyQuickInstruction(q.value)"
            >{{ q.label }}</button>
          </div>
          <ul v-if="chatHistory.length" class="chat-log">
            <li v-for="(m, i) in chatHistory" :key="i" :class="['msg', m.role]">
              <span class="role">{{ m.role === 'user' ? '你' : 'Coach' }}</span>
              <span class="content">{{ m.content }}</span>
            </li>
          </ul>
          <div class="chat-input-row">
            <input
              v-model="chatInput"
              placeholder="给 Coach 一句指令，如「更简洁」"
              :disabled="chatBusy"
              @keydown.enter.prevent="sendChat"
            />
            <button class="primary" :disabled="chatBusy || !chatInput.trim()" @click="sendChat">
              {{ chatBusy ? '…' : '发送' }}
            </button>
          </div>
        </div>

        <!-- Ask 追问入口 -->
        <div class="ask-row">
          <button class="link-btn" @click="askOpen = !askOpen">
            {{ askOpen ? '收起追问 ↑' : '有疑惑就问 Alex →' }}
          </button>
        </div>
        <div v-if="askOpen" class="ask-host">
          <AskPanel
            scope="polish"
            ref-type="polish"
            :ref-id="refId"
            :context-payload="{
              original: original,
              polished: polished,
              segments: segments,
            }"
            placeholder="问问 Coach 这段为什么这么改..."
            empty-hint="对哪一处不理解？"
          />
        </div>
      </section>

      <!-- ── 已保存卡片 ── -->
      <section v-if="cards.length" class="cards-block">
        <h3>我的写作卡片 · {{ cards.length }}</h3>
        <ul>
          <li v-for="c in cards" :key="c.id" class="card-item">
            <div class="card-head">
              <span v-if="c.category" class="cat-tag">{{ CATEGORY_LABEL[c.category] || c.category }}</span>
              <span class="card-date">{{ (c.created_at || '').slice(0, 10) }}</span>
              <button class="card-del" @click="deleteCard(c.id)">×</button>
            </div>
            <div class="seg-diff">
              <span class="seg-from">{{ c.original }}</span>
              <span class="seg-arrow">→</span>
              <span class="seg-to">{{ c.polished }}</span>
            </div>
            <p v-if="c.explanation" class="seg-expl">{{ c.explanation }}</p>
          </li>
        </ul>
      </section>
    </main>

    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.polish-page {
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
.back { color: var(--text-2); }
.title { font-weight: 600; color: var(--accent); }
.reset-btn {
  font-size: 12px;
  color: var(--text-3);
  padding: 4px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 999px;
}

.body {
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.input-block textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
}
.input-block textarea:focus {
  outline: none;
  border-color: var(--accent);
}
.input-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-2);
  gap: var(--space-3);
}
.char-count {
  font-size: 12px;
  color: var(--text-3);
}
.char-count.over { color: #c6463a; }
.primary {
  padding: 8px 18px;
  background: var(--accent);
  color: var(--text-inverse);
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
}
.primary:disabled { opacity: 0.5; }

.err {
  margin-top: var(--space-2);
  color: #c6463a;
  font-size: 13px;
}

.result-block,
.cards-block {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-4);
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.block-head h3,
.cards-block h3 {
  margin: 0;
  font-size: 14px;
  color: var(--accent);
}
.link-btn {
  font-size: 12px;
  color: var(--accent);
  background: transparent;
}

.polished-text {
  padding: var(--space-3);
  background: var(--bg);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  font-size: 15px;
  line-height: 1.65;
  color: var(--text-1);
  word-break: break-word;
}
.overall-note {
  margin: var(--space-3) 0 0;
  font-size: 13px;
  color: var(--text-2);
}

.segments {
  margin-top: var(--space-4);
}
.segments h4,
.chat-block h4 {
  margin: 0 0 var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.segments ul,
.chat-log,
.cards-block ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.seg-item,
.card-item {
  padding: var(--space-3);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.seg-head,
.card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}
.cat-tag {
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  border-radius: 999px;
  flex-shrink: 0;
}
.seg-save {
  margin-left: auto;
  font-size: 12px;
  padding: 2px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-2);
}
.seg-save.saved { color: #c89b3c; border-color: #c89b3c; }
.seg-save.saving { opacity: 0.6; }
.card-date {
  font-size: 11px;
  color: var(--text-3);
}
.card-del {
  margin-left: auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 14px;
  color: var(--text-3);
}
.card-del:active { color: #c6463a; }

.seg-diff {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: 14px;
  line-height: 1.5;
  margin: 4px 0;
}
.seg-from {
  text-decoration: line-through;
  color: #c6463a;
  background: rgba(198, 70, 58, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
}
.seg-to {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.seg-arrow { color: var(--text-3); }
.seg-expl {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.5;
}

.no-changes {
  margin: var(--space-4) 0 0;
  text-align: center;
  color: var(--text-2);
  font-size: 14px;
}

/* Chat */
.chat-block {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px dashed var(--border);
}
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-3);
}
.quick {
  padding: 4px 12px;
  font-size: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-2);
}
.quick:active {
  background: var(--accent);
  color: var(--text-inverse);
}
.quick:disabled { opacity: 0.5; }
.chat-log {
  margin-bottom: var(--space-3);
  max-height: 200px;
  overflow-y: auto;
}
.msg {
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  gap: var(--space-2);
  align-items: baseline;
}
.msg .role {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-3);
  width: 38px;
  text-align: right;
}
.msg.user .content { color: var(--text-1); }
.msg.assistant .content { color: var(--accent); }
.chat-input-row {
  display: flex;
  gap: var(--space-2);
}
.chat-input-row input {
  flex: 1;
  padding: 8px var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-size: 14px;
}
.chat-input-row input:focus {
  outline: none;
  border-color: var(--accent);
}

.ask-row {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border);
  text-align: center;
}
.ask-host {
  margin-top: var(--space-3);
  border-top: 1px solid var(--border);
  padding-top: var(--space-3);
}
.ask-host > :deep(.ap-root) {
  width: 100%;
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
  z-index: 100;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--duration) var(--ease);
}
.toast-enter-from,
.toast-leave-to { opacity: 0; }
</style>
