"""
任务日志服务

参考文档: docs/engineering_requirements.md 6.3-6.5 节
提供任务日志的存储、查询和实时推送功能
"""
import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, AsyncGenerator
from threading import Lock

import structlog

logger = structlog.get_logger(__name__)


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    @classmethod
    def from_string(cls, level: str) -> "LogLevel":
        """从字符串转换"""
        return cls[level.upper()]
    
    def __ge__(self, other: "LogLevel") -> bool:
        order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        return order.index(self.value) >= order.index(other.value)
    
    def __gt__(self, other: "LogLevel") -> bool:
        order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        return order.index(self.value) > order.index(other.value)


@dataclass
class TaskLogEntry:
    """任务日志条目"""
    id: str
    task_id: str
    level: LogLevel
    logger_name: str
    message: str
    timestamp: datetime
    gpu_id: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "level": self.level.value,
            "logger": self.logger_name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat() + "Z",
            "gpu_id": self.gpu_id,
            "extra": self.extra,
        }
    
    def to_json_line(self) -> str:
        """转换为 JSON 格式的日志行"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


class LogBuffer:
    """
    日志环形缓冲区
    
    用于存储最近的日志，支持 SSE 实时推送
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._buffer: List[TaskLogEntry] = []
        self._lock = Lock()
        self._subscribers: Dict[str, asyncio.Queue] = {}
    
    def append(self, entry: TaskLogEntry) -> None:
        """添加日志条目"""
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) > self.max_size:
                self._buffer.pop(0)
        
        # 通知订阅者
        self._notify_subscribers(entry)
    
    def get_recent(self, limit: int = 100, min_level: Optional[LogLevel] = None) -> List[TaskLogEntry]:
        """获取最近的日志"""
        with self._lock:
            entries = self._buffer[-limit:] if limit else self._buffer[:]
            if min_level:
                entries = [e for e in entries if e.level >= min_level]
            return entries
    
    def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        """订阅日志更新"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[subscriber_id] = queue
        return queue
    
    def unsubscribe(self, subscriber_id: str) -> None:
        """取消订阅"""
        self._subscribers.pop(subscriber_id, None)
    
    def _notify_subscribers(self, entry: TaskLogEntry) -> None:
        """通知所有订阅者"""
        for sub_id, queue in list(self._subscribers.items()):
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                # 队列满了，移除最旧的
                try:
                    queue.get_nowait()
                    queue.put_nowait(entry)
                except:
                    pass


class TaskLogService:
    """
    任务日志服务
    
    功能:
    - 记录任务执行日志
    - 存储到内存缓冲区（用于 SSE）
    - 持久化到数据库（可选）
    - 查询历史日志
    """
    
    def __init__(self, buffer_size: int = 10000):
        # 按任务 ID 分组的日志缓冲区
        self._task_buffers: Dict[str, LogBuffer] = defaultdict(lambda: LogBuffer(max_size=1000))
        # 全局日志缓冲区
        self._global_buffer = LogBuffer(max_size=buffer_size)
        # 系统日志缓冲区
        self._system_buffer = LogBuffer(max_size=buffer_size)
        # 日志持久化回调
        self._persist_callback: Optional[Callable[[TaskLogEntry], None]] = None
        self._lock = Lock()
    
    def set_persist_callback(self, callback: Callable[[TaskLogEntry], None]) -> None:
        """设置日志持久化回调"""
        self._persist_callback = callback
    
    def log(
        self,
        task_id: str,
        level: LogLevel,
        message: str,
        logger_name: str = "task",
        gpu_id: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> TaskLogEntry:
        """
        记录任务日志
        
        Args:
            task_id: 任务 ID
            level: 日志级别
            message: 日志消息
            logger_name: 日志来源名称
            gpu_id: GPU ID
            extra: 额外数据
        
        Returns:
            创建的日志条目
        """
        entry = TaskLogEntry(
            id=f"log_{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            level=level,
            logger_name=logger_name,
            message=message,
            timestamp=datetime.utcnow(),
            gpu_id=gpu_id,
            extra=extra or {},
        )
        
        # 添加到任务缓冲区
        self._task_buffers[task_id].append(entry)
        
        # 添加到全局缓冲区
        self._global_buffer.append(entry)
        
        # 持久化
        if self._persist_callback:
            try:
                self._persist_callback(entry)
            except Exception as e:
                logger.error("log_persist_failed", error=str(e))
        
        return entry
    
    def log_system(
        self,
        level: LogLevel,
        message: str,
        logger_name: str = "system",
        extra: Optional[Dict[str, Any]] = None,
    ) -> TaskLogEntry:
        """记录系统日志"""
        entry = TaskLogEntry(
            id=f"syslog_{uuid.uuid4().hex[:12]}",
            task_id="system",
            level=level,
            logger_name=logger_name,
            message=message,
            timestamp=datetime.utcnow(),
            extra=extra or {},
        )
        
        self._system_buffer.append(entry)
        return entry
    
    def debug(self, task_id: str, message: str, **extra) -> TaskLogEntry:
        """记录 DEBUG 级别日志"""
        return self.log(task_id, LogLevel.DEBUG, message, extra=extra)
    
    def info(self, task_id: str, message: str, **extra) -> TaskLogEntry:
        """记录 INFO 级别日志"""
        return self.log(task_id, LogLevel.INFO, message, extra=extra)
    
    def warning(self, task_id: str, message: str, **extra) -> TaskLogEntry:
        """记录 WARNING 级别日志"""
        return self.log(task_id, LogLevel.WARNING, message, extra=extra)
    
    def error(self, task_id: str, message: str, **extra) -> TaskLogEntry:
        """记录 ERROR 级别日志"""
        return self.log(task_id, LogLevel.ERROR, message, extra=extra)
    
    def critical(self, task_id: str, message: str, **extra) -> TaskLogEntry:
        """记录 CRITICAL 级别日志"""
        return self.log(task_id, LogLevel.CRITICAL, message, extra=extra)
    
    def get_task_logs(
        self,
        task_id: str,
        level: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TaskLogEntry]:
        """
        获取任务日志
        
        Args:
            task_id: 任务 ID
            level: 最低日志级别过滤
            limit: 返回条数
            offset: 偏移量
        
        Returns:
            日志条目列表
        """
        buffer = self._task_buffers.get(task_id)
        if not buffer:
            return []
        
        min_level = LogLevel.from_string(level) if level else None
        entries = buffer.get_recent(limit=limit + offset, min_level=min_level)
        
        return entries[offset:offset + limit]
    
    def get_recent_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> List[TaskLogEntry]:
        """获取全局最近日志"""
        min_level = LogLevel.from_string(level) if level else None
        return self._global_buffer.get_recent(limit=limit, min_level=min_level)
    
    def get_system_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> List[TaskLogEntry]:
        """获取系统日志"""
        min_level = LogLevel.from_string(level) if level else None
        return self._system_buffer.get_recent(limit=limit, min_level=min_level)
    
    def subscribe_task(self, task_id: str) -> tuple[str, asyncio.Queue]:
        """
        订阅任务日志更新
        
        Returns:
            (subscriber_id, queue) 元组
        """
        subscriber_id = f"sub_{uuid.uuid4().hex[:8]}"
        buffer = self._task_buffers[task_id]
        queue = buffer.subscribe(subscriber_id)
        return subscriber_id, queue
    
    def unsubscribe_task(self, task_id: str, subscriber_id: str) -> None:
        """取消订阅任务日志"""
        buffer = self._task_buffers.get(task_id)
        if buffer:
            buffer.unsubscribe(subscriber_id)
    
    def subscribe_system(self) -> tuple[str, asyncio.Queue]:
        """订阅系统日志更新"""
        subscriber_id = f"sys_sub_{uuid.uuid4().hex[:8]}"
        queue = self._system_buffer.subscribe(subscriber_id)
        return subscriber_id, queue
    
    def unsubscribe_system(self, subscriber_id: str) -> None:
        """取消订阅系统日志"""
        self._system_buffer.unsubscribe(subscriber_id)
    
    async def stream_task_logs(
        self,
        task_id: str,
        include_history: bool = True,
        history_limit: int = 50,
    ) -> AsyncGenerator[TaskLogEntry, None]:
        """
        流式获取任务日志 (用于 SSE)
        
        Args:
            task_id: 任务 ID
            include_history: 是否包含历史日志
            history_limit: 历史日志条数
        
        Yields:
            日志条目
        """
        # 先发送历史日志
        if include_history:
            for entry in self.get_task_logs(task_id, limit=history_limit):
                yield entry
        
        # 订阅实时更新
        subscriber_id, queue = self.subscribe_task(task_id)
        
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield entry
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield TaskLogEntry(
                        id="heartbeat",
                        task_id=task_id,
                        level=LogLevel.DEBUG,
                        logger_name="system",
                        message="heartbeat",
                        timestamp=datetime.utcnow(),
                    )
        finally:
            self.unsubscribe_task(task_id, subscriber_id)
    
    def clear_task_logs(self, task_id: str) -> None:
        """清除任务日志缓冲区"""
        with self._lock:
            self._task_buffers.pop(task_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        return {
            "task_buffers": len(self._task_buffers),
            "global_buffer_size": len(self._global_buffer._buffer),
            "system_buffer_size": len(self._system_buffer._buffer),
            "active_subscribers": sum(
                len(buf._subscribers) for buf in self._task_buffers.values()
            ) + len(self._system_buffer._subscribers),
        }


# 全局单例
_log_service: Optional[TaskLogService] = None


def get_log_service() -> TaskLogService:
    """获取日志服务单例"""
    global _log_service
    if _log_service is None:
        _log_service = TaskLogService()
    return _log_service


class TaskLogger:
    """
    任务专用日志器
    
    为特定任务提供便捷的日志接口
    """
    
    def __init__(
        self,
        task_id: str,
        logger_name: str = "task",
        gpu_id: Optional[int] = None,
        service: Optional[TaskLogService] = None,
    ):
        self.task_id = task_id
        self.logger_name = logger_name
        self.gpu_id = gpu_id
        self._service = service or get_log_service()
        self._structlog = structlog.get_logger(logger_name)
    
    def _log(self, level: LogLevel, message: str, **extra) -> None:
        """内部日志方法"""
        # 记录到任务日志服务
        self._service.log(
            task_id=self.task_id,
            level=level,
            message=message,
            logger_name=self.logger_name,
            gpu_id=self.gpu_id,
            extra=extra,
        )
        
        # 同时记录到 structlog
        log_method = getattr(self._structlog, level.value.lower())
        log_method(message, task_id=self.task_id, gpu_id=self.gpu_id, **extra)
    
    def debug(self, message: str, **extra) -> None:
        self._log(LogLevel.DEBUG, message, **extra)
    
    def info(self, message: str, **extra) -> None:
        self._log(LogLevel.INFO, message, **extra)
    
    def warning(self, message: str, **extra) -> None:
        self._log(LogLevel.WARNING, message, **extra)
    
    def error(self, message: str, **extra) -> None:
        self._log(LogLevel.ERROR, message, **extra)
    
    def critical(self, message: str, **extra) -> None:
        self._log(LogLevel.CRITICAL, message, **extra)
    
    def step(self, step_num: int, message: str, **metrics) -> None:
        """记录优化步骤"""
        self.info(message, step=step_num, **metrics)
    
    def progress(self, current: int, total: int, message: str = "Progress") -> None:
        """记录进度"""
        percent = (current / total * 100) if total > 0 else 0
        self.info(f"{message}: {current}/{total} ({percent:.1f}%)", 
                  current=current, total=total, percent=percent)
