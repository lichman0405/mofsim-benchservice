"""
Task 任务对象

提供任务的高级封装，支持等待、日志流等功能。
"""

from __future__ import annotations

import time
import asyncio
from typing import Optional, Dict, Any, Callable, Iterator, AsyncIterator, TYPE_CHECKING

from .models import TaskInfo, TaskResult, TaskStatus
from .exceptions import TaskFailedError, TaskTimeoutError, TaskCancelledError

if TYPE_CHECKING:
    from .client import MOFSimClient
    from .async_client import AsyncMOFSimClient


class Task:
    """
    任务对象
    
    封装任务的各种操作，提供便捷的方法来等待、取消、获取日志等。
    
    Example:
        ```python
        task = client.submit_optimization(...)
        
        # 等待完成
        result = task.wait(timeout=3600)
        
        # 或者流式获取日志
        for log in task.stream_logs():
            print(log)
        ```
    """
    
    def __init__(
        self,
        task_info: TaskInfo,
        client: "MOFSimClient",
    ):
        self._info = task_info
        self._client = client
        self._result: Optional[TaskResult] = None
    
    @property
    def task_id(self) -> str:
        """任务 ID"""
        return self._info.task_id
    
    @property
    def task_type(self) -> str:
        """任务类型"""
        return self._info.task_type
    
    @property
    def status(self) -> str:
        """当前状态"""
        return self._info.status
    
    @property
    def model(self) -> str:
        """使用的模型"""
        return self._info.model
    
    @property
    def priority(self) -> str:
        """任务优先级"""
        return self._info.priority
    
    @property
    def progress(self) -> float:
        """执行进度 (0-100)"""
        return self._info.progress
    
    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self._info.is_terminal
    
    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self._info.is_success
    
    @property
    def error_message(self) -> Optional[str]:
        """错误信息"""
        return self._info.error_message
    
    @property
    def info(self) -> TaskInfo:
        """获取任务完整信息"""
        return self._info
    
    def refresh(self) -> "Task":
        """
        刷新任务状态
        
        Returns:
            self，方便链式调用
        """
        self._info = self._client.get_task_info(self.task_id)
        return self
    
    def wait(
        self,
        timeout: float = 3600.0,
        poll_interval: float = 5.0,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> TaskResult:
        """
        等待任务完成
        
        Args:
            timeout: 最大等待时间（秒）
            poll_interval: 状态轮询间隔（秒）
            on_progress: 进度回调函数
        
        Returns:
            TaskResult 任务结果
            
        Raises:
            TaskTimeoutError: 等待超时
            TaskFailedError: 任务执行失败
            TaskCancelledError: 任务被取消
        """
        start_time = time.time()
        last_progress = -1.0
        
        while time.time() - start_time < timeout:
            self.refresh()
            
            # 进度回调
            if on_progress and self.progress != last_progress:
                on_progress(self.progress)
                last_progress = self.progress
            
            # 检查终态
            if self.is_terminal:
                if self.status == "COMPLETED":
                    return self.get_result()
                elif self.status == "FAILED":
                    raise TaskFailedError(self.task_id, self.error_message)
                elif self.status == "CANCELLED":
                    raise TaskCancelledError(self.task_id)
                elif self.status == "TIMEOUT":
                    raise TaskTimeoutError(self.task_id, timeout)
            
            time.sleep(poll_interval)
        
        raise TaskTimeoutError(self.task_id, timeout)
    
    def get_result(self) -> TaskResult:
        """
        获取任务结果
        
        Returns:
            TaskResult 任务结果
            
        Raises:
            RuntimeError: 任务尚未完成
        """
        if self._result is not None:
            return self._result
        
        if not self.is_terminal:
            self.refresh()
            if not self.is_terminal:
                raise RuntimeError(f"Task {self.task_id} is not completed yet")
        
        self._result = self._client.get_task_result(self.task_id)
        return self._result
    
    def cancel(self) -> bool:
        """
        取消任务
        
        Returns:
            是否成功取消
        """
        if self.is_terminal:
            return False
        
        success = self._client.cancel_task(self.task_id)
        if success:
            self.refresh()
        return success
    
    def get_logs(
        self,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        获取任务日志
        
        Args:
            level: 日志级别过滤 (DEBUG, INFO, WARNING, ERROR)
            limit: 最大返回条数
        
        Returns:
            日志列表
        """
        return self._client.get_task_logs(self.task_id, level=level, limit=limit)
    
    def stream_logs(
        self,
        timeout: float = 3600.0,
    ) -> Iterator[Dict[str, Any]]:
        """
        流式获取任务日志
        
        使用 SSE (Server-Sent Events) 实时获取日志。
        
        Args:
            timeout: 流超时时间
        
        Yields:
            日志条目
        """
        yield from self._client.stream_task_logs(self.task_id, timeout=timeout)
    
    def __repr__(self) -> str:
        return f"Task(id={self.task_id!r}, type={self.task_type!r}, status={self.status!r})"
    
    def __str__(self) -> str:
        return f"Task {self.task_id} [{self.status}]"


class AsyncTask:
    """
    异步任务对象
    
    与 Task 类似，但所有方法都是异步的。
    
    Example:
        ```python
        task = await client.submit_optimization(...)
        result = await task.wait()
        ```
    """
    
    def __init__(
        self,
        task_info: TaskInfo,
        client: "AsyncMOFSimClient",
    ):
        self._info = task_info
        self._client = client
        self._result: Optional[TaskResult] = None
    
    @property
    def task_id(self) -> str:
        """任务 ID"""
        return self._info.task_id
    
    @property
    def task_type(self) -> str:
        """任务类型"""
        return self._info.task_type
    
    @property
    def status(self) -> str:
        """当前状态"""
        return self._info.status
    
    @property
    def model(self) -> str:
        """使用的模型"""
        return self._info.model
    
    @property
    def priority(self) -> str:
        """任务优先级"""
        return self._info.priority
    
    @property
    def progress(self) -> float:
        """执行进度 (0-100)"""
        return self._info.progress
    
    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self._info.is_terminal
    
    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self._info.is_success
    
    @property
    def error_message(self) -> Optional[str]:
        """错误信息"""
        return self._info.error_message
    
    @property
    def info(self) -> TaskInfo:
        """获取任务完整信息"""
        return self._info
    
    async def refresh(self) -> "AsyncTask":
        """刷新任务状态"""
        self._info = await self._client.get_task_info(self.task_id)
        return self
    
    async def wait(
        self,
        timeout: float = 3600.0,
        poll_interval: float = 5.0,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> TaskResult:
        """
        异步等待任务完成
        
        Args:
            timeout: 最大等待时间（秒）
            poll_interval: 状态轮询间隔（秒）
            on_progress: 进度回调函数
        
        Returns:
            TaskResult 任务结果
        """
        start_time = time.time()
        last_progress = -1.0
        
        while time.time() - start_time < timeout:
            await self.refresh()
            
            # 进度回调
            if on_progress and self.progress != last_progress:
                on_progress(self.progress)
                last_progress = self.progress
            
            # 检查终态
            if self.is_terminal:
                if self.status == "COMPLETED":
                    return await self.get_result()
                elif self.status == "FAILED":
                    raise TaskFailedError(self.task_id, self.error_message)
                elif self.status == "CANCELLED":
                    raise TaskCancelledError(self.task_id)
                elif self.status == "TIMEOUT":
                    raise TaskTimeoutError(self.task_id, timeout)
            
            await asyncio.sleep(poll_interval)
        
        raise TaskTimeoutError(self.task_id, timeout)
    
    async def get_result(self) -> TaskResult:
        """获取任务结果"""
        if self._result is not None:
            return self._result
        
        if not self.is_terminal:
            await self.refresh()
            if not self.is_terminal:
                raise RuntimeError(f"Task {self.task_id} is not completed yet")
        
        self._result = await self._client.get_task_result(self.task_id)
        return self._result
    
    async def cancel(self) -> bool:
        """取消任务"""
        if self.is_terminal:
            return False
        
        success = await self._client.cancel_task(self.task_id)
        if success:
            await self.refresh()
        return success
    
    async def get_logs(
        self,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """获取任务日志"""
        return await self._client.get_task_logs(self.task_id, level=level, limit=limit)
    
    async def stream_logs(
        self,
        timeout: float = 3600.0,
    ) -> AsyncIterator[Dict[str, Any]]:
        """异步流式获取任务日志"""
        async for log in self._client.stream_task_logs(self.task_id, timeout=timeout):
            yield log
    
    def __repr__(self) -> str:
        return f"AsyncTask(id={self.task_id!r}, type={self.task_type!r}, status={self.status!r})"
    
    def __str__(self) -> str:
        return f"AsyncTask {self.task_id} [{self.status}]"


# Re-export for convenience
__all__ = ["Task", "AsyncTask", "TaskResult", "TaskStatus"]
