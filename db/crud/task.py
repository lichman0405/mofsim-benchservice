"""
任务 CRUD 操作

处理任务相关的数据库操作
"""
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update, func, desc, and_, or_
from sqlalchemy.orm import Session

from db.models import Task, Structure, TaskStatus, TaskType, TaskPriority
from core.scheduler import TaskState, TaskLifecycle


class TaskCRUD:
    """任务 CRUD 操作"""
    
    @staticmethod
    def create(
        db: Session,
        task_type: TaskType,
        model_name: str,
        structure_id: Optional[UUID] = None,
        structure_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        callback_url: Optional[str] = None,
        callback_events: Optional[List[str]] = None,
    ) -> Task:
        """
        创建任务
        
        Args:
            db: 数据库会话
            task_type: 任务类型
            model_name: 模型名称
            structure_id: 结构 ID（可选）
            structure_name: 结构名称
            parameters: 任务参数
            priority: 优先级
            callback_url: 回调 URL
            callback_events: 回调事件列表
        
        Returns:
            创建的任务对象
        """
        task = Task(
            task_type=task_type,
            status=TaskStatus.PENDING,
            priority=priority,
            model_name=model_name,
            structure_id=structure_id,
            structure_name=structure_name,
            parameters=parameters or {},
            callback_url=callback_url,
            callback_events=callback_events,
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return task
    
    @staticmethod
    def get_by_id(db: Session, task_id: UUID) -> Optional[Task]:
        """根据 ID 获取任务"""
        return db.query(Task).filter(Task.id == task_id).first()
    
    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        model_name: Optional[str] = None,
        priority: Optional[TaskPriority] = None,
    ) -> Tuple[List[Task], int]:
        """
        获取任务列表
        
        Returns:
            (任务列表, 总数)
        """
        query = db.query(Task)
        
        # 应用过滤条件
        if status:
            query = query.filter(Task.status == status)
        if task_type:
            query = query.filter(Task.task_type == task_type)
        if model_name:
            query = query.filter(Task.model_name == model_name)
        if priority:
            query = query.filter(Task.priority == priority)
        
        # 计算总数
        total = query.count()
        
        # 分页和排序
        tasks = query.order_by(desc(Task.created_at)) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()
        
        return tasks, total
    
    @staticmethod
    def update_status(
        db: Session,
        task_id: UUID,
        new_status: TaskStatus,
        error_message: Optional[str] = None,
        gpu_id: Optional[int] = None,
        celery_task_id: Optional[str] = None,
    ) -> Optional[Task]:
        """
        更新任务状态
        
        会自动更新相应的时间戳
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        # 验证状态转换
        old_status = TaskState(task.status.value)
        new_state = TaskState(new_status.value)
        
        if not TaskLifecycle.can_transition(old_status, new_state):
            raise ValueError(
                f"Invalid state transition: {task.status.value} -> {new_status.value}"
            )
        
        # 更新状态
        task.status = new_status
        
        # 更新时间戳
        if new_status in (TaskStatus.RUNNING, TaskStatus.ASSIGNED):
            if task.started_at is None:
                task.started_at = datetime.utcnow()
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, 
                           TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = (
                    task.completed_at - task.started_at
                ).total_seconds()
        
        # 更新其他字段
        if error_message:
            task.error_message = error_message
        if gpu_id is not None:
            task.gpu_id = gpu_id
        if celery_task_id:
            task.celery_task_id = celery_task_id
        
        db.commit()
        db.refresh(task)
        
        return task
    
    @staticmethod
    def update_result(
        db: Session,
        task_id: UUID,
        result: Dict[str, Any],
        output_files: Optional[Dict[str, str]] = None,
        peak_memory_mb: Optional[int] = None,
    ) -> Optional[Task]:
        """更新任务结果"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        task.result = result
        if output_files:
            task.output_files = output_files
        if peak_memory_mb:
            task.peak_memory_mb = peak_memory_mb
        
        db.commit()
        db.refresh(task)
        
        return task
    
    @staticmethod
    def cancel(db: Session, task_id: UUID) -> Optional[Task]:
        """取消任务"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        # 检查是否可取消
        old_status = TaskState(task.status.value)
        if not TaskLifecycle.can_cancel(old_status):
            raise ValueError(f"Cannot cancel task in {task.status.value} state")
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        if task.started_at:
            task.duration_seconds = (
                task.completed_at - task.started_at
            ).total_seconds()
        
        db.commit()
        db.refresh(task)
        
        return task
    
    @staticmethod
    def get_pending_tasks(db: Session, limit: int = 100) -> List[Task]:
        """获取待处理的任务"""
        return db.query(Task) \
            .filter(Task.status == TaskStatus.PENDING) \
            .order_by(Task.priority, Task.created_at) \
            .limit(limit) \
            .all()
    
    @staticmethod
    def get_running_tasks(db: Session) -> List[Task]:
        """获取运行中的任务"""
        return db.query(Task) \
            .filter(Task.status == TaskStatus.RUNNING) \
            .all()
    
    @staticmethod
    def count_by_status(db: Session) -> Dict[str, int]:
        """按状态统计任务数量"""
        results = db.query(Task.status, func.count(Task.id)) \
            .group_by(Task.status) \
            .all()
        
        return {status.value: count for status, count in results}
    
    @staticmethod
    def get_today_completed_count(db: Session) -> int:
        """获取今日完成的任务数"""
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        return db.query(func.count(Task.id)) \
            .filter(
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= today_start
            ) \
            .scalar()
    
    @staticmethod
    def bulk_create(
        db: Session,
        tasks_data: List[Dict[str, Any]]
    ) -> List[Task]:
        """
        批量创建任务
        
        Args:
            db: 数据库会话
            tasks_data: 任务数据列表，每个包含:
                - task_type
                - model_name
                - structure_id (optional)
                - structure_name (optional)
                - parameters (optional)
                - priority (optional)
        
        Returns:
            创建的任务列表
        """
        tasks = []
        for data in tasks_data:
            task = Task(
                task_type=data["task_type"],
                status=TaskStatus.PENDING,
                priority=data.get("priority", TaskPriority.NORMAL),
                model_name=data["model_name"],
                structure_id=data.get("structure_id"),
                structure_name=data.get("structure_name"),
                parameters=data.get("parameters", {}),
                callback_url=data.get("callback_url"),
                callback_events=data.get("callback_events"),
            )
            tasks.append(task)
        
        db.add_all(tasks)
        db.commit()
        
        # 刷新获取 ID
        for task in tasks:
            db.refresh(task)
        
        return tasks
