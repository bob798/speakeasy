function getUserId() {
    // 优先从 SpeakeasyAuth 取登录用户 ID（V0.6 起）
    if (window.SpeakeasyAuth) {
        const u = window.SpeakeasyAuth.getUser();
        if (u && u.id) return u.id;
    }
    // 兼容兜底：匿名 uid
    let id = localStorage.getItem('speakeasy_uid');
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('speakeasy_uid', id); }
    return id;
}

function getSessionId() {
    let id = sessionStorage.getItem('speakeasy_sid');
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem('speakeasy_sid', id); }
    return id;
}

function newSession() {
    sessionStorage.removeItem('speakeasy_sid');
    return getSessionId();
}

function showToast(msg, type = 'info', duration = 3000) {
    document.querySelector('.toast')?.remove();
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, duration);
}

function showBanner(msg) {
    const b = document.getElementById('compat-banner');
    document.getElementById('compat-msg').textContent = msg;
    b.style.display = 'flex';
}
