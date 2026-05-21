from __future__ import annotations
import os
import time
from typing import AsyncGenerator, Optional
import httpx
import anthropic
from openai import OpenAI
from app.config import MAX_TOKENS, MODEL_NAME, MODEL_REGISTRY, get_scene_model, runtime_model
from app.prompts.system import SYSTEM_PROMPT
from app.prompts.summary import SUMMARY_PROMPT
from app.logger import get_logger
from app.services.llm_logger import log_llm_call, StreamLogger

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
        "default_model": "glm-4-7-251222",
    },
}


def _active_model() -> str:
    """获取运行时活跃模型名（支持热切换）"""
    return runtime_model.model


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

    async def chat_stream(self, message: str, history: list[dict]) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def chat_stream_messages(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """接收完整 messages 列表（含 system），流式输出。与 complete() 接口设计一致。"""
        raise NotImplementedError

    def generate_summary(self, history: list[dict]) -> str:
        raise NotImplementedError

    async def complete(
        self,
        messages_or_prompt,
        max_tokens: int = 1000,
        scene: str = "default",
        timeout: Optional[float] = None,
    ) -> str:
        """
        单次 LLM 调用，返回纯文本。
        - 传入 str：单条 prompt，包装成 user message
        - 传入 list：完整 messages 列表（含 system）
        - timeout: 可选，按调用覆盖 SDK 全局 timeout；None 时回落到 client 全局 30s
        """
        import asyncio
        if isinstance(messages_or_prompt, list):
            messages = messages_or_prompt
        else:
            messages = [{"role": "user", "content": messages_or_prompt}]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._complete_sync_messages(messages, max_tokens, scene, timeout),
        )

    def _complete_sync_messages(
        self,
        messages: list,
        max_tokens: int,
        scene: str = "default",
        timeout: Optional[float] = None,
    ) -> str:
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
        logger.info("调用 Anthropic chat model=%s history_turns=%d", _active_model(), len(history))
        t0 = time.time()
        try:
            messages = history + [{"role": "user", "content": message}]
            response = self.client.messages.create(
                model=_active_model(),
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

    async def chat_stream(self, message: str, history: list[dict]) -> AsyncGenerator[str, None]:
        logger.info("调用 Anthropic chat_stream model=%s history_turns=%d", _active_model(), len(history))
        messages = history + [{"role": "user", "content": message}]
        with self.client.messages.stream(
            model=_active_model(), max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                yield text

    async def chat_stream_messages(self, messages: list[dict], scene: str = "default") -> AsyncGenerator[str, None]:
        logger.info("调用 Anthropic chat_stream_messages model=%s", _active_model())
        sl = StreamLogger(scene, "anthropic", _active_model(), messages)
        system = next((m["content"] for m in messages if m.get("role") == "system"), None)
        user_messages = [m for m in messages if m.get("role") != "system"]
        kwargs = {"model": _active_model(), "max_tokens": MAX_TOKENS, "messages": user_messages}
        if system:
            kwargs["system"] = system
        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    sl.on_chunk(text)
                    yield text
            sl.finish()
        except Exception as e:
            sl.finish(status="error", error_message=str(e))
            raise

    def generate_summary(self, history: list[dict]) -> str:
        logger.info("调用 Anthropic summary model=%s", _active_model())
        t0 = time.time()
        messages = [{"role": "user", "content": SUMMARY_PROMPT + self._format_history(history)}]
        try:
            response = self.client.messages.create(
                model=_active_model(),
                max_tokens=256,
                messages=messages,
            )
            elapsed = time.time() - t0
            result = response.content[0].text
            logger.info("Anthropic summary 完成 耗时=%.2fs", elapsed)
            log_llm_call("summary", "anthropic", _active_model(), messages, result,
                         total_ms=int(elapsed * 1000))
            return result
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("Anthropic summary 失败 耗时=%.2fs error=%s", elapsed, e, exc_info=True)
            log_llm_call("summary", "anthropic", _active_model(), messages, "",
                         total_ms=int(elapsed * 1000), status="error", error_message=str(e))
            raise Exception(f"今日一句生成失败：{e}")

    def _complete_sync_messages(
        self,
        messages: list,
        max_tokens: int,
        scene: str = "default",
        timeout: Optional[float] = None,
    ) -> str:
        t0 = time.time()
        system = next((m["content"] for m in messages if m.get("role") == "system"), None)
        user_messages = [m for m in messages if m.get("role") != "system"]
        kwargs = {"model": _active_model(), "max_tokens": max_tokens, "messages": user_messages}
        if system:
            kwargs["system"] = system
        if timeout is not None:
            kwargs["timeout"] = timeout
        try:
            response = self.client.messages.create(**kwargs)
            result = response.content[0].text
            elapsed = time.time() - t0
            log_llm_call(scene, "anthropic", _active_model(), messages, result,
                         total_ms=int(elapsed * 1000))
            return result
        except Exception as e:
            elapsed = time.time() - t0
            log_llm_call(scene, "anthropic", _active_model(), messages, "",
                         total_ms=int(elapsed * 1000), status="error", error_message=str(e))
            raise


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
        logger.info("调用 %s chat model=%s history_turns=%d", self.provider, _active_model(), len(history))
        t0 = time.time()
        try:
            messages = (
                [{"role": "system", "content": SYSTEM_PROMPT}]
                + history
                + [{"role": "user", "content": message}]
            )
            response = self.client.chat.completions.create(
                model=_active_model(),
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

    async def chat_stream(self, message: str, history: list[dict]) -> AsyncGenerator[str, None]:
        logger.info("调用 %s chat_stream model=%s history_turns=%d", self.provider, _active_model(), len(history))
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history
            + [{"role": "user", "content": message}]
        )
        resp = self.client.chat.completions.create(
            model=_active_model(), max_tokens=MAX_TOKENS, stream=True,
            messages=messages
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def chat_stream_messages(self, messages: list[dict], scene: str = "default") -> AsyncGenerator[str, None]:
        logger.info("调用 %s chat_stream_messages model=%s", self.provider, _active_model())
        sl = StreamLogger(scene, self.provider, _active_model(), messages)
        try:
            resp = self.client.chat.completions.create(
                model=_active_model(), max_tokens=MAX_TOKENS, stream=True,
                messages=messages
            )
            for chunk in resp:
                delta = chunk.choices[0].delta.content
                if delta:
                    sl.on_chunk(delta)
                    yield delta
            sl.finish()
        except Exception as e:
            sl.finish(status="error", error_message=str(e))
            raise

    def generate_summary(self, history: list[dict]) -> str:
        logger.info("调用 %s summary model=%s", self.provider, _active_model())
        t0 = time.time()
        messages = [{"role": "user", "content": SUMMARY_PROMPT + self._format_history(history)}]
        try:
            response = self.client.chat.completions.create(
                model=_active_model(),
                max_tokens=256,
                messages=messages,
            )
            elapsed = time.time() - t0
            result = response.choices[0].message.content
            logger.info("%s summary 完成 耗时=%.2fs", self.provider, elapsed)
            log_llm_call("summary", self.provider, _active_model(), messages, result,
                         total_ms=int(elapsed * 1000))
            return result
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("%s summary 失败 耗时=%.2fs error=%s", self.provider, elapsed, e, exc_info=True)
            log_llm_call("summary", self.provider, _active_model(), messages, "",
                         total_ms=int(elapsed * 1000), status="error", error_message=str(e))
            raise Exception(f"今日一句生成失败（{self.provider}）：{e}")

    def _complete_sync_messages(
        self,
        messages: list,
        max_tokens: int,
        scene: str = "default",
        timeout: Optional[float] = None,
    ) -> str:
        t0 = time.time()
        kwargs = {
            "model": _active_model(),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        try:
            response = self.client.chat.completions.create(**kwargs)
            result = response.choices[0].message.content
            elapsed = time.time() - t0
            log_llm_call(scene, self.provider, _active_model(), messages, result,
                         total_ms=int(elapsed * 1000))
            return result
        except Exception as e:
            elapsed = time.time() - t0
            log_llm_call(scene, self.provider, _active_model(), messages, "",
                         total_ms=int(elapsed * 1000), status="error", error_message=str(e))
            raise


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


# V0.2a 别名
get_model_client = get_client


# ──────────────────────────────────────────────
# 按场景获取客户端（支持不同场景用不同模型）
# ──────────────────────────────────────────────
def get_scene_client(scene: str = "default") -> tuple[BaseModelClient, str]:
    """
    返回 (client, model_name)。
    调用方用返回的 model_name 覆盖请求中的 model 参数。

    用法:
        client, model = get_scene_client("explain")
        # 然后在调用时传 model=model 而非全局 MODEL_NAME
    """
    provider, model_name = get_scene_model(scene)
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"不支持的 provider: '{provider}'")
    if provider == "anthropic":
        return AnthropicClient(), model_name
    else:
        return OpenAICompatibleClient(provider), model_name