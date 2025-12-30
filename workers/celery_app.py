"""
Celery 应用配置

参考文档: docs/architecture/async_task_design.md 2.1 节
"""
from celery import Celery

from core.config import get_settings

settings = get_settings()

# 创建 Celery 应用
celery_app = Celery(
    "mofsim_workers",
    broker=settings.get_celery_broker_url(),
    backend=settings.get_celery_result_backend(),
    include=[
        "workers.tasks.optimization",
        "workers.tasks.stability",
        "workers.tasks.bulk_modulus",
        "workers.tasks.heat_capacity",
        "workers.tasks.interaction_energy",
        "workers.tasks.single_point",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区
    timezone="UTC",
    enable_utc=True,
    
    # 任务超时
    task_soft_time_limit=settings.celery.task_soft_timeout,
    task_time_limit=settings.celery.task_hard_timeout,
    
    # Worker 配置
    worker_prefetch_multiplier=settings.celery.worker_prefetch,
    task_acks_late=settings.celery.task_acks_late,
    
    # 结果过期
    result_expires=86400 * 7,  # 7 天
    
    # 任务路由 - 按优先级
    task_routes={
        "workers.tasks.*": {"queue": "default"},
    },
    
    # 优先级队列
    task_queues={
        "critical": {"exchange": "critical", "routing_key": "critical"},
        "high": {"exchange": "high", "routing_key": "high"},
        "default": {"exchange": "default", "routing_key": "default"},
        "low": {"exchange": "low", "routing_key": "low"},
    },
    
    # 任务追踪
    task_track_started=True,
    
    # 重试配置
    task_default_retry_delay=60,
    task_max_retries=3,
)

# 定时任务 (可选)
celery_app.conf.beat_schedule = {
    # 清理过期任务 - 每小时
    "cleanup-expired-tasks": {
        "task": "workers.tasks.maintenance.cleanup_expired",
        "schedule": 3600.0,
    },
}
