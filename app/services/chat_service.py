# Compatibility shim — chat logic lives in model_client.py
from app.prompts.system import SYSTEM_PROMPT
from app.services.model_client import get_client

__all__ = ["SYSTEM_PROMPT", "get_client"]
