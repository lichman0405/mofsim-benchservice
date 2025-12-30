"""
任务基类

提供通用的任务生命周期管理
"""
from typing import Dict, Any, Optional
import time

from celery import Task
import structlog

logger = structlog.get_logger(__name__)


class BaseModelTask(Task):
    """
    模型任务基类
    
    提供:
    - GPU 资源管理
    - 模型加载/卸载
    - 状态更新
    - 错误处理
    """
    abstract = True
    
    # 任务绑定
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    max_retries = 3
    
    _model = None
    _gpu_id = None
    
    def before_start(self, task_id, args, kwargs):
        """任务开始前"""
        logger.info(
            "task_starting",
            task_id=task_id,
            task_name=self.name,
        )
        self._start_time = time.perf_counter()
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """任务完成后"""
        duration = time.perf_counter() - getattr(self, "_start_time", 0)
        logger.info(
            "task_completed",
            task_id=task_id,
            status=status,
            duration_seconds=round(duration, 2),
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败"""
        logger.error(
            "task_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试"""
        logger.warning(
            "task_retrying",
            task_id=task_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
    
    def load_model(self, model_name: str, gpu_id: int) -> Any:
        """
        加载模型到 GPU
        
        TODO: Phase 2 实现
        """
        raise NotImplementedError("Phase 2 实现")
    
    def unload_model(self):
        """
        卸载模型
        
        TODO: Phase 2 实现
        """
        pass
    
    def update_task_status(self, task_id: str, status: str, **kwargs):
        """
        更新任务状态到数据库
        
        TODO: Phase 2 实现
        """
        pass
