import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import ALLOWED_ORIGINS, MODEL_NAME
from app.api.chat import router
from app.logger import get_logger

logger = get_logger("main")
app = FastAPI(title="Speakeasy API")


@app.on_event("startup")
async def _on_startup():
    provider = os.getenv("MODEL_PROVIDER", "anthropic")
    logger.info("服务启动 provider=%s model=%s", provider, MODEL_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
