import logging
import os
from contextvars import ContextVar

# 通过 contextvars 在异步环境中安全传递 request_id
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


class _RequestIdFormatter(logging.Formatter):
    """在每条日志里自动注入当前请求的 request_id"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get("-")
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """返回已配置好格式和级别的 logger，避免重复添加 handler"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s | %(levelname)-5s | %(name)s | [%(request_id)s] %(message)s"
        handler.setFormatter(
            _RequestIdFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    return logger
