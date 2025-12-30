"""
任务生命周期管理

处理任务状态转换和验证
参考文档: docs/architecture/async_task_design.md
"""
from enum import Enum
from typing import Optional, Set, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import time

import structlog

logger = structlog.get_logger(__name__)


class TaskState(str, Enum):
    """任务状态"""
    PENDING = "pending"       # 待处理（刚创建）
    QUEUED = "queued"         # 已入队
    ASSIGNED = "assigned"     # 已分配 GPU
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 成功完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消
    TIMEOUT = "timeout"       # 超时


@dataclass
class TaskStateTransition:
    """状态转换记录"""
    from_state: TaskState
    to_state: TaskState
    timestamp: float
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskLifecycle:
    """
    任务生命周期管理器
    
    负责：
    - 状态转换验证
    - 状态转换记录
    - 可取消状态检查
    """
    
    # 有效的状态转换
    VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
        TaskState.PENDING: {TaskState.QUEUED, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.QUEUED: {TaskState.ASSIGNED, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.ASSIGNED: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.RUNNING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.TIMEOUT},
        TaskState.COMPLETED: set(),  # 终态
        TaskState.FAILED: set(),     # 终态
        TaskState.CANCELLED: set(),  # 终态
        TaskState.TIMEOUT: set(),    # 终态
    }
    
    # 可取消的状态
    CANCELLABLE_STATES: Set[TaskState] = {
        TaskState.PENDING,
        TaskState.QUEUED,
        TaskState.ASSIGNED,
        TaskState.RUNNING,
    }
    
    # 终止状态
    TERMINAL_STATES: Set[TaskState] = {
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.TIMEOUT,
    }
    
    # 活跃状态
    ACTIVE_STATES: Set[TaskState] = {
        TaskState.PENDING,
        TaskState.QUEUED,
        TaskState.ASSIGNED,
        TaskState.RUNNING,
    }
    
    @classmethod
    def can_transition(cls, from_state: TaskState, to_state: TaskState) -> bool:
        """检查状态转换是否有效"""
        valid_targets = cls.VALID_TRANSITIONS.get(from_state, set())
        return to_state in valid_targets
    
    @classmethod
    def validate_transition(
        cls,
        from_state: TaskState,
        to_state: TaskState,
        raise_error: bool = True
    ) -> bool:
        """
        验证状态转换
        
        Args:
            from_state: 当前状态
            to_state: 目标状态
            raise_error: 是否在无效时抛出异常
        
        Returns:
            是否有效
        
        Raises:
            ValueError: 如果转换无效且 raise_error=True
        """
        if cls.can_transition(from_state, to_state):
            return True
        
        if raise_error:
            raise ValueError(
                f"Invalid state transition: {from_state.value} -> {to_state.value}"
            )
        return False
    
    @classmethod
    def can_cancel(cls, state: TaskState) -> bool:
        """检查任务是否可取消"""
        return state in cls.CANCELLABLE_STATES
    
    @classmethod
    def is_terminal(cls, state: TaskState) -> bool:
        """检查是否为终止状态"""
        return state in cls.TERMINAL_STATES
    
    @classmethod
    def is_active(cls, state: TaskState) -> bool:
        """检查是否为活跃状态"""
        return state in cls.ACTIVE_STATES
    
    @classmethod
    def create_transition(
        cls,
        from_state: TaskState,
        to_state: TaskState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        validate: bool = True
    ) -> TaskStateTransition:
        """
        创建状态转换记录
        
        Args:
            from_state: 当前状态
            to_state: 目标状态
            reason: 转换原因
            metadata: 附加元数据
            validate: 是否验证转换有效性
        
        Returns:
            TaskStateTransition 记录
        """
        if validate:
            cls.validate_transition(from_state, to_state)
        
        transition = TaskStateTransition(
            from_state=from_state,
            to_state=to_state,
            timestamp=time.time(),
            reason=reason,
            metadata=metadata
        )
        
        logger.info(
            "task_state_transition",
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason
        )
        
        return transition
    
    @classmethod
    def get_next_states(cls, state: TaskState) -> Set[TaskState]:
        """获取可能的下一个状态"""
        return cls.VALID_TRANSITIONS.get(state, set())


class TaskTimeoutManager:
    """任务超时管理器"""
    
    # 默认超时（秒）
    DEFAULT_TIMEOUT = 3600  # 1 小时
    
    # 任务类型超时配置
    TASK_TYPE_TIMEOUTS = {
        "optimization": 1800,      # 30 分钟
        "stability": 7200,         # 2 小时
        "bulk-modulus": 3600,      # 1 小时
        "heat-capacity": 7200,     # 2 小时
        "interaction-energy": 1800, # 30 分钟
        "single-point": 600,       # 10 分钟
    }
    
    # 最大允许超时
    MAX_TIMEOUT = 86400  # 24 小时
    
    @classmethod
    def get_timeout(
        cls,
        task_type: str,
        custom_timeout: Optional[int] = None
    ) -> int:
        """
        获取任务超时时间
        
        Args:
            task_type: 任务类型
            custom_timeout: 自定义超时（优先级最高）
        
        Returns:
            超时秒数
        """
        if custom_timeout is not None:
            return min(custom_timeout, cls.MAX_TIMEOUT)
        
        return cls.TASK_TYPE_TIMEOUTS.get(task_type, cls.DEFAULT_TIMEOUT)
    
    @classmethod
    def is_timed_out(
        cls,
        started_at: float,
        task_type: str,
        custom_timeout: Optional[int] = None
    ) -> bool:
        """检查任务是否超时"""
        timeout = cls.get_timeout(task_type, custom_timeout)
        elapsed = time.time() - started_at
        return elapsed > timeout
    
    @classmethod
    def time_remaining(
        cls,
        started_at: float,
        task_type: str,
        custom_timeout: Optional[int] = None
    ) -> float:
        """获取剩余时间（秒）"""
        timeout = cls.get_timeout(task_type, custom_timeout)
        elapsed = time.time() - started_at
        return max(0, timeout - elapsed)
