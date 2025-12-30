"""
结构化日志配置

参考文档: docs/engineering_requirements.md 6.2 节
使用 structlog 实现结构化日志

日志格式:
- 开发环境: 彩色控制台输出
- 生产环境: JSON 格式
"""
import logging
import sys
from typing import Optional

import structlog
from structlog.typing import Processor

from core.config import get_settings


def setup_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """
    配置 structlog 日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式 (json, console)
        log_file: 日志文件路径
    """
    settings = get_settings()
    
    level = level or settings.logging.level
    log_format = log_format or settings.logging.format
    log_file = log_file or settings.logging.file_path
    
    # 共享处理器
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if log_format == "json":
        # JSON 格式 - 生产环境
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # 控制台格式 - 开发环境
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # 降低第三方库日志级别
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # 文件处理器
    if log_file:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.logging.max_size_mb * 1024 * 1024,
            backupCount=settings.logging.backup_count,
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    获取 logger 实例
    
    Args:
        name: logger 名称，通常使用 __name__
    
    Returns:
        structlog BoundLogger 实例
    """
    return structlog.get_logger(name)
