"""
Worker 管理模块

负责 Worker 启动、监控和心跳管理
参考文档: docs/architecture/gpu_scheduler_design.md 5 节
"""
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import os

import structlog

logger = structlog.get_logger(__name__)


class WorkerStatus(str, Enum):
    """Worker 状态"""
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class WorkerInfo:
    """Worker 信息"""
    worker_id: str
    gpu_id: int
    hostname: str
    pid: Optional[int] = None
    status: WorkerStatus = WorkerStatus.STARTING
    current_task_id: Optional[str] = None
    last_heartbeat: float = field(default_factory=time.time)
    started_at: float = field(default_factory=time.time)
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    @property
    def is_alive(self) -> bool:
        """检查 worker 是否存活"""
        return self.status not in (WorkerStatus.OFFLINE, WorkerStatus.ERROR)
    
    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "gpu_id": self.gpu_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "last_heartbeat": self.last_heartbeat,
            "started_at": self.started_at,
            "uptime_seconds": time.time() - self.started_at,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
        }


class WorkerManager:
    """
    Worker 管理器
    
    功能：
    - Worker 注册和注销
    - 心跳监控
    - 故障检测
    """
    
    HEARTBEAT_INTERVAL = 10  # 秒
    HEARTBEAT_TIMEOUT = 30   # 秒
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.workers: Dict[str, WorkerInfo] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 回调函数
        self.on_worker_down: Optional[callable] = None
        self.on_worker_recovered: Optional[callable] = None
    
    def register_worker(
        self,
        worker_id: str,
        gpu_id: int,
        hostname: str,
        pid: Optional[int] = None
    ) -> WorkerInfo:
        """注册 Worker"""
        info = WorkerInfo(
            worker_id=worker_id,
            gpu_id=gpu_id,
            hostname=hostname,
            pid=pid,
            status=WorkerStatus.RUNNING,
        )
        self.workers[worker_id] = info
        
        logger.info(
            "worker_registered",
            worker_id=worker_id,
            gpu_id=gpu_id,
            hostname=hostname
        )
        
        # 持久化到 Redis
        if self.redis:
            self._save_worker_to_redis(info)
        
        return info
    
    def unregister_worker(self, worker_id: str):
        """注销 Worker"""
        if worker_id in self.workers:
            del self.workers[worker_id]
            logger.info("worker_unregistered", worker_id=worker_id)
            
            if self.redis:
                self.redis.hdel("mofsim:workers", worker_id)
    
    def heartbeat(self, worker_id: str, **kwargs) -> bool:
        """更新 Worker 心跳"""
        if worker_id not in self.workers:
            return False
        
        info = self.workers[worker_id]
        info.last_heartbeat = time.time()
        
        # 更新其他信息
        if "status" in kwargs:
            info.status = WorkerStatus(kwargs["status"])
        if "current_task_id" in kwargs:
            info.current_task_id = kwargs["current_task_id"]
        
        # 持久化
        if self.redis:
            self._save_worker_to_redis(info)
        
        return True
    
    def set_worker_busy(self, worker_id: str, task_id: str):
        """标记 Worker 忙碌"""
        if worker_id in self.workers:
            info = self.workers[worker_id]
            info.status = WorkerStatus.BUSY
            info.current_task_id = task_id
    
    def set_worker_idle(self, worker_id: str, task_succeeded: bool = True):
        """标记 Worker 空闲"""
        if worker_id in self.workers:
            info = self.workers[worker_id]
            info.status = WorkerStatus.IDLE
            info.current_task_id = None
            
            if task_succeeded:
                info.tasks_completed += 1
            else:
                info.tasks_failed += 1
    
    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """获取 Worker 信息"""
        return self.workers.get(worker_id)
    
    def get_worker_by_gpu(self, gpu_id: int) -> Optional[WorkerInfo]:
        """根据 GPU ID 获取 Worker"""
        for info in self.workers.values():
            if info.gpu_id == gpu_id:
                return info
        return None
    
    def get_all_workers(self) -> List[WorkerInfo]:
        """获取所有 Worker"""
        return list(self.workers.values())
    
    def get_active_workers(self) -> List[WorkerInfo]:
        """获取活跃的 Worker"""
        return [w for w in self.workers.values() if w.is_alive]
    
    async def start_monitor(self):
        """启动心跳监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("worker_monitor_started")
    
    async def stop_monitor(self):
        """停止心跳监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("worker_monitor_stopped")
    
    async def _monitor_loop(self):
        """心跳监控循环"""
        while self._running:
            try:
                now = time.time()
                
                for worker_id, info in list(self.workers.items()):
                    if info.status in (WorkerStatus.OFFLINE, WorkerStatus.ERROR):
                        continue
                    
                    # 检查心跳超时
                    if now - info.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                        await self._handle_worker_timeout(worker_id)
                
            except Exception as e:
                logger.error("worker_monitor_error", error=str(e))
            
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)
    
    async def _handle_worker_timeout(self, worker_id: str):
        """处理 Worker 超时"""
        info = self.workers.get(worker_id)
        if not info:
            return
        
        old_status = info.status
        info.status = WorkerStatus.OFFLINE
        
        logger.warning(
            "worker_timeout",
            worker_id=worker_id,
            gpu_id=info.gpu_id,
            last_heartbeat=info.last_heartbeat,
            current_task_id=info.current_task_id
        )
        
        # 触发回调
        if self.on_worker_down:
            try:
                await self.on_worker_down(worker_id, info.gpu_id, info.current_task_id)
            except Exception as e:
                logger.error("worker_down_callback_error", error=str(e))
    
    def _save_worker_to_redis(self, info: WorkerInfo):
        """保存 Worker 信息到 Redis"""
        try:
            import json
            self.redis.hset(
                "mofsim:workers",
                info.worker_id,
                json.dumps(info.to_dict())
            )
        except Exception as e:
            logger.warning("redis_save_worker_failed", error=str(e))
    
    def _load_workers_from_redis(self):
        """从 Redis 加载 Worker 信息"""
        if not self.redis:
            return
        
        try:
            import json
            data = self.redis.hgetall("mofsim:workers")
            for worker_id, info_json in data.items():
                if isinstance(worker_id, bytes):
                    worker_id = worker_id.decode()
                if isinstance(info_json, bytes):
                    info_json = info_json.decode()
                
                info_dict = json.loads(info_json)
                # 重建 WorkerInfo 对象时标记为 OFFLINE（需要重新心跳）
                info = WorkerInfo(
                    worker_id=info_dict["worker_id"],
                    gpu_id=info_dict["gpu_id"],
                    hostname=info_dict["hostname"],
                    status=WorkerStatus.OFFLINE,
                )
                self.workers[worker_id] = info
        except Exception as e:
            logger.warning("redis_load_workers_failed", error=str(e))
    
    def get_summary(self) -> dict:
        """获取 Worker 状态摘要"""
        total = len(self.workers)
        by_status = {}
        for status in WorkerStatus:
            count = sum(1 for w in self.workers.values() if w.status == status)
            if count > 0:
                by_status[status.value] = count
        
        return {
            "total_workers": total,
            "active_workers": len(self.get_active_workers()),
            "by_status": by_status,
            "workers": [w.to_dict() for w in self.workers.values()]
        }


def get_worker_id(gpu_id: int) -> str:
    """生成 Worker ID"""
    import socket
    hostname = socket.gethostname()
    return f"worker-{hostname}-gpu-{gpu_id}"


def get_worker_env(gpu_id: int) -> dict:
    """获取 Worker 环境变量"""
    return {
        "CUDA_VISIBLE_DEVICES": str(gpu_id),
        "MOFSIM_WORKER_GPU_ID": str(gpu_id),
        "MOFSIM_WORKER_ID": get_worker_id(gpu_id),
    }
