"""
FastAPI 依赖注入

参考文档: docs/engineering_requirements.md 第五节
"""
from typing import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from core.config import Settings
from db.database import SessionLocal


@lru_cache()
def get_settings() -> Settings:
    """获取配置（缓存单例）"""
    return Settings()


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    
    使用方式:
    @app.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 占位符 - 后续实现
def get_current_user():
    """获取当前用户（认证后实现）"""
    # TODO: Phase 4 实现认证
    pass


def get_celery_app():
    """获取 Celery 应用"""
    from workers.celery_app import celery_app
    return celery_app


def get_redis_client():
    """获取 Redis 客户端"""
    # TODO: Phase 2 实现
    pass
