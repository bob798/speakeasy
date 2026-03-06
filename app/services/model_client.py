import os
import time
import httpx
import anthropic
from openai import OpenAI
from app.config import MAX_TOKENS, MODEL_NAME
from app.prompts.system import SYSTEM_PROMPT
from app.prompts.summary import SUMMARY_PROMPT
from app.logger import get_logger

logger = get_logger("model_client")

# ──────────────────────────────────────────────
# 支持的 Provider 及对应配置
# MODEL_PROVIDER 可选值：anthropic / deepseek / volcengine / zhipu
# ──────────────────────────────────────────────
PROVIDER_CONFIG = {
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": None,  # 使用 Anthropic 官方 SDK，无需 base_url
        "default_model": "doubao-1-5-pro-32k-250115", # 此字段未启用
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "doubao-1-5-pro-32k-250115",
    },
    "volcengine": {
        "env_key": "VOLCENGINE_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "deepseek-v3-250324",
    },
    "zhipu": {
        "env_key": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "doubao-1-5-pro-32k-250115",
    },
}


def _get_provider() -> str:
    """读取 MODEL_PROVIDER 环境变量，校验合法性"""
    provider = os.environ.get("MODEL_PROVIDER", "anthropic").lower()
    if provider not in PROVIDER_CONFIG:
        raise ValueError(
            f"不支持的 MODEL_PROVIDER: '{provider}'，"
            f"可选值：{list(PROVIDER_CONFIG.keys())}"
        )
    return provider


def _get_api_key(provider: str) -> str:
    """读取对应 Provider 的 API Key，Key 缺失时启动报错"""
    env_key = PROVIDER_CONFIG[provider]["env_key"]
    api_key = os.environ.get(env_key)
    if not api_key:
        raise EnvironmentError(
            f"未找到环境变量 {env_key}，"
            f"请在 .env 文件中配置后重启服务。"
        )
    return api_key


# ──────────────────────────────────────────────
# 基类
# ──────────────────────────────────────────────
class BaseModelClient:
    def chat(self, message: str, history: list[dict]) -> str:
        raise NotImplementedError

    def generate_summary(self, history: list[dict]) -> str:
        raise NotImplementedError

    def _format_history(self, history: list[dict]) -> str:
        """将对话历史格式化为纯文本，供 summary 使用"""
        return "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in history
        )


# ──────────────────────────────────────────────
# Anthropic 客户端
# ──────────────────────────────────────────────
class AnthropicClient(BaseModelClient):
    def __init__(self):
        api_key = _get_api_key("anthropic")
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=30.0,
            http_client=httpx.Client(trust_env=False),
        )

    def chat(self, message: str, history: list[dict]) -> str:
        logger.info("调用 Anthropic chat model=%s history_turns=%d", MODEL_NAME, len(history))
        t0 = time.time()
        try:
            messages = history + [{"role": "user", "content": message}]
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            elapsed = time.time() - t0
            logger.info("Anthropic chat 完成 耗时=%.2fs", elapsed)
            return response.content[0].text
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("Anthropic chat 失败 耗时=%.2fs error=%s", elapsed, e, exc_info=True)
            raise Exception(f"Anthropic API 调用失败：{e}")

    def generate_summary(self, history: list[dict]) -> str:
        logger.info("调用 Anthropic summary model=%s", MODEL_NAME)
        t0 = time.time()
        try:
            prompt = SUMMARY_PROMPT + self._format_history(history)
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - t0
            logger.info("Anthropic summary 完成 耗时=%.2fs", elapsed)
            return response.content[0].text
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("Anthropic summary 失败 耗时=%.2fs error=%s", elapsed, e, exc_info=True)
            raise Exception(f"今日一句生成失败：{e}")


# ──────────────────────────────────────────────
# OpenAI 兼容客户端（DeepSeek / 火山方舟 / 智谱 通用）
# ──────────────────────────────────────────────
class OpenAICompatibleClient(BaseModelClient):
    def __init__(self, provider: str):
        self.provider = provider
        api_key = _get_api_key(provider)
        base_url = PROVIDER_CONFIG[provider]["base_url"]
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0,
            http_client=httpx.Client(trust_env=False),  # 忽略系统代理

        )

    def chat(self, message: str, history: list[dict]) -> str:
        logger.info("调用 %s chat model=%s history_turns=%d", self.provider, MODEL_NAME, len(history))
        t0 = time.time()
        try:
            messages = (
                [{"role": "system", "content": SYSTEM_PROMPT}]
                + history
                + [{"role": "user", "content": message}]
            )
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                messages=messages,
            )
            elapsed = time.time() - t0
            logger.info("%s chat 完成 耗时=%.2fs", self.provider, elapsed)
            return response.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("%s chat 失败 耗时=%.2fs error=%s", self.provider, elapsed, e, exc_info=True)
            raise Exception(f"{self.provider} API 调用失败：{e}")

    def generate_summary(self, history: list[dict]) -> str:
        logger.info("调用 %s summary model=%s", self.provider, MODEL_NAME)
        t0 = time.time()
        try:
            prompt = SUMMARY_PROMPT + self._format_history(history)
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - t0
            logger.info("%s summary 完成 耗时=%.2fs", self.provider, elapsed)
            return response.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("%s summary 失败 耗时=%.2fs error=%s", self.provider, elapsed, e, exc_info=True)
            raise Exception(f"今日一句生成失败（{self.provider}）：{e}")


# ──────────────────────────────────────────────
# 工厂函数：根据环境变量返回对应客户端实例
# ──────────────────────────────────────────────
def get_client() -> BaseModelClient:
    provider = _get_provider()
    if provider == "anthropic":
        return AnthropicClient()
    else:
        return OpenAICompatibleClient(provider)


# ──────────────────────────────────────────────
# 向后兼容：保留 ClaudeService 调用方式
# 其他模块 service = ClaudeService() 无需修改
# ──────────────────────────────────────────────
class ClaudeService:
    def __new__(cls):
        return get_client()