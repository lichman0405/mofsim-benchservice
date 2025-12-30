"""
FastAPI 依赖注入

参考文档: docs/engineering_requirements.md 第五节
"""
from typing import Generator, Optional
from functools import lru_cache

from sqlalchemy.orm import Session
from redis import Redis

from core.config import Settings, get_settings
from db.database import SessionLocal


# 全局单例存储
_redis_client: Optional[Redis] = None
_gpu_manager = None
_priority_queue = None
_scheduler = None


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


def get_redis_client() -> Optional[Redis]:
    """获取 Redis 客户端"""
    global _redis_client
    
    if _redis_client is None:
        settings = get_settings()
        try:
            _redis_client = Redis.from_url(
                settings.get_redis_url(),
                decode_responses=True
            )
            # 测试连接
            _redis_client.ping()
        except Exception:
            # Redis 不可用时返回 None
            _redis_client = None
    
    return _redis_client


def get_gpu_manager():
    """获取 GPU 管理器"""
    global _gpu_manager
    
    if _gpu_manager is None:
        from core.scheduler import GPUManager
        settings = get_settings()
        
        # 从配置中获取 GPU 设备列表
        gpu_ids = settings.gpu.device_list if settings.gpu.device_list else None
        
        _gpu_manager = GPUManager(
            gpu_ids=gpu_ids,
            reserved_gpu_ids=[],  # 可以从配置扩展
            mock_mode=not bool(gpu_ids),  # 没有配置 GPU 时使用 mock 模式
        )
    
    return _gpu_manager


def get_priority_queue():
    """获取优先级队列"""
    global _priority_queue
    
    if _priority_queue is None:
        redis_client = get_redis_client()
        
        if redis_client is None:
            # 无 Redis 时使用 Mock 队列
            from core.scheduler.priority_queue import MockPriorityQueue
            _priority_queue = MockPriorityQueue()
        else:
            from core.scheduler import PriorityQueue
            _priority_queue = PriorityQueue(redis_client)
    
    return _priority_queue


def get_scheduler():
    """获取调度器"""
    global _scheduler
    
    if _scheduler is None:
        from core.scheduler import Scheduler
        
        gpu_manager = get_gpu_manager()
        queue = get_priority_queue()
        
        _scheduler = Scheduler(
            gpu_manager=gpu_manager,
            queue=queue,
        )
    
    return _scheduler


def reset_singletons():
    """重置所有单例（用于测试）"""
    global _redis_client, _gpu_manager, _priority_queue, _scheduler
    _redis_client = None
    _gpu_manager = None
    _priority_queue = None
    _scheduler = None

