"""
Celery 应用配置

参考文档: docs/architecture/async_task_design.md 2.1 节
"""
from celery import Celery
from kombu import Queue, Exchange
import os

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
        "workers.tasks.maintenance",
    ]
)

# 定义优先级队列
# 使用 x-max-priority 支持队列内优先级
default_exchange = Exchange("default", type="direct")

task_queues = [
    Queue("critical", default_exchange, routing_key="critical", 
          queue_arguments={"x-max-priority": 10}),
    Queue("high", default_exchange, routing_key="high",
          queue_arguments={"x-max-priority": 10}),
    Queue("default", default_exchange, routing_key="default",
          queue_arguments={"x-max-priority": 10}),
    Queue("low", default_exchange, routing_key="low",
          queue_arguments={"x-max-priority": 10}),
]

# 为每个 GPU 创建专用队列
gpu_id = os.environ.get("MOFSIM_WORKER_GPU_ID")
if gpu_id is not None:
    task_queues.append(
        Queue(f"gpu-{gpu_id}", default_exchange, routing_key=f"gpu-{gpu_id}",
              queue_arguments={"x-max-priority": 10})
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
    worker_concurrency=1,  # 每个 Worker 只执行一个任务
    
    # 结果过期
    result_expires=86400 * 7,  # 7 天
    
    # 任务队列
    task_queues=task_queues,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    
    # 任务追踪
    task_track_started=True,
    
    # 重试配置
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # 结果后端配置
    result_extended=True,  # 存储更多任务信息
)

# 任务路由函数
def route_task(name, args, kwargs, options, task=None, **kw):
    """动态路由任务到指定队列"""
    # 检查是否指定了 GPU
    gpu_id = kwargs.get("gpu_id") or options.get("gpu_id")
    if gpu_id is not None:
        return {"queue": f"gpu-{gpu_id}", "routing_key": f"gpu-{gpu_id}"}
    
    # 检查优先级
    priority = kwargs.get("priority") or options.get("priority", "normal")
    priority_map = {
        "critical": "critical",
        "high": "high",
        "normal": "default",
        "low": "low",
    }
    queue = priority_map.get(priority.lower(), "default")
    return {"queue": queue, "routing_key": queue}


celery_app.conf.task_routes = (route_task,)

# 定时任务 (可选)
celery_app.conf.beat_schedule = {
    # 清理过期任务 - 每小时
    "cleanup-expired-tasks": {
        "task": "workers.tasks.maintenance.cleanup_expired",
        "schedule": 3600.0,
    },
    # GPU 状态刷新 - 每 30 秒
    "refresh-gpu-status": {
        "task": "workers.tasks.maintenance.refresh_gpu_status",
        "schedule": 30.0,
    },
}


# Worker 启动时的初始化
@celery_app.on_after_configure.connect
def setup_worker_signals(sender, **kwargs):
    """配置 Worker 信号"""
    from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun
    
    @worker_ready.connect
    def on_worker_ready(sender, **kwargs):
        """Worker 启动完成"""
        import structlog
        logger = structlog.get_logger(__name__)
        
        worker_id = os.environ.get("MOFSIM_WORKER_ID", "unknown")
        gpu_id = os.environ.get("MOFSIM_WORKER_GPU_ID", "none")
        
        logger.info(
            "worker_ready",
            worker_id=worker_id,
            gpu_id=gpu_id,
            hostname=sender.hostname if hasattr(sender, 'hostname') else 'unknown'
        )
    
    @worker_shutdown.connect
    def on_worker_shutdown(sender, **kwargs):
        """Worker 关闭"""
        import structlog
        logger = structlog.get_logger(__name__)
        logger.info("worker_shutdown", hostname=sender.hostname if hasattr(sender, 'hostname') else 'unknown')

