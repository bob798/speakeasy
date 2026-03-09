/**
 * app.js — 主应用逻辑
 *
 * CEO 决策落地：
 *   1. Alex 主动发开场白，消解空白焦虑
 *   2. 语音识别完成 → 自动发送（不经过输入框）
 *   3. 状态指示线替代 Banner
 *   4. 空状态引导
 *
 * CTO 决策落地：
 *   1. STT 三层架构（VAD + 倒计时 + 兜底）
 *   2. TTS 自动朗读队列
 *   3. 流式输出 SSE
 *   4. 全路径降级
 */

const userId    = getUserId();
let sessionId   = getSessionId();
let autoPlay    = false;
let sttProvider   = null;
let sttState      = 'idle';  // idle | recording | processing
let sttGeneration = 0;       // 代际计数，用于作废旧回调
let chatHistory   = [];
let _chatSnapshot = null;    // 当前会话 DOM 快照（切换到历史视图时暂存）

// 历史列表分页状态
const HISTORY_PAGE = 20;
let _historyOffset  = 0;
let _historyTotal   = 0;
let _historyLoading = false;

// 触底加载更多（IntersectionObserver）
const _historyObserver = new IntersectionObserver(entries => {
  if (entries[0].isIntersecting) _loadMoreHistory();
}, { threshold: 0.1 });

const ttsQueue  = new TTSQueue(createTTSProvider());

// ── 启动 ────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  setupAutoplayToggle();
  showEmptyState();
  await initSTT();
  await loadHistory();
  alexOpeningMessage();
});

// ── Alex 开场白 ──────────────────────────────────────────────────────────
function alexOpeningMessage() {
  // 只在全新 session（没有对话历史）时出现
  if (chatHistory.length > 0) return;

  const opening = "Hey! I'm Alex 👋 What's on your mind today? You can type or tap the mic to speak.";
  const id = appendBubble('ai', '');
  let i = 0;

  // 打字机效果展示开场白
  const typeInterval = setInterval(() => {
    i++;
    updateBubble(id, opening.slice(0, i), i < opening.length);
    if (i >= opening.length) {
      clearInterval(typeInterval);
      updateBubble(id, opening, false);
      attachTTSBtn(id, opening);
      if (autoPlay) ttsQueue.enqueue(opening);
      // 不加入 chatHistory，开场白不作为上下文
      // 在 Alex 消息下方重新展示话题卡片
      const chat = document.getElementById('chat');
      if (!chat) return;   // 新对话已触发，chat 已被替换，直接退出
      const topics = getRandomTopics(3);
      const cardsHtml = topics.map(t =>
        `<button class="topic-card" onclick="onTopicClick(${JSON.stringify(t.prompt).replace(/"/g, '&quot;')})">
          <span class="topic-emoji">${t.emoji}</span>
          <span>${t.label}</span>
        </button>`
      ).join('');
      const cardsDiv = document.createElement('div');
      cardsDiv.className = 'topic-cards';
      cardsDiv.innerHTML = cardsHtml;
      chat.appendChild(cardsDiv);
      scrollChat();
    }
  }, 22);
}

// ── STT 初始化 ───────────────────────────────────────────────────────────
async function initSTT() {
  const server = createSTTProvider();

  // 检查录音基础支持
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatusLine('degraded', '浏览器不支持录音，请使用 Chrome / Edge');
    hideMicBtn();
    return;
  }

  if (!server.isSupported()) {
    setStatusLine('degraded', '录音需要 HTTPS 环境（本地开发请用 localhost 或 127.0.0.1）');
    hideMicBtn();
    return;
  }

  // 检查后端 STT 配置
  try {
    const status = await fetch(CONFIG.DEBUG).then(r => r.json());

    if (!status.stt_available) {
      const ws = new WebSpeechSTTProvider();
      if (ws.isSupported()) {
        // 降级到 WebSpeech，状态线变黄，hover 提示原因
        setStatusLine('degraded', '语音识别使用浏览器内置方案（Chrome 限定），设置 GROQ_API_KEY 可升级');
        sttProvider = ws;
      } else {
        setStatusLine('degraded', '语音功能不可用：未配置 GROQ_API_KEY 且浏览器不支持 WebSpeech');
        hideMicBtn();
      }
    } else {
      setStatusLine('ok');
      sttProvider = server;
    }
  } catch (e) {
    // 后端未启动或网络问题
    setStatusLine('error', '无法连接到服务器');
    sttProvider = server; // 仍然允许尝试，让用户发现问题
  }
}

// ── 自动朗读开关 ─────────────────────────────────────────────────────────
function setupAutoplayToggle() {
  const btn = document.getElementById('autoplay-btn');
  btn.addEventListener('click', () => {
    autoPlay = !autoPlay;
    btn.setAttribute('aria-checked', String(autoPlay));
    if (!autoPlay) ttsQueue.clear();
  });
}

// ── 发送消息（核心流程）─────────────────────────────────────────────────
async function sendMessage(text) {
  if (!text?.trim()) return;

  // 重置输入框
  clearInput();
  document.getElementById('input-box').style.height = 'auto';
  setInputPlaceholder('');

  // 渲染用户气泡
  appendBubble('user', text);
  chatHistory.push({ role: 'user', content: text });

  // 第一条消息时更新侧边栏当前对话预览
  if (chatHistory.filter(m => m.role === 'user').length === 1) {
    updateCurrentPreview(text);
  }

  // 创建 AI 气泡（loading dots）
  const bubbleId = appendBubble('ai', '', false);

  try {
    const res = await fetch(CONFIG.CHAT_STREAM, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id:    userId,
        session_id: sessionId,
        message:    text,
        history:    chatHistory.slice(-10),  // 最近 10 轮上下文
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let buf  = '';
    let full = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buf += dec.decode(value, { stream: true });
      const parts = buf.split('\n\n');
      buf = parts.pop(); // 保留不完整的最后一段

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        let d;
        try { d = JSON.parse(part.slice(6)); } catch { continue; }

        if (d.type === 'delta') {
          full += d.content;
          updateBubble(bubbleId, full, true);

        } else if (d.type === 'done') {
          updateBubble(bubbleId, full, false);
          attachTTSBtn(bubbleId, full);
          chatHistory.push({ role: 'assistant', content: full });
          _roundCount++;
          updateRoundCount(_roundCount);
          if (autoPlay) ttsQueue.enqueue(full);
          // 延迟刷新历史列表（等后端写入完成）
          setTimeout(loadHistory, 800);

        } else if (d.type === 'error') {
          removeBubble(bubbleId);
          showToast(d.message || 'AI 回复失败，请重试', 'error');
        }
      }
    }

  } catch (e) {
    removeBubble(bubbleId);
    showToast('网络错误，请检查连接后重试', 'error');
    console.error('[sendMessage]', e);
  }
}

// ── 录音状态机 ───────────────────────────────────────────────────────────
function onMicClick() {
  if (!sttProvider) {
    showToast('语音功能不可用，请检查浏览器权限', 'error');
    return;
  }

  if (sttState === 'idle') {
    // 开始录音：记录当前代际，回调过期则忽略
    sttState = 'recording';
    setMicState('recording');
    const gen = ++sttGeneration;

    sttProvider.start(
      // onInterim: 实时显示识别中的文字
      (interim) => {
        if (sttGeneration !== gen) return;
        updateInterim(interim, true);
      },

      // onFinal: 识别完成 → 直接发送（不经过输入框）
      (text) => {
        if (sttGeneration !== gen) return;
        sttState = 'idle';
        setMicState('idle');
        updateInterim('', false);
        sendMessage(text);
      },

      // onError: 分类处理
      (err) => {
        if (sttGeneration !== gen) return;
        sttState = 'idle';
        setMicState('idle');
        updateInterim('', false);

        if (err.type === 'PERMISSION_DENIED') {
          showToast('请在浏览器地址栏允许麦克风权限', 'error');
        } else if (err.type === 'FALLBACK') {
          // 后端不可用，自动切换到 WebSpeech
          sttProvider = new WebSpeechSTTProvider();
          if (sttProvider.isSupported()) {
            setStatusLine('degraded', '已切换到浏览器内置识别（Chrome 限定）');
            showToast('已切换到浏览器内置识别', 'info');
          } else {
            hideMicBtn();
            showToast('语音识别不可用', 'error');
          }
        } else if (err.type === 'EMPTY') {
          showToast('没有检测到语音，请重试', 'info');
        } else {
          showToast('识别失败，请重试', 'error');
          console.error('[STT error]', err);
        }
      }
    );

  } else if (sttState === 'recording') {
    // 用户主动停止（L1 控制）
    sttState = 'processing';
    setMicState('processing');
    sttProvider.stop();

    // 安全兜底：10 秒后若仍未完成，强制重置，防止永久转圈
    const safeGen = sttGeneration;
    setTimeout(() => {
      if (sttState === 'processing' && sttGeneration === safeGen) {
        ++sttGeneration;
        sttState = 'idle';
        setMicState('idle');
        showToast('识别超时，请重试', 'info');
      }
    }, 10000);

  } else if (sttState === 'processing') {
    // 处理中再次点击 → 立即取消并作废旧回调，恢复按钮
    ++sttGeneration;
    sttProvider.cancel?.();
    sttState = 'idle';
    setMicState('idle');
  }
}

// ── 文字发送 ────────────────────────────────────────────────────────────
function onSend() {
  const text = getInput().trim();
  if (text) sendMessage(text);
}

// ── 新对话 ──────────────────────────────────────────────────────────────
function onNewChat() {
  // 取消正在录音的状态，并作废旧回调
  ++sttGeneration;
  if (sttState !== 'idle' && sttProvider) {
    sttProvider.cancel();
    sttState = 'idle';
    setMicState('idle');
  }
  ttsQueue.clear();

  _chatSnapshot = null;   // 丢弃旧会话快照
  sessionId   = newSession();
  chatHistory = [];
  _roundCount = 0;
  updateRoundCount(0);
  clearChatArea();
  setMode('chat');
  document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
  setCurrentSessionActive(true);
  updateCurrentPreview('');

  // Alex 重新发开场白
  setTimeout(alexOpeningMessage, 300);
}

// ── 从历史视图返回当前会话 ────────────────────────────────────────────────
function returnToCurrentSession() {
  const chat = document.getElementById('chat');
  chat.innerHTML = '';

  if (_chatSnapshot) {
    // 把暂存的 DOM 节点移回聊天区（事件绑定完整保留）
    chat.appendChild(_chatSnapshot);
    _chatSnapshot = null;
  } else {
    // 快照不存在（如刷新后直接查看历史），显示空态
    showEmptyState();
  }

  // 恢复轮次计数
  _roundCount = chatHistory.filter(m => m.role === 'assistant').length;
  updateRoundCount(_roundCount);

  setMode('chat');
  document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
  setCurrentSessionActive(true);
  scrollChat();
}

// ── 历史面板 ────────────────────────────────────────────────────────────
async function loadHistory() {
  _historyOffset  = 0;
  _historyTotal   = 0;
  _historyLoading = false;
  try {
    const data = await fetch(`${CONFIG.HISTORY}/${userId}?limit=${HISTORY_PAGE}&offset=0`).then(r => r.json());
    _historyOffset = data.sessions?.length || 0;
    _historyTotal  = data.total || 0;
    renderHistoryList(data.sessions || [], false);
  } catch (e) {
    // 静默失败
  }
}

async function _loadMoreHistory() {
  if (_historyLoading || _historyOffset >= _historyTotal) return;
  _historyLoading = true;
  try {
    const data = await fetch(`${CONFIG.HISTORY}/${userId}?limit=${HISTORY_PAGE}&offset=${_historyOffset}`).then(r => r.json());
    const sessions = data.sessions || [];
    _historyOffset += sessions.length;
    _historyTotal   = data.total || 0;
    renderHistoryList(sessions, true);
  } catch (e) {
    // 静默失败
  } finally {
    _historyLoading = false;
  }
}

async function onHistoryClick(sid) {
  // 高亮选中
  document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
  document.querySelector(`[data-sid="${sid}"]`)?.classList.add('active');

  // 第一次切换到历史视图时，把当前会话 DOM 移入 DocumentFragment 暂存
  if (!_chatSnapshot) {
    const chat = document.getElementById('chat');
    _chatSnapshot = document.createDocumentFragment();
    while (chat.firstChild) _chatSnapshot.appendChild(chat.firstChild);
    setCurrentSessionActive(false);
  }

  try {
    const data = await fetch(`${CONFIG.HISTORY}/${sid}/messages`).then(r => r.json());
    renderReadonlyChat(data.messages, sid);

    // 顶部「回到当前对话」按钮
    const badge = document.getElementById('chat').querySelector('.readonly-badge');
    if (badge) {
      badge.innerHTML = `📖 历史记录 &nbsp;·&nbsp;
        <button onclick="returnToCurrentSession()" style="color:var(--accent);background:none;border:none;cursor:pointer;font-size:11px;font-family:inherit">
          ← 回到当前对话
        </button>`;
    }
  } catch (e) {
    showToast('加载历史失败', 'error');
  }
}
