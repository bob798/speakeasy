// ── Speakeasy 通用认证客户端 ─────────────────────────────
// 所有页面引入后使用 authFetch 发送请求；401 自动跳转 /login
(function () {
  const TOKEN_KEY = 'speakeasy_token';
  const USER_KEY  = 'speakeasy_user';

  window.SpeakeasyAuth = {
    getToken()  { try { return localStorage.getItem(TOKEN_KEY);  } catch { return null; } },
    getUser()   { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; } },

    setAuth(token, user) {
      try {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(USER_KEY,  JSON.stringify(user || null));
      } catch (_) {}
    },

    logout() {
      try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch (_) {}
      location.href = '/login';
    },

    async requireAuth() {
      const token = this.getToken();
      if (!token) { location.href = '/login'; return false; }
      // 校验 token 有效性（可以省略，由各接口自己处理）
      try {
        const resp = await fetch('/auth/me', { headers: { Authorization: 'Bearer ' + token } });
        if (!resp.ok) { this.logout(); return false; }
        const data = await resp.json();
        this.setAuth(token, data.user);
        return true;
      } catch (_) {
        // 网络错误不强制踢出登录
        return true;
      }
    },

    // 统一 fetch：自动带 Authorization；401 自动踢出
    async authFetch(url, options = {}) {
      const token = this.getToken();
      options.headers = Object.assign({}, options.headers || {});
      if (token) options.headers['Authorization'] = 'Bearer ' + token;
      const resp = await fetch(url, options);
      if (resp.status === 401) {
        this.logout();
        throw new Error('未登录或登录已过期');
      }
      return resp;
    },
  };

  // 便捷全局别名
  window.authFetch = (url, options) => window.SpeakeasyAuth.authFetch(url, options);
})();
