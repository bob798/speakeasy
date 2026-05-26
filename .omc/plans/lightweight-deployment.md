# Speakeasy Lightweight Deployment Plan

**Date:** 2026-04-17
**Status:** APPROVED (Consensus: Planner + Architect + Critic)
**Goal:** Slim Docker image from ~1.5GB to <300MB, remove dead server-side VAD code, establish self-hosted VPS deployment with docker-compose + Caddy HTTPS + CI/CD.

---

## 1. Requirements Summary

| Requirement | Detail |
|---|---|
| Image size target | < 300MB (down from ~1.5GB) |
| Remove server VAD | Delete `app/routers/vad.py`, `app/services/vad_service.py`, all VAD test files |
| Dependency cleanup | Remove `asyncpg`, transitive `numpy`/`torch`/`silero_vad`. **Keep `anthropic`**. |
| Keep | FastAPI, Edge-TTS, Groq STT, SQLite (aiosqlite), vanilla JS frontend, ffmpeg |
| Deployment target | Single VPS with Docker, HTTPS via reverse proxy, CI/CD on push to main |
| Recording model | User-controlled button (client-side Web Audio API VAD already in place at `static/js/stt-provider.js`) |

---

## 2. RALPLAN-DR Summary

### Principles (5)

1. **Dead code is liability** -- Unused server VAD adds ~1.2GB of PyTorch weight, attack surface, and startup time for zero user value.
2. **Minimal dependency surface** -- Every pip package is a maintenance burden. Only keep what runtime actually imports.
3. **Reproducible deployment** -- A single `docker compose up` must produce a working instance from a clean VPS (Ubuntu 22.04+ with Docker + Docker Compose).
4. **HTTPS by default** -- Production must serve over TLS. No exceptions, no manual cert management.
5. **Ship incrementally** -- Each stage is independently verifiable and committable. Use one commit per stage on the branch.

### Decision Drivers (Top 3)

1. **Image size** -- The primary goal. Every decision is weighed against its impact on the final image.
2. **Operational simplicity** -- Solo-developer VPS deployment. Fewer moving parts beat marginal performance gains.
3. **Zero-downtime path** -- CI/CD must not break the running service during deploy.

### Viable Options

#### A. Reverse Proxy: Caddy vs Nginx

| | Caddy | Nginx |
|---|---|---|
| **Pros** | Auto HTTPS (ACME built-in), 6-line Caddyfile, zero cert cron jobs | Battle-tested, lower memory, more community examples |
| **Cons** | Slightly larger image (~40MB); requires port 80/443 open + real DNS for ACME challenge | Manual certbot setup, renewal cron, 30+ line config for equivalent |
| **Verdict** | **Recommended.** Auto-TLS eliminates an entire class of ops failures. Include an HTTP-only dev Caddyfile for local/staging testing. |

**Architect steelman (Caddy risk):** Caddy's auto-HTTPS requires port 80/443 accessible from the internet + real DNS resolution. On a VPS behind firewall, CDN, or staging without DNS, auto-TLS fails silently (self-signed fallback) or blocks startup. **Mitigation:** Provide `Caddyfile.dev` (HTTP-only, `localhost:80`) alongside production `Caddyfile`.

#### B. Base Image: python:3.12-slim vs python:3.12-alpine

| | python:3.12-slim (Debian) | python:3.12-alpine |
|---|---|---|
| **Pros** | pip wheels just work, glibc compatible, ffmpeg apt-get | Smaller base (~50MB vs ~120MB) |
| **Cons** | ~70MB larger base | musl libc breaks some wheels, requires build tools for compilation, ffmpeg needs custom repo |
| **Verdict** | **Recommended: slim.** The 70MB delta is trivial compared to the 1.2GB saved by removing PyTorch. Alpine's musl incompatibilities create real build failures. |

**Note:** Use `python:3.12-slim` to match the development environment (Python 3.12).

#### C. CI/CD: GitHub Actions + GHCR vs alternatives

| | GitHub Actions + GHCR | Self-hosted Gitea+Drone | Manual SSH script |
|---|---|---|---|
| **Pros** | Free for public repos, rich ecosystem, GHCR built-in | Full control, no vendor lock | Zero setup |
| **Cons** | Vendor dependency, secrets management | Extra infra to maintain | No rollback, no audit trail, error-prone |
| **Verdict** | **Recommended: GitHub Actions.** Build on GH runner, push to GHCR, SSH to VPS to pull image (no build tooling needed on VPS). |

**CI/CD strategy (clarified):** Build Docker image on GitHub Actions runner → push to GHCR → SSH to VPS → `docker compose pull && docker compose up -d`. VPS only needs Docker, not build tools.

---

## 3. Implementation Steps

### Stage 1: VAD Removal (dead code deletion)

**Objective:** Remove all server-side VAD code. Frontend is unaffected (uses client-side Web Audio API).

| Step | Action | Files | Acceptance Criteria |
|---|---|---|---|
| 1.1 | Delete VAD router | `app/routers/vad.py` (50 lines) | File does not exist |
| 1.2 | Delete VAD service | `app/services/vad_service.py` (62 lines) | File does not exist |
| 1.3 | Remove VAD import and registration from main | `main.py` line 10 (`from app.routers.vad import router as vad_router`) and line 38 (`app.include_router(vad_router)`) | `grep -r "vad_router" main.py` returns nothing |
| 1.4 | Delete/fix VAD test files | Delete: `tests/test_step4_v031.py`, `tests/test_step6_v031.py`, `tests/test_step6_v031_bugfix.py`. Fix: `tests/test_step1_v031.py` lines 48-51 (remove silero import test). Note: `tests/test_step5_v031_bugfix.py` line 36 has `assert "vad_active" not in data` — negative assertion, passes without changes. | VAD test files deleted, silero-specific assertions removed |
| 1.5 | Search for remaining server VAD references | All `.py` files in `app/`, `main.py`, AND `tests/` | `grep -r "silero\|VADService\|VADState\|vad_service\|from app.routers.vad" app/ main.py tests/` returns zero matches (excluding negative assertions) |
| 1.6 | Verify app starts | `python -c "from main import app; print('OK')"` | Prints OK without ImportError |

**IMPORTANT: Frontend VAD references MUST be preserved.** `static/index.html` (7 references) and `static/js/stt-provider.js` (`AudioVAD` class) contain client-side Web Audio API VAD using browser-native frequency analysis. These are NOT server-side Silero VAD and must NOT be touched. They provide the user-facing recording UI feedback.

### Stage 2: Dependency Cleanup

**Objective:** Remove unused packages from `requirements.txt`. Verify no runtime import breaks.

| Step | Action | Detail | Acceptance Criteria |
|---|---|---|---|
| 2.1 | Remove `asyncpg==0.30.0` | Line 9 of `requirements.txt`. PostgreSQL driver, project uses SQLite only. Zero imports in `app/`. | `grep -r "asyncpg" app/` returns nothing |
| 2.2 | Confirm `numpy`/`torch`/`silero` not needed | These were transitive deps of Silero VAD. After Stage 1 deletion, no `.py` file imports them. Not directly in `requirements.txt`. | `pip install -r requirements.txt` succeeds without pulling torch/numpy |
| 2.3 | **KEEP `anthropic==0.40.0`** | `app/services/model_client.py:5` has unconditional `import anthropic`. `AnthropicClient` (lines 109-184) is fully implemented. `anthropic` is the DEFAULT provider (line 44: `os.environ.get("MODEL_PROVIDER", "anthropic")`). Removing it would cause ImportError on every startup. | Package remains in `requirements.txt` |
| 2.4 | Pin ALL unpinned packages | Pin `groq`, `edge-tts`, `python-multipart`, `fsrs`, `youtube-transcript-api`, `yt-dlp` to current installed versions. | All packages in requirements.txt have `==X.Y.Z` pins |
| 2.5 | Verify `yt-dlp` transitive size | Run `pip install --dry-run -r requirements.txt` and check total download size. If >100MB total, consider if yt-dlp can be made optional. | Total pip download size documented |
| 2.6 | Clean install test | `pip install --no-cache-dir -r requirements.txt` in a fresh venv | Installs without torch/numpy/silero |
| 2.7 | Run remaining tests | `pytest tests/ -x` (after VAD test files deleted in Stage 1) | All pass (or pre-existing failures documented) |

**Final `requirements.txt` target (~13 packages):**
```
fastapi==0.115.0
uvicorn==0.30.0
anthropic==0.40.0
openai==1.57.0
python-dotenv==1.0.0
pydantic==2.9.0
sqlalchemy==2.0.36
aiosqlite==0.20.0
groq==<pinned>
edge-tts==<pinned>
python-multipart==<pinned>
fsrs==<pinned>
youtube-transcript-api==<pinned>
yt-dlp==<pinned>
```

### Stage 3: Dockerfile Optimization

**Objective:** Minimize image size with layer caching and clean build practices.

| Step | Action | Detail | Acceptance Criteria |
|---|---|---|---|
| 3.1 | Update base to `python:3.12-slim` | Match development environment Python version (3.12). | Dockerfile FROM line updated |
| 3.2 | Review and update existing `.dockerignore` | `.dockerignore` already exists. Verify it excludes: `venv/`, `__pycache__/`, `*.db*`, `.git/`, `tests/`, `docs/`, `.omc/`, `*.md`. | `docker build` context is <5MB |
| 3.3 | Optimize layer ordering | Copy `requirements.txt` first, `pip install`, then copy app code. (Already done in current Dockerfile — verify preserved.) | Layer cache hits on code-only changes |
| 3.4 | Remove legacy hardcoded ENV | Remove `ENV SPEAKEASY_DB_PATH=/data/speakeasy.db` from Dockerfile (line 19). Move to docker-compose env. | Dockerfile has no hardcoded paths |
| 3.5 | Build and measure | `docker build -t speakeasy:slim .` then `docker images speakeasy:slim` | Image size < 300MB |
| 3.6 | Smoke test the image | `docker run --rm -p 8000:8000 speakeasy:slim` and `curl http://localhost:8000/` | Returns HTML (index.html) |
| 3.7 | Fallback if >300MB | If image exceeds 300MB, investigate `yt-dlp` transitive deps (`certifi`, `brotli`, `mutagen`, `pycryptodomex`, `websockets`). Consider `--no-deps` with explicit sub-deps. | Image under target or deviation documented |

**Expected image breakdown:**
- python:3.12-slim base: ~120MB
- ffmpeg: ~50MB
- pip packages (no torch): ~80MB
- app code + static: ~5MB
- **Total: ~255MB** (well under 300MB target)

### Stage 4: Deployment Infrastructure

**Objective:** Create docker-compose.yml, Caddyfile, healthcheck, and GitHub Actions CI/CD for VPS deployment.

| Step | Action | Detail | Acceptance Criteria |
|---|---|---|---|
| 4.0 | Add `/health` endpoint | Add `GET /health` returning `{"status": "ok"}` in `main.py`. Used by docker-compose healthcheck. | `curl http://localhost:8000/health` returns 200 |
| 4.1 | Create `docker-compose.yml` | Services: `app` (with healthcheck), `caddy` (depends_on app healthy). Volumes: `speakeasy_data`, `caddy_data`, `caddy_config`. Networks: `speakeasy_net`. | `docker compose config` validates without error |
| 4.2 | Create `Caddyfile` (production) | Domain via `{$DOMAIN}` env var, auto-HTTPS, reverse_proxy to `app:8000`, encode gzip. | File exists, <10 lines |
| 4.2b | Create `Caddyfile.dev` (local) | HTTP-only, `localhost:80` reverse_proxy to `app:8000`. For local/staging testing without real DNS. | File exists |
| 4.3 | Create `.env.production.example` | Template with all required vars: `DOMAIN`, `MODEL_PROVIDER=volcengine`, `VOLCENGINE_API_KEY`, `GROQ_API_KEY`, `SPEAKEASY_DB_PATH=/data/speakeasy.db`. | File exists, no real secrets committed |
| 4.4 | Create `.github/workflows/deploy.yml` | Trigger on push to `main`. Steps: checkout → login GHCR → build+push image → SSH to VPS → `docker compose pull && docker compose up -d`. | YAML validates |
| 4.5 | Update `.gitignore` | Add `.env.production`, verify `speakeasy.db*`, `static/tts_cache/*`, `static/audio_cache/*` are excluded | Sensitive files excluded |
| 4.6 | ~~Add `fly.toml` legacy comment~~ | DONE — `fly.toml` 已彻底移除（仓库不再保留 Fly.io 配置）。 | n/a |
| 4.7 | Write deployment README section | Setup instructions: clone, copy `.env.production.example`, `docker compose up -d`. Include rollback: `docker compose pull <previous-tag> && docker compose up -d`. | Instructions copy-pasteable on Ubuntu 22.04+ with Docker |

**docker-compose.yml structure:**
```yaml
services:
  app:
    image: ghcr.io/<owner>/speakeasy:latest
    build: .
    restart: unless-stopped
    env_file: .env.production
    volumes:
      - speakeasy_data:/data
    networks:
      - speakeasy_net
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - speakeasy_net
    depends_on:
      app:
        condition: service_healthy

volumes:
  speakeasy_data:
  caddy_data:
  caddy_config:

networks:
  speakeasy_net:
```

---

## 4. Acceptance Criteria (End-to-End)

| # | Criterion | Verification Command |
|---|---|---|
| AC-1 | No server VAD code in backend | `grep -r "silero\|VADService\|vad_service\|from app.routers.vad" app/ main.py tests/` returns empty |
| AC-2 | No torch/numpy installed | `docker run --rm speakeasy:slim pip list \| grep -i "torch\|numpy"` returns empty |
| AC-3 | Image size < 300MB | `docker images speakeasy:slim --format '{{.Size}}'` shows < 300MB |
| AC-4 | App starts and serves frontend | `curl -s http://localhost:8000/ \| head -1` contains `<!DOCTYPE html>` |
| AC-5 | STT endpoint works | `curl -s -X POST http://localhost:8000/api/stt/transcribe` returns 422 (not 500) |
| AC-6 | TTS endpoint responds | `curl -s -o /dev/null -w '%{http_code}' "http://localhost:8000/api/tts/speak?text=hello"` returns 200 or 422 |
| AC-7 | docker-compose up works | `docker compose up -d` on Ubuntu 22.04+ with Docker starts both services, `docker compose ps` shows both healthy |
| AC-8 | Caddy issues TLS cert | `curl -I https://{domain}` returns 200 (requires real domain + DNS, manual verification) |
| AC-9 | CI/CD deploys on push | Push to main → GH Action runs → `docker ps --format '{{.Image}}'` on VPS shows updated GHCR image digest |
| AC-10 | Existing tests pass | `pytest tests/ -x` passes (VAD test files already deleted in Stage 1) |
| AC-11 | Anthropic provider works | `MODEL_PROVIDER=anthropic python -c "from app.services.model_client import get_client; c=get_client(); print(type(c))"` prints AnthropicClient |
| AC-12 | Health endpoint works | `curl -s http://localhost:8000/health` returns `{"status":"ok"}` with 200 |

---

## 5. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `edge-tts` or `yt-dlp` pulls in large transitive deps | Low | Medium | Step 2.5 does `--dry-run` check. Step 3.7 has fallback. |
| Existing tests import VAD indirectly | Low | Medium | Stage 1.5 does full grep including `tests/`. Stage 2.7 runs test suite. |
| VPS SSH key compromise via GitHub secrets | Low | High | Use GitHub deploy keys (read-only repo + SSH). Document rotation procedure in README. |
| Caddy ACME fails (no DNS/firewall) | Medium | Medium | `Caddyfile.dev` provides HTTP-only fallback. Document DNS requirement. |
| SQLite file locking under concurrent requests | Medium | Low | Already the status quo. Not in scope. Document as known limitation. |
| Image exceeds 300MB due to yt-dlp deps | Low | Medium | Step 3.7 fallback plan. |
| Deployment downtime during update | Low | Medium | docker-compose `restart: unless-stopped` + healthcheck. Rollback documented in Step 4.7. |

---

## 6. Verification Steps (Ordered)

1. **Post Stage 1:** `python -c "from main import app"` succeeds. `grep -r "silero\|VADService\|VADState" app/ main.py tests/` returns nothing.
2. **Post Stage 2:** Fresh venv install completes without torch. `pip list | wc -l` is under 50 packages. `anthropic` is present.
3. **Post Stage 3:** `docker build -t speakeasy:slim . && docker images speakeasy:slim` shows <300MB. `docker run --rm -p 8000:8000 speakeasy:slim` serves the app. `curl localhost:8000/health` returns 200.
4. **Post Stage 4:** On a test VPS, `git clone && cp .env.production.example .env.production && docker compose up -d` brings up the app. `docker compose ps` shows both services healthy.
5. **Final:** Push a trivial commit to `main`, verify GitHub Action triggers, VPS updates automatically.

---

## ADR: Deployment Architecture Decision

- **Decision:** Caddy reverse proxy + GitHub Actions CI/CD (GHCR) + python:3.12-slim base image
- **Drivers:** Image size minimization, operational simplicity for solo developer, zero-config HTTPS
- **Alternatives considered:**
  - Nginx: rejected — manual cert management (certbot + cron) adds operational burden for solo developer
  - Alpine base: rejected — musl compatibility issues with Python wheels outweigh 70MB savings; pragmatic given the 1.2GB PyTorch savings already achieved
  - Self-hosted Gitea/Drone: rejected — unnecessary infrastructure for a GitHub-hosted project
  - Manual SSH deploy: rejected — no audit trail, no rollback, error-prone
  - Build on VPS: rejected — requires build tooling on VPS; GHCR approach means VPS only needs Docker
- **Why chosen:** Caddy eliminates TLS ops entirely. GitHub Actions + GHCR is free and avoids build tooling on VPS. Slim base avoids musl wheel compilation failures.
- **Consequences:** Caddy adds ~40MB to the stack (acceptable). GitHub Actions creates vendor dependency (mitigated: workflow is portable to any CI with SSH). GHCR requires VPS to have network access to ghcr.io.
- **Follow-ups:** ~~Evaluate `fly.toml` full removal in a future PR.~~ DONE. Consider SQLite backup strategy for production.

---

## Execution Order

```
Stage 1 (VAD removal) --> Stage 2 (dependency cleanup) --> Stage 3 (Dockerfile) --> Stage 4 (infra)
```

Each stage gets its own commit on the branch. Merge as one PR with clear commit boundaries for easy bisection.

**Estimated effort:** 2-3 hours for an executor agent, including verification.

---

## Consensus Changelog

Applied improvements from Architect + Critic review:
1. **[CRITICAL]** Step 2.3: Changed from "remove anthropic" to "KEEP anthropic" — it is actively imported at `model_client.py:5` and is the default provider
2. **[MAJOR]** Added healthcheck endpoint (Stage 4 Step 4.0) and `depends_on: service_healthy` to docker-compose
3. **[MAJOR]** Expanded Step 1.5 grep scope to include `tests/` directory
4. **[MAJOR]** Added frontend VAD preservation note (AudioVAD in stt-provider.js is client-side, must keep)
5. **[MAJOR]** Updated base image to python:3.12-slim (matches dev environment)
6. **[MINOR]** Step 3.2: Changed from "Add .dockerignore" to "Review and update existing .dockerignore"
7. **[MINOR]** Step 2.4: Pin ALL unpinned packages, not just groq and edge-tts
8. **[MINOR]** Added `Caddyfile.dev` for local/staging testing (Architect synthesis)
9. **[MINOR]** Clarified CI/CD strategy: build on GH runner → GHCR → VPS pulls (no build on VPS)
10. **[MINOR]** Added AC-11 (Anthropic provider works) and AC-12 (healthcheck works)
11. **[MINOR]** Added rollback procedure to Step 4.7
12. **[MINOR]** Fixed Principle 5 / Execution Order alignment: one commit per stage, merge as single PR
