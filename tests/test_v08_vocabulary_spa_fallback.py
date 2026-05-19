"""V0.8 hotfix: /vocabulary 应走 SPA fallback，不被 API_PREFIXES 误拦截为 404。

Regression：早先 API_PREFIXES 含 "vocab" 前缀（无斜杠），
`"vocabulary".startswith("vocab")` 命中 → catch-all 抛 404，
导致前端 /vocabulary 独立页无法直达访问。
"""
import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_vocabulary_returns_200_via_spa_fallback():
    """GET /vocabulary 必须被 SPA fallback 接管（不能 404）。"""
    resp = client.get("/vocabulary")
    assert resp.status_code == 200, (
        f"/vocabulary 应走 SPA fallback，实际 {resp.status_code}：{resp.text[:200]}"
    )


def test_vocab_get_still_routed_to_api():
    """对照：/vocab 仍由 FastAPI 路由系统命中（不会变成 SPA fallback）。"""
    resp = client.get("/vocab")
    # 没带 auth → 401 表示路由到了 /vocab 但被鉴权拦截；非 404 / 非 200 SPA HTML。
    # 关键是 content-type 不是 HTML（说明走的不是 SPA fallback）。
    ctype = resp.headers.get("content-type", "")
    assert "json" in ctype or resp.status_code in (401, 422, 403), (
        f"/vocab 应走 API 路由，content-type={ctype}, status={resp.status_code}"
    )


def test_vocab_with_subpath_still_blocked_by_api_prefix():
    """/vocab/{id} 类未命中路径仍应被 API_PREFIXES 拦截（"vocab/" 前缀保留）。"""
    resp = client.get("/vocab/non-existent-path-12345")
    # 不应返回 SPA HTML；应是 404 (route not found) or 401 (auth)。
    ctype = resp.headers.get("content-type", "")
    assert "html" not in ctype, (
        f"/vocab/xxx 不应走 SPA fallback，content-type={ctype}"
    )
