"""Amor 结构化日志模块.

框架内统一使用:
    from amor.logging import get_logger
    logger = get_logger(__name__)
    logger.info("node_start", extra={"node_id": "think", "step": 3})
"""

from __future__ import annotations
import logging


def get_logger(name: str | None = None):
    """获取 Amor 框架 logger.

    Args:
        name: logger 名称，默认 "amor"，子模块传 __name__ 自动为 "amor.xxx"

    Returns:
        配置好的 Logger 实例
    """
    logger_name = name if name else "amor"
    logger = logging.getLogger(logger_name)

    # 避免重复添加
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(AmorFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


class AmorFormatter(logging.Formatter):
    """结构化日志格式化器.

    输出格式:
        [2026-06-27 10:30:00] amor.graph.compiled INFO  node_start  node_id=think step=3
    """

    def format(self, record: logging.LogRecord) -> str:
        extra_parts = ""
        if record.__dict__.get("extra"):
            extras = record.__dict__["extra"]
            if isinstance(extras,dict):
                extra_parts = "  " + " ".join(
                    f"{k}={v}"for k,v in extras.items()
                )

        return (
            f"[{self.formatTime(record,self.default_time_format)}]"
            f"{record.name} {record.levelname:<7} "
            f"{record.getMessage()}{extra_parts}"
        )