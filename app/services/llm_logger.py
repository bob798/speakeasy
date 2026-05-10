"""LLM 调用日志记录器 — 完整记录模型输入输出，为模型选型对比提供数据"""

import json
import time
from typing import Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, LlmCallLog
from app.logger import get_logger

logger = get_logger("llm_logger")


def log_llm_call(
    scene: str,
    provider: str,
    model: str,
    input_messages: list,
    output_text: str,
    stream: bool = False,
    ttft_ms: Optional[int] = None,
    total_ms: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    status: str = "ok",
    error_message: Optional[str] = None,
):
    """写入一条 LLM 调用日志到 llm_call_logs 表"""
    try:
        with OrmSession(engine) as s:
            s.add(LlmCallLog(
                scene=scene,
                provider=provider,
                model=model,
                input_messages=json.dumps(input_messages, ensure_ascii=False),
                output_text=output_text,
                stream=stream,
                ttft_ms=ttft_ms,
                total_ms=total_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                status=status,
                error_message=error_message,
            ))
            s.commit()
    except Exception as e:
        logger.warning("写入 LLM 日志失败: %s", e)


class StreamLogger:
    """流式调用的日志收集器：在流结束后一次性写入"""

    def __init__(self, scene: str, provider: str, model: str, input_messages: list):
        self.scene = scene
        self.provider = provider
        self.model = model
        self.input_messages = input_messages
        self.t0 = time.time()
        self.ttft_ms: Optional[int] = None
        self._chunks: list[str] = []

    def on_first_token(self):
        if self.ttft_ms is None:
            self.ttft_ms = int((time.time() - self.t0) * 1000)

    def on_chunk(self, text: str):
        if self.ttft_ms is None:
            self.on_first_token()
        self._chunks.append(text)

    def finish(self, status: str = "ok", error_message: Optional[str] = None):
        total_ms = int((time.time() - self.t0) * 1000)
        output_text = "".join(self._chunks)
        log_llm_call(
            scene=self.scene,
            provider=self.provider,
            model=self.model,
            input_messages=self.input_messages,
            output_text=output_text,
            stream=True,
            ttft_ms=self.ttft_ms,
            total_ms=total_ms,
            status=status,
            error_message=error_message,
        )
        logger.info(
            "LLM stream done scene=%s model=%s ttft=%sms total=%dms output_len=%d",
            self.scene, self.model,
            self.ttft_ms if self.ttft_ms is not None else "N/A",
            total_ms, len(output_text),
        )
