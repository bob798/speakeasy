import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.services.bbc_eaw_seeder import seed_at_startup
from app.routers import chat, stt, tts, history, debug, review
from app.routers.settings import router as settings_router
from app.routers.memory import router as memory_router
from app.routers.articles import router as articles_router
from app.routers.translate import router as translate_router
from app.routers.auth import router as auth_router
from app.routers.ask import router as ask_router
from app.routers.stats import router as stats_router
from app.routers.bbc_eaw import router as bbc_eaw_router
from app.routers.bbc_review import router as bbc_review_router
from app.routers.vocab import router as vocab_router
from app.routers.polish import router as polish_router
from app.routers.model import router as model_router


# ── V0.8 前端重构挂载策略（Pass 3 plan §4 + Critic B1-B5）────────────
# `/`        → frontend/dist/index.html（Vue SPA，history 模式）
# `/legacy/` → 老版 static HTML（回滚路径，保留 2 周灰度期）
# `/static/` → 保留（audio_cache、tts_cache 等数据目录仍走这里）
# `/assets/` → Vite 构建产物（JS/CSS/PWA sw/manifest）
#
# 如果 frontend/dist 不存在（未构建），全部 fallback 回老版 static/
FRONTEND_DIST = "frontend/dist"
SPA_AVAILABLE = os.path.isdir(FRONTEND_DIST)

# API 路径前缀：catch-all 不得覆盖这些 GET 路由（它们已被对应 router 处理）
# 这里列的是 **GET 路径前缀**，用于 SPA fallback 判断
API_PREFIXES = (
    "api/",
    "chat",
    "stt",
    "tts",
    "history",
    "sessions",
    "review/",
    "memory/",
    "practice/",
    "articles/",
    "translate/",
    "vocab/",
    "polish/",
    "auth/",
    "ask/",
    "assessment/",
    "settings/",
    "stats/",
    "bbc-eaw/",
    "health",
    "debug/",
    "legacy/",
    ".well-known/",
    "static/",
    "assets/",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    seed_at_startup()  # idempotent · 失败仅 warn 不挂启动
    yield


app = FastAPI(title="Speakeasy API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(history.router)
app.include_router(debug.router)
app.include_router(review.router)
app.include_router(settings_router)
app.include_router(memory_router)
app.include_router(articles_router, prefix="/articles")
app.include_router(articles_router, prefix="/practice", include_in_schema=False)
# ↑ alias: include_in_schema=False prevents OpenAPI duplication; remove in 1-2 versions
app.include_router(translate_router)
app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(stats_router)
app.include_router(bbc_eaw_router)
app.include_router(bbc_review_router)
app.include_router(vocab_router)
app.include_router(polish_router)
app.include_router(model_router)

# 数据目录挂载（audio_cache、tts_cache 等）——无论新旧前端都要读
app.mount("/static", StaticFiles(directory="static"), name="static")

# SPA 资源挂载（Vue bundle）——仅在构建产物存在时启用
if SPA_AVAILABLE and os.path.isdir(os.path.join(FRONTEND_DIST, "assets")):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="spa_assets",
    )


# ── 系统端点（保持不变）────────────────────────────────────────
def _read_version() -> str:
    """
    版本号来源优先级：
    1. APP_VERSION 环境变量（CI 构建时注入，如 0.10-20260504-5216d48）
    2. VERSION 文件 + 本地 git sha（开发环境）
    3. dev
    """
    import os, subprocess
    env_ver = os.environ.get("APP_VERSION")
    if env_ver:
        return env_ver
    try:
        base = open("VERSION").read().strip()
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return f"{base}-dev-{sha}"
    except Exception:
        return "dev"

APP_VERSION = _read_version()


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION, "spa_available": SPA_AVAILABLE}


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools_noop():
    return Response(status_code=204)


# ── /legacy/* 老版 HTML（回滚路径，Pass 3 B3）─────────────────
@app.get("/legacy/")
@app.get("/legacy")
async def legacy_root():
    return FileResponse("static/index.html")


@app.get("/legacy/review")
async def legacy_review():
    return FileResponse("static/review.html")


@app.get("/legacy/memory")
async def legacy_memory():
    return FileResponse("static/memory.html")


@app.get("/legacy/practice")
async def legacy_practice():
    return FileResponse("static/practice.html")


@app.get("/legacy/translate")
async def legacy_translate():
    return FileResponse("static/translate.html")


@app.get("/legacy/login")
async def legacy_login():
    return FileResponse("static/login.html")


# ── SPA catch-all（必须放在所有路由之后）──────────────────────
def _serve_spa_or_legacy(full_path: str = "") -> FileResponse:
    """
    Vue Router history 模式 fallback 策略：
    1. 如果路径是 API 前缀 → 404（应该被对应 router 拦截，走到这说明没匹配）
    2. 如果 frontend/dist 可用且路径是具体文件 → 返回该文件
    3. 如果 frontend/dist 可用 → 返回 dist/index.html（由 Vue Router 接管）
    4. 否则 fallback → 返回老版 static/index.html
    """
    # API 前缀防护：404 让前端看到明确错误，而不是加载 SPA shell 迷惑用户
    if full_path.startswith(API_PREFIXES):
        raise HTTPException(status_code=404, detail="Not Found")

    if SPA_AVAILABLE:
        # 具体文件（如 manifest.webmanifest / sw.js / favicon.svg）
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    # 未构建 SPA → 回老版 index.html（灰度期尚未切换状态）
    return FileResponse("static/index.html")


@app.get("/")
async def root():
    return _serve_spa_or_legacy("")


# catch-all：任何未匹配的 GET 路径（包括 /chat /practice /memory 等 Vue 路由）
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return _serve_spa_or_legacy(full_path)
