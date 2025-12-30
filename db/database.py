"""
数据库连接配置

参考文档: docs/architecture/database_design.md 第二节
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import get_settings

settings = get_settings()

# 创建数据库引擎
engine = create_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_pre_ping=True,  # 连接健康检查
    echo=settings.debug,  # 调试模式下打印 SQL
)

# 创建会话工厂
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# 声明基类
Base = declarative_base()
