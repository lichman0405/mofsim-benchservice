"""
任务服务层

处理任务相关的业务逻辑
"""
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
import structlog

from db.models import Task, TaskStatus, TaskType, TaskPriority
from db.crud import TaskCRUD
from core.scheduler import (
    PriorityQueue, MockPriorityQueue, 
    TaskPriority as SchedulerPriority,
    GPUManager,
    Scheduler,
    TaskLifecycle,
    TaskState,
)
from api.middleware.error_handler import TaskNotFoundError, ModelNotFoundError

logger = structlog.get_logger(__name__)


# 支持的模型列表
SUPPORTED_MODELS = [
    "mace-mp-0-medium",
    "mace-mp-0-large", 
    "mace-omat-0-medium",
    "mace-omat-0-large",
    "orb-v2",
    "sevennet-0",
    "mattersim-v1-1m",
    "mattersim-v1-5m",
    "grace-2l-oam",
]


class TaskService:
    """任务服务"""
    
    def __init__(
        self,
        db: Session,
        queue: Optional[PriorityQueue] = None,
        gpu_manager: Optional[GPUManager] = None,
    ):
        self.db = db
        self.queue = queue
        self.gpu_manager = gpu_manager
    
    def validate_model(self, model_name: str) -> bool:
        """验证模型是否支持"""
        if model_name not in SUPPORTED_MODELS:
            raise ModelNotFoundError(model_name)
        return True
    
    def _map_priority(self, priority: TaskPriority) -> SchedulerPriority:
        """映射数据库优先级到调度器优先级"""
        mapping = {
            TaskPriority.CRITICAL: SchedulerPriority.CRITICAL,
            TaskPriority.HIGH: SchedulerPriority.HIGH,
            TaskPriority.NORMAL: SchedulerPriority.NORMAL,
            TaskPriority.LOW: SchedulerPriority.LOW,
        }
        return mapping.get(priority, SchedulerPriority.NORMAL)
    
    def submit_task(
        self,
        task_type: TaskType,
        model_name: str,
        structure_id: Optional[UUID] = None,
        structure_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        callback_url: Optional[str] = None,
        callback_events: Optional[List[str]] = None,
        timeout: Optional[int] = None,
    ) -> Task:
        """
        提交任务
        
        1. 验证参数
        2. 创建数据库记录
        3. 加入优先级队列
        4. 返回任务信息
        """
        # 验证模型
        self.validate_model(model_name)
        
        # 添加超时到参数
        if timeout:
            parameters = parameters or {}
            parameters["timeout"] = timeout
        
        # 创建任务
        task = TaskCRUD.create(
            db=self.db,
            task_type=task_type,
            model_name=model_name,
            structure_id=structure_id,
            structure_name=structure_name,
            parameters=parameters,
            priority=priority,
            callback_url=callback_url,
            callback_events=callback_events,
        )
        
        logger.info(
            "task_created",
            task_id=str(task.id),
            task_type=task_type.value,
            model=model_name,
            priority=priority.value,
        )
        
        # 加入队列
        if self.queue:
            try:
                scheduler_priority = self._map_priority(priority)
                self.queue.enqueue(
                    str(task.id),
                    priority=scheduler_priority,
                    metadata={
                        "task_type": task_type.value,
                        "model_name": model_name,
                    }
                )
                
                # 更新状态为 QUEUED
                TaskCRUD.update_status(self.db, task.id, TaskStatus.QUEUED)
                task.status = TaskStatus.QUEUED
                
            except Exception as e:
                logger.error(
                    "queue_enqueue_failed",
                    task_id=str(task.id),
                    error=str(e)
                )
        
        return task
    
    def get_task(self, task_id: UUID) -> Task:
        """获取任务详情"""
        task = TaskCRUD.get_by_id(self.db, task_id)
        if not task:
            raise TaskNotFoundError(str(task_id))
        return task
    
    def get_task_with_queue_position(self, task_id: UUID) -> Tuple[Task, Optional[int]]:
        """获取任务详情及队列位置"""
        task = self.get_task(task_id)
        
        position = None
        if self.queue and task.status == TaskStatus.QUEUED:
            position = self.queue.position(str(task_id))
        
        return task, position
    
    def get_task_result(self, task_id: UUID) -> Task:
        """获取任务结果"""
        task = self.get_task(task_id)
        
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            raise ValueError(f"Task {task_id} is not finished yet")
        
        return task
    
    def _map_status_to_state(self, status: TaskStatus) -> TaskState:
        """映射数据库状态到调度器状态"""
        mapping = {
            TaskStatus.PENDING: TaskState.PENDING,
            TaskStatus.QUEUED: TaskState.QUEUED,
            TaskStatus.ASSIGNED: TaskState.ASSIGNED,
            TaskStatus.RUNNING: TaskState.RUNNING,
            TaskStatus.COMPLETED: TaskState.COMPLETED,
            TaskStatus.FAILED: TaskState.FAILED,
            TaskStatus.CANCELLED: TaskState.CANCELLED,
            TaskStatus.TIMEOUT: TaskState.TIMEOUT,
        }
        return mapping.get(status, TaskState.PENDING)
    
    def cancel_task(self, task_id: UUID) -> Task:
        """
        取消任务
        
        1. 检查任务状态
        2. 从队列移除（如果在队列中）
        3. 如果正在运行，发送取消信号
        4. 更新数据库状态
        """
        task = self.get_task(task_id)
        
        # 检查是否可取消
        current_state = self._map_status_to_state(task.status)
        if not TaskLifecycle.can_cancel(current_state):
            raise ValueError(f"Cannot cancel task in {task.status.value} state")
        
        # 从队列移除
        if self.queue and task.status == TaskStatus.QUEUED:
            self.queue.remove(str(task_id))
        
        # 如果正在运行，需要通知 Celery 取消
        if task.status == TaskStatus.RUNNING and task.celery_task_id:
            try:
                from workers.celery_app import celery_app
                celery_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info(
                    "celery_task_revoked",
                    task_id=str(task_id),
                    celery_task_id=task.celery_task_id
                )
            except Exception as e:
                logger.warning(
                    "celery_revoke_failed",
                    task_id=str(task_id),
                    error=str(e)
                )
        
        # 更新状态
        task = TaskCRUD.cancel(self.db, task_id)
        
        logger.info(
            "task_cancelled",
            task_id=str(task_id),
            previous_status=current_state.value
        )
        
        return task
    
    def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[List[Task], int]:
        """获取任务列表"""
        # 转换枚举
        status_enum = TaskStatus(status) if status else None
        task_type_enum = TaskType(task_type) if task_type else None
        
        return TaskCRUD.get_list(
            db=self.db,
            page=page,
            page_size=page_size,
            status=status_enum,
            task_type=task_type_enum,
            model_name=model_name,
        )
    
    def submit_batch(
        self,
        task_type: TaskType,
        tasks_data: List[Dict[str, Any]],
    ) -> Tuple[List[Task], List[Dict[str, Any]]]:
        """
        批量提交任务
        
        Returns:
            (成功的任务列表, 失败详情列表)
        """
        successful_tasks = []
        errors = []
        
        for i, data in enumerate(tasks_data):
            try:
                # 验证模型
                model_name = data.get("model")
                self.validate_model(model_name)
                
                task = self.submit_task(
                    task_type=task_type,
                    model_name=model_name,
                    structure_id=data.get("structure", {}).get("file_id"),
                    structure_name=data.get("structure", {}).get("name"),
                    parameters=data.get("parameters", {}),
                    priority=TaskPriority(data.get("options", {}).get("priority", "NORMAL")),
                    callback_url=(data.get("options", {}).get("callback") or {}).get("url"),
                    callback_events=(data.get("options", {}).get("callback") or {}).get("events"),
                    timeout=data.get("options", {}).get("timeout"),
                )
                successful_tasks.append(task)
                
            except Exception as e:
                errors.append({
                    "index": i,
                    "error": str(e),
                    "data": data,
                })
                logger.warning(
                    "batch_task_failed",
                    index=i,
                    error=str(e)
                )
        
        return successful_tasks, errors
    
    def get_queue_position(self, task_id: UUID) -> Optional[int]:
        """获取任务在队列中的位置"""
        if self.queue:
            return self.queue.position(str(task_id))
        return None
    
    def estimate_wait_time(self, position: int) -> int:
        """估算等待时间（秒）"""
        # 简单估算：每个任务平均 5 分钟
        AVG_TASK_TIME = 300
        return position * AVG_TASK_TIME
    
    def get_stats(self) -> Dict[str, Any]:
        """获取任务统计"""
        status_counts = TaskCRUD.count_by_status(self.db)
        today_completed = TaskCRUD.get_today_completed_count(self.db)
        
        return {
            "by_status": status_counts,
            "today_completed": today_completed,
            "queue_size": self.queue.size() if self.queue else 0,
        }
