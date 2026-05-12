from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    DATABASE_URL:     str  = os.getenv("DATABASE_URL", "")
    GROQ_API_KEY:     str  = os.getenv("GROQ_API_KEY", "")
    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
    # 对话接口的 token 上限。Alex 每次回复 ≤3 句，约 80 tokens 足够。
    # 设为 300 保留余量，防止过于复杂的长回复。
    # review_service / summary 使用独立的 max_tokens 参数，不受此影响。
    MAX_TOKENS:       int  = int(os.getenv("MAX_TOKENS", "300"))
    MODEL_NAME:       str  = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    MODEL_NAME_ALT:   str  = os.getenv("MODEL_NAME_ALT", "")
    ALLOWED_ORIGINS:  str  = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    AZURE_TTS_KEY:    str  = os.getenv("AZURE_TTS_KEY", "")
    AZURE_TTS_REGION: str  = os.getenv("AZURE_TTS_REGION", "eastasia")
    GOOGLE_TTS_API_KEY: str = os.getenv("GOOGLE_TTS_API_KEY", "")
    TTS_DEFAULT_PROVIDER: str = os.getenv("TTS_DEFAULT_PROVIDER", "edge")


settings = Settings()

# 向后兼容模块级别变量
MAX_TOKENS:      int = settings.MAX_TOKENS
MODEL_NAME:      str = settings.MODEL_NAME
ALLOWED_ORIGINS: str = settings.ALLOWED_ORIGINS


# ──────────────────────────────────────────────
# 运行时模型状态（支持热切换，无需重启）
# ──────────────────────────────────────────────
class _RuntimeModelState:
    """进程内单例，存储当前活跃模型。API 可写，所有 service 读。"""

    def __init__(self):
        self._provider: str = os.getenv("MODEL_PROVIDER", "anthropic")
        self._model: str = settings.MODEL_NAME
        self._model_alt: str = settings.MODEL_NAME_ALT
        # 固定可用列表（不随切换变化）
        self._available: list[str] = [settings.MODEL_NAME]
        if settings.MODEL_NAME_ALT:
            self._available.append(settings.MODEL_NAME_ALT)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def model_alt(self) -> str:
        return self._model_alt

    @property
    def available_models(self) -> list[str]:
        return self._available

    def switch(self, model_name: str) -> str:
        """切换当前活跃模型，返回切换后的模型名。"""
        if model_name not in self.available_models:
            raise ValueError(
                f"模型 '{model_name}' 不在可用列表中: {self.available_models}"
            )
        self._model = model_name
        return self._model

    def status(self) -> dict:
        return {
            "provider": self._provider,
            "active_model": self._model,
            "available_models": self.available_models,
        }


runtime_model = _RuntimeModelState()


# ──────────────────────────────────────────────
# 多模型注册表
# 支持按场景 (scene) 选用不同 provider + model
# 场景：chat / explain / review / translate / default
# ──────────────────────────────────────────────
MODEL_REGISTRY = {
    "volcengine": {
        "env_key": "VOLCENGINE_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["deepseek-v3-250324", "doubao-1-5-pro-32k-250115", "glm-4-7-251222"],
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": None,
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "zhipu": {
        "env_key": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-flash", "glm-4-7-251222"],
    },
}


def get_scene_model(scene: str = "default") -> tuple[str, str]:
    """
    获取某场景的 (provider, model_name)。
    优先读 MODEL_SCENE_<SCENE> 环境变量（格式: provider/model），
    fallback 到全局 MODEL_PROVIDER + MODEL_NAME。

    示例 .env:
      MODEL_SCENE_EXPLAIN=zhipu/glm-4-7-251222
      MODEL_SCENE_REVIEW=volcengine/deepseek-v3-250324
    """
    env_key = f"MODEL_SCENE_{scene.upper()}"
    scene_val = os.getenv(env_key)
    if scene_val and "/" in scene_val:
        provider, model = scene_val.split("/", 1)
        return provider, model
    # fallback: 全局配置
    provider = os.getenv("MODEL_PROVIDER", "anthropic")
    model = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    return provider, model
