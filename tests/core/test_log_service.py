"""
日志服务测试

测试任务日志服务和归档功能
"""
import pytest
import asyncio
from datetime import datetime

from core.services.log_service import (
    TaskLogService,
    TaskLogger,
    LogLevel,
    TaskLogEntry,
    LogBuffer,
)


class TestLogLevel:
    """测试日志级别"""
    
    def test_from_string(self):
        """测试从字符串转换"""
        assert LogLevel.from_string("info") == LogLevel.INFO
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        assert LogLevel.from_string("Warning") == LogLevel.WARNING
    
    def test_comparison(self):
        """测试级别比较"""
        assert LogLevel.ERROR >= LogLevel.WARNING
        assert LogLevel.WARNING >= LogLevel.INFO
        assert LogLevel.INFO >= LogLevel.DEBUG
        assert LogLevel.CRITICAL > LogLevel.ERROR


class TestLogBuffer:
    """测试日志缓冲区"""
    
    def test_append_and_get(self):
        """测试添加和获取日志"""
        buffer = LogBuffer(max_size=10)
        
        entry = TaskLogEntry(
            id="log_1",
            task_id="task_1",
            level=LogLevel.INFO,
            logger_name="test",
            message="Test message",
            timestamp=datetime.utcnow(),
        )
        
        buffer.append(entry)
        recent = buffer.get_recent(limit=10)
        
        assert len(recent) == 1
        assert recent[0].id == "log_1"
    
    def test_max_size(self):
        """测试最大容量限制"""
        buffer = LogBuffer(max_size=5)
        
        for i in range(10):
            entry = TaskLogEntry(
                id=f"log_{i}",
                task_id="task_1",
                level=LogLevel.INFO,
                logger_name="test",
                message=f"Message {i}",
                timestamp=datetime.utcnow(),
            )
            buffer.append(entry)
        
        recent = buffer.get_recent(limit=100)
        assert len(recent) == 5
        # 应该保留最新的 5 条
        assert recent[0].id == "log_5"
        assert recent[-1].id == "log_9"
    
    def test_level_filter(self):
        """测试级别过滤"""
        buffer = LogBuffer(max_size=100)
        
        for level in [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]:
            entry = TaskLogEntry(
                id=f"log_{level.value}",
                task_id="task_1",
                level=level,
                logger_name="test",
                message=f"Message {level.value}",
                timestamp=datetime.utcnow(),
            )
            buffer.append(entry)
        
        # 过滤 WARNING 及以上
        filtered = buffer.get_recent(limit=100, min_level=LogLevel.WARNING)
        assert len(filtered) == 2
        assert all(e.level >= LogLevel.WARNING for e in filtered)


class TestTaskLogService:
    """测试任务日志服务"""
    
    def test_log_task(self):
        """测试记录任务日志"""
        service = TaskLogService()
        
        entry = service.log(
            task_id="task_123",
            level=LogLevel.INFO,
            message="Optimization started",
            logger_name="task.optimization",
            gpu_id=0,
            extra={"step": 1, "energy": -100.5},
        )
        
        assert entry.task_id == "task_123"
        assert entry.level == LogLevel.INFO
        assert entry.message == "Optimization started"
        assert entry.extra["step"] == 1
    
    def test_convenience_methods(self):
        """测试便捷方法"""
        service = TaskLogService()
        
        service.debug("task_1", "Debug message")
        service.info("task_1", "Info message")
        service.warning("task_1", "Warning message")
        service.error("task_1", "Error message")
        
        logs = service.get_task_logs("task_1")
        assert len(logs) == 4
    
    def test_get_task_logs_with_filter(self):
        """测试日志查询过滤"""
        service = TaskLogService()
        
        service.debug("task_1", "Debug")
        service.info("task_1", "Info")
        service.warning("task_1", "Warning")
        service.error("task_1", "Error")
        
        # 过滤 WARNING 及以上
        logs = service.get_task_logs("task_1", level="WARNING")
        assert len(logs) == 2
        assert all(l.level >= LogLevel.WARNING for l in logs)
    
    def test_system_logs(self):
        """测试系统日志"""
        service = TaskLogService()
        
        service.log_system(LogLevel.INFO, "System started", logger_name="system.main")
        service.log_system(LogLevel.WARNING, "Memory low", extra={"available_mb": 1024})
        
        logs = service.get_system_logs()
        assert len(logs) == 2
    
    def test_get_stats(self):
        """测试统计信息"""
        service = TaskLogService()
        
        service.info("task_1", "Message 1")
        service.info("task_2", "Message 2")
        
        stats = service.get_stats()
        assert stats["task_buffers"] == 2
        assert stats["global_buffer_size"] == 2
    
    def test_clear_task_logs(self):
        """测试清除任务日志"""
        service = TaskLogService()
        
        service.info("task_1", "Message")
        assert len(service.get_task_logs("task_1")) == 1
        
        service.clear_task_logs("task_1")
        assert len(service.get_task_logs("task_1")) == 0


class TestTaskLogger:
    """测试任务日志器"""
    
    def test_task_logger(self):
        """测试任务专用日志器"""
        service = TaskLogService()
        logger = TaskLogger(
            task_id="task_123",
            logger_name="task.optimization",
            gpu_id=0,
            service=service,
        )
        
        logger.info("Step completed", step=1, energy=-100.0)
        logger.warning("Force too high", fmax=0.5)
        
        logs = service.get_task_logs("task_123")
        assert len(logs) == 2
    
    def test_step_logging(self):
        """测试步骤日志"""
        service = TaskLogService()
        logger = TaskLogger(task_id="task_1", service=service)
        
        logger.step(1, "Optimization step", energy=-100.0, fmax=0.1)
        logger.step(2, "Optimization step", energy=-110.0, fmax=0.05)
        
        logs = service.get_task_logs("task_1")
        assert len(logs) == 2
        assert logs[0].extra["step"] == 1
    
    def test_progress_logging(self):
        """测试进度日志"""
        service = TaskLogService()
        logger = TaskLogger(task_id="task_1", service=service)
        
        logger.progress(50, 100, "Processing")
        
        logs = service.get_task_logs("task_1")
        assert len(logs) == 1
        assert logs[0].extra["percent"] == 50.0


class TestTaskLogEntry:
    """测试日志条目"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        entry = TaskLogEntry(
            id="log_1",
            task_id="task_1",
            level=LogLevel.INFO,
            logger_name="test",
            message="Test message",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            gpu_id=0,
            extra={"key": "value"},
        )
        
        d = entry.to_dict()
        assert d["id"] == "log_1"
        assert d["task_id"] == "task_1"
        assert d["level"] == "INFO"
        assert d["logger"] == "test"
        assert d["message"] == "Test message"
        assert d["gpu_id"] == 0
        assert d["extra"]["key"] == "value"
        assert "2025-01-01" in d["timestamp"]
    
    def test_to_json_line(self):
        """测试转换为 JSON 行"""
        entry = TaskLogEntry(
            id="log_1",
            task_id="task_1",
            level=LogLevel.INFO,
            logger_name="test",
            message="Test message",
            timestamp=datetime.utcnow(),
        )
        
        json_line = entry.to_json_line()
        assert '"level": "INFO"' in json_line
        assert '"message": "Test message"' in json_line
