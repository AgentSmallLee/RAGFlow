"""
日志工具模块
使用 loguru 提供统一的日志输出
"""

import sys
from loguru import logger


def setup_logger(level: str = "INFO") -> None:
    """
    配置日志输出格式和级别

    Args:
        level: 日志级别，可选 DEBUG / INFO / WARNING / ERROR / CRITICAL
    """
    # 移除默认配置
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        enqueue=True,
    )


# 初始化默认日志
setup_logger()

__all__ = ["logger", "setup_logger"]
