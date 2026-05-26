import logging
import os
import pathlib
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from typing import Optional

# 通过 contextvars 在异步环境中安全传递 request_id
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# 文件日志配置（VPS 部署后线上需要持久日志）
# - LOG_TO_FILE  : 是否写文件，"0"/"false" 关闭（默认开）
# - LOG_DIR      : 日志目录，默认 "logs"（docker-compose 里挂载到 /app/logs）
# - LOG_FILE     : 文件名，默认 "app.log"
# - LOG_FILE_MAX_BYTES   : 单文件上限，默认 10 MB
# - LOG_FILE_BACKUP_COUNT: 保留轮转份数，默认 5
LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "1").lower() not in {"0", "false", "no"}
LOG_DIR: str = os.getenv("LOG_DIR", "logs")
LOG_FILE: str = os.getenv("LOG_FILE", "app.log")
LOG_FILE_MAX_BYTES: int = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))

_FMT = "%(asctime)s | %(levelname)-5s | %(name)s | [%(request_id)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


class _RequestIdFormatter(logging.Formatter):
    """在每条日志里自动注入当前请求的 request_id"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get("-")
        return super().format(record)


_formatter = _RequestIdFormatter(_FMT, datefmt=_DATEFMT)
_file_handler: Optional[logging.Handler] = None
_file_handler_attempted = False


def _build_file_handler() -> Optional[logging.Handler]:
    """惰性初始化共享的文件 handler；目录创建失败时降级为 None 不阻断启动"""
    global _file_handler, _file_handler_attempted
    if _file_handler_attempted:
        return _file_handler
    _file_handler_attempted = True
    if not LOG_TO_FILE:
        return None
    try:
        log_dir = pathlib.Path(LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / LOG_FILE,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(_formatter)
        _file_handler = handler
    except OSError as e:
        # 容器/VPS 上偶发目录不可写时不要让应用起不来，记一行到 stderr 后降级到仅 stdout
        logging.getLogger(__name__).warning(
            "无法创建日志文件 %s/%s（%s）；仅输出到 stdout", LOG_DIR, LOG_FILE, e
        )
        _file_handler = None
    return _file_handler


def get_logger(name: str) -> logging.Logger:
    """返回已配置好格式和级别的 logger，避免重复添加 handler"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(_formatter)
        logger.addHandler(stream_handler)
        file_handler = _build_file_handler()
        if file_handler is not None:
            logger.addHandler(file_handler)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    return logger
