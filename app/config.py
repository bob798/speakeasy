from dotenv import load_dotenv
import os

load_dotenv()


MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
MODEL_NAME: str = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
