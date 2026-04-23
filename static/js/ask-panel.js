// ── Speakeasy AskPanel ─────────────────────────────────────
// 可复用的"针对某段上下文的多轮追问"前端组件。
//
// 用法（注意：需要 window.authFetch 已加载）：
//   const panel = window.AskPanel.create({
//     mount:         HTMLElement,          // 挂载容器（组件会清空该容器）
//     scope:         'practice_explain',    // 对应后端 SCOPE_PROMPTS
//     refType:       'explanation',         // 业务侧引用类型
//     refId:         'abc123',              // 业务侧稳定 ID
//     contextPayload: { ... },              // 首轮 system prompt 用的上下文
//     placeholder:   '问点什么…',
//     emptyHint:     '还没有追问，先问一个吧',
//     onError(msg):  optional,
//   });
//   panel.loadExisting();     // 尝试加载同 refId 已有 thread
//   panel.destroy();          // 关闭抽屉时调用
//
// 样式通过全局 CSS 变量；若页面缺少变量，组件内置兜底色。
(function () {
  if (window.AskPanel) return; // 已加载

  const NAMESPACE = 'ask-panel';
  const STYLE_ID  = `${NAMESPACE}-style`;

  const CSS = `
.ap-root { display:flex; flex-direction:column; height:100%; min-height:0; background:var(--elevated, #fff); }
.ap-messages { flex:1; overflow-y:auto; padding:10px 14px; display:flex; flex-direction:column; gap:10px; }
.ap-empty { color:var(--text-3, #b5aa9a); font-size:12px; text-align:center; padding:18px 6px; }
.ap-msg { display:flex; flex-direction:column; max-width:92%; word-wrap:break-word; }
.ap-msg.user { align-self:flex-end; }
.ap-msg.assistant { align-self:flex-start; }
.ap-bubble { padding:8px 12px; border-radius:10px; font-size:13px; line-height:1.55; white-space:pre-wrap; }
.ap-msg.user .ap-bubble { background:var(--accent-dim, rgba(61,107,79,0.12)); color:var(--text-1, #2c2820); border-bottom-right-radius:3px; }
.ap-msg.assistant .ap-bubble { background:var(--overlay, #f0ede6); color:var(--text-1, #2c2820); border-bottom-left-radius:3px; }
.ap-msg .ap-role { font-size:10px; color:var(--text-3, #b5aa9a); margin-bottom:2px; letter-spacing:0.5px; }
.ap-msg.user .ap-role { text-align:right; }
.ap-pending { opacity:0.6; font-style:italic; }
.ap-error { color:#b0403a; background:rgba(176,64,58,0.1); padding:8px 10px; border-radius:6px; font-size:12px; }
.ap-inputbar { display:flex; gap:8px; padding:10px 12px; border-top:1px solid var(--border, #e4ddcf); background:var(--elevated, #fff); }
.ap-input { flex:1; border:1px solid var(--border, #e4ddcf); border-radius:8px; padding:8px 10px; font-size:13px; font-family:inherit; background:var(--bg, #fbf8f2); color:var(--text-1, #2c2820); resize:none; min-height:36px; max-height:100px; }
.ap-input:focus { outline:none; border-color:var(--accent, #3d6b4f); }
.ap-send { padding:0 14px; border-radius:8px; border:none; background:var(--accent, #3d6b4f); color:#fff; font-size:13px; font-weight:500; cursor:pointer; transition:opacity 0.15s; }
.ap-send:disabled { opacity:0.4; cursor:not-allowed; }
.ap-send:hover:not(:disabled) { background:var(--accent-light, #4e8963); }
`;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderMessage({ role, content, pending = false }) {
    const wrap = document.createElement('div');
    wrap.className = `ap-msg ${role}`;
    const roleEl = document.createElement('div');
    roleEl.className = 'ap-role';
    roleEl.textContent = role === 'user' ? 'You' : 'Tutor';
    const bubble = document.createElement('div');
    bubble.className = 'ap-bubble' + (pending ? ' ap-pending' : '');
    bubble.textContent = content;
    wrap.appendChild(roleEl);
    wrap.appendChild(bubble);
    return wrap;
  }

  function renderError(msg) {
    const el = document.createElement('div');
    el.className = 'ap-error';
    el.textContent = '❌ ' + msg;
    return el;
  }

  function create(opts) {
    ensureStyle();
    const {
      mount,
      scope,
      refType,
      refId,
      contextPayload = {},
      placeholder = '问点什么…',
      emptyHint = '还没有追问，先问一个吧',
      onError = null,
    } = opts || {};
    if (!mount) throw new Error('AskPanel: mount 必填');
    if (!scope || !refType || !refId) throw new Error('AskPanel: scope/refType/refId 必填');
    if (!window.authFetch) throw new Error('AskPanel: 需要 window.authFetch');

    // ── State ────────────────────────────────────────────
    let threadId = null;
    let busy = false;
    let destroyed = false;

    // ── DOM ──────────────────────────────────────────────
    mount.innerHTML = '';
    const root = document.createElement('div');
    root.className = 'ap-root';
    const msgsEl = document.createElement('div');
    msgsEl.className = 'ap-messages';
    const emptyEl = document.createElement('div');
    emptyEl.className = 'ap-empty';
    emptyEl.textContent = emptyHint;
    msgsEl.appendChild(emptyEl);

    const bar = document.createElement('div');
    bar.className = 'ap-inputbar';
    const input = document.createElement('textarea');
    input.className = 'ap-input';
    input.placeholder = placeholder;
    input.rows = 1;
    const send = document.createElement('button');
    send.className = 'ap-send';
    send.type = 'button';
    send.textContent = '发送';
    bar.appendChild(input);
    bar.appendChild(send);

    root.appendChild(msgsEl);
    root.appendChild(bar);
    mount.appendChild(root);

    // ── Helpers ──────────────────────────────────────────
    function scrollBottom() {
      msgsEl.scrollTop = msgsEl.scrollHeight;
    }

    function clearEmpty() {
      if (emptyEl.parentNode === msgsEl) msgsEl.removeChild(emptyEl);
    }

    function appendMessage(m) {
      clearEmpty();
      const node = renderMessage(m);
      msgsEl.appendChild(node);
      scrollBottom();
      return node;
    }

    function showError(msg) {
      msgsEl.appendChild(renderError(msg));
      scrollBottom();
      if (typeof onError === 'function') onError(msg);
    }

    function setBusy(b) {
      busy = b;
      send.disabled = b;
      input.disabled = b;
    }

    async function ask(question) {
      if (destroyed) return;
      const q = (question || '').trim();
      if (!q) return;
      setBusy(true);
      appendMessage({ role: 'user', content: q });
      const pendingNode = appendMessage({ role: 'assistant', content: '思考中…', pending: true });

      try {
        let resp;
        if (threadId == null) {
          resp = await window.authFetch('/ask/threads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              scope, ref_type: refType, ref_id: String(refId),
              context: contextPayload || {},
              question: q,
            }),
          });
        } else {
          resp = await window.authFetch(`/ask/threads/${threadId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q }),
          });
        }
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

        if (threadId == null) {
          threadId = data.thread_id;
          // 首轮返回完整 messages，后端已存了 user/assistant；pending 节点替换为最终答案
          const answer = (data.messages && data.messages[1] && data.messages[1].content) || '';
          pendingNode.querySelector('.ap-bubble').textContent = answer;
          pendingNode.querySelector('.ap-bubble').classList.remove('ap-pending');
        } else {
          pendingNode.querySelector('.ap-bubble').textContent = data.answer || '';
          pendingNode.querySelector('.ap-bubble').classList.remove('ap-pending');
        }
        scrollBottom();
      } catch (err) {
        if (pendingNode && pendingNode.parentNode === msgsEl) msgsEl.removeChild(pendingNode);
        showError((err && err.message) || String(err));
      } finally {
        setBusy(false);
        if (!destroyed) input.focus();
      }
    }

    async function loadExisting() {
      if (threadId != null) return;
      try {
        const resp = await window.authFetch(
          `/ask/threads?scope=${encodeURIComponent(scope)}&ref_type=${encodeURIComponent(refType)}&ref_id=${encodeURIComponent(refId)}&limit=1`
        );
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.items || !data.items.length) return;
        const existing = data.items[0];
        const r2 = await window.authFetch(`/ask/threads/${existing.id}`);
        if (!r2.ok) return;
        const thread = await r2.json();
        threadId = thread.id;
        clearEmpty();
        msgsEl.innerHTML = '';
        (thread.messages || []).forEach(m => appendMessage({ role: m.role, content: m.content }));
      } catch (_) {
        // 静默失败：用户仍然可以开启新 thread
      }
    }

    // ── Events ───────────────────────────────────────────
    function onSend() {
      const v = input.value;
      if (!v.trim() || busy) return;
      input.value = '';
      ask(v);
    }

    send.addEventListener('click', onSend);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    });

    return {
      get threadId() { return threadId; },
      ask,
      loadExisting,
      focus() { input.focus(); },
      destroy() {
        destroyed = true;
        mount.innerHTML = '';
      },
    };
  }

  window.AskPanel = { create };
})();
