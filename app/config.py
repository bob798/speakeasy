from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    DATABASE_URL:     str  = os.getenv("DATABASE_URL", "")
    GROQ_API_KEY:     str  = os.getenv("GROQ_API_KEY", "")
    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
    MAX_TOKENS:       int  = int(os.getenv("MAX_TOKENS", "1024"))
    MODEL_NAME:       str  = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    ALLOWED_ORIGINS:  str  = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")


settings = Settings()

# 向后兼容模块级别变量
MAX_TOKENS:      int = settings.MAX_TOKENS
MODEL_NAME:      str = settings.MODEL_NAME
ALLOWED_ORIGINS: str = settings.ALLOWED_ORIGINS
