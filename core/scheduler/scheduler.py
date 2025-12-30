"""
任务调度器

核心调度逻辑，负责任务到 GPU 的分配
参考文档: docs/architecture/gpu_scheduler_design.md
"""
from typing import Optional, Tuple, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
import asyncio
import time

import structlog

from .priority_queue import PriorityQueue, TaskPriority
from .gpu_manager import GPUManager, GPUState, GPUStatus
from .task_lifecycle import TaskState, TaskLifecycle

logger = structlog.get_logger(__name__)


@dataclass
class ScheduleResult:
    """调度结果"""
    success: bool
    task_id: Optional[str] = None
    gpu_id: Optional[int] = None
    reason: Optional[str] = None


@dataclass 
class MemoryEstimate:
    """显存估算"""
    model_base_mb: int
    atom_memory_mb: int
    task_multiplier: float
    total_mb: int


class Scheduler:
    """
    任务调度器
    
    功能：
    - 从优先级队列获取任务
    - 选择最佳 GPU
    - 分配任务到 GPU
    - 模型亲和性调度
    - 负载均衡
    """
    
    # 默认模型显存估算 (MB)
    DEFAULT_MODEL_MEMORY_MB = 4000
    
    # 每原子显存估算 (MB)
    MEMORY_PER_ATOM_MB = 2
    
    # 任务类型显存倍率
    TASK_TYPE_MULTIPLIERS = {
        "optimization": 1.2,
        "stability": 1.5,
        "bulk-modulus": 1.3,
        "heat-capacity": 2.0,
        "interaction-energy": 1.2,
        "single-point": 1.0,
    }
    
    # 模型显存估算 (MB) - 可动态更新
    MODEL_MEMORY_ESTIMATES = {
        "mace-mp-0-medium": 4000,
        "mace-mp-0-large": 8000,
        "mace-omat-0-medium": 5000,
        "mace-omat-0-large": 10000,
        "orb-v2": 3000,
        "sevennet-0": 3500,
        "mattersim-v1-1m": 4000,
        "mattersim-v1-5m": 8000,
        "grace-2l-oam": 4500,
    }
    
    def __init__(
        self,
        gpu_manager: GPUManager,
        queue: PriorityQueue,
        task_fetcher: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
        poll_interval_ms: int = 100,
    ):
        """
        初始化调度器
        
        Args:
            gpu_manager: GPU 管理器
            queue: 优先级队列
            task_fetcher: 异步函数，根据 task_id 获取任务信息
            poll_interval_ms: 调度轮询间隔（毫秒）
        """
        self.gpu_manager = gpu_manager
        self.queue = queue
        self.task_fetcher = task_fetcher
        self.poll_interval_ms = poll_interval_ms
        
        self._running = False
        self._schedule_task: Optional[asyncio.Task] = None
        
        # 统计
        self.stats = {
            "schedule_attempts": 0,
            "schedule_successes": 0,
            "schedule_failures": 0,
            "no_free_gpu": 0,
            "no_pending_task": 0,
        }
    
    async def schedule_next(self) -> ScheduleResult:
        """
        调度下一个任务
        
        Returns:
            ScheduleResult 包含调度结果
        """
        self.stats["schedule_attempts"] += 1
        
        # 1. 刷新 GPU 状态
        self.gpu_manager.refresh_states()
        
        # 2. 获取空闲 GPU
        free_gpus = self.gpu_manager.get_free_gpus()
        if not free_gpus:
            self.stats["no_free_gpu"] += 1
            return ScheduleResult(
                success=False,
                reason="No free GPU available"
            )
        
        # 3. 从队列查看任务（不移除）
        task_id = self.queue.peek_first()
        if not task_id:
            self.stats["no_pending_task"] += 1
            return ScheduleResult(
                success=False,
                reason="No pending task in queue"
            )
        
        # 4. 获取任务详情
        task_info = await self._get_task_info(task_id)
        if not task_info:
            # 任务不存在，从队列移除
            self.queue.remove(task_id)
            return ScheduleResult(
                success=False,
                task_id=task_id,
                reason="Task not found"
            )
        
        # 5. 选择最佳 GPU
        gpu_id = await self._select_best_gpu(task_info, free_gpus)
        if gpu_id is None:
            self.stats["schedule_failures"] += 1
            return ScheduleResult(
                success=False,
                task_id=task_id,
                reason="No suitable GPU (memory or other constraints)"
            )
        
        # 6. 分配 GPU
        if await self.gpu_manager.allocate(gpu_id, task_id):
            # 从队列移除
            self.queue.dequeue()
            self.stats["schedule_successes"] += 1
            
            logger.info(
                "task_scheduled",
                task_id=task_id,
                gpu_id=gpu_id,
                model=task_info.get("model_name"),
            )
            
            return ScheduleResult(
                success=True,
                task_id=task_id,
                gpu_id=gpu_id
            )
        
        self.stats["schedule_failures"] += 1
        return ScheduleResult(
            success=False,
            task_id=task_id,
            reason="GPU allocation failed (race condition)"
        )
    
    async def _get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        if self.task_fetcher:
            try:
                return await self.task_fetcher(task_id)
            except Exception as e:
                logger.warning("task_fetch_failed", task_id=task_id, error=str(e))
                return None
        
        # 无 fetcher 时返回默认信息
        return {
            "task_id": task_id,
            "model_name": "unknown",
            "task_type": "optimization",
            "n_atoms": 500,
        }
    
    async def _select_best_gpu(
        self,
        task_info: Dict[str, Any],
        free_gpus: list
    ) -> Optional[int]:
        """
        选择最佳 GPU
        
        评分标准：
        1. 模型亲和性（已加载模型的 GPU 得分更高）
        2. 可用显存
        3. 温度
        4. 空闲时间
        """
        model_name = task_info.get("model_name", "unknown")
        required_memory = self._estimate_memory(task_info)
        
        candidates = []
        
        for gpu_id in free_gpus:
            state = self.gpu_manager.gpu_states[gpu_id]
            
            # 检查显存是否足够
            if not self.gpu_manager.check_memory_available(gpu_id, required_memory):
                continue
            
            # 计算得分
            score = self._calculate_gpu_score(state, model_name)
            candidates.append((gpu_id, score))
        
        if not candidates:
            logger.warning(
                "no_suitable_gpu",
                model=model_name,
                required_memory_mb=required_memory,
                free_gpus=free_gpus
            )
            return None
        
        # 返回得分最高的 GPU
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _calculate_gpu_score(self, state: GPUState, model_name: str) -> float:
        """计算 GPU 得分"""
        score = 0.0
        
        # 模型亲和性（0-100 分）
        if model_name in state.loaded_models:
            score += 100
        elif len(state.loaded_models) < self.gpu_manager.MAX_MODELS_PER_GPU:
            score += 50
        
        # 可用显存（0-40 分）
        if state.memory_total_mb > 0:
            memory_ratio = state.memory_free_mb / state.memory_total_mb
            score += memory_ratio * 40
        
        # 温度（0-20 分）
        if state.temperature_c > 0:
            temp_score = max(0, (100 - state.temperature_c)) / 100 * 20
            score += temp_score
        
        # 空闲时间（0-10 分）
        if state.last_task_completed_at:
            idle_time = time.time() - state.last_task_completed_at
            # 空闲超过 60 秒得满分
            idle_score = min(idle_time / 60, 1) * 10
            score += idle_score
        else:
            score += 10  # 从未执行过任务的 GPU 给满分
        
        return score
    
    def _estimate_memory(self, task_info: Dict[str, Any]) -> int:
        """估算任务所需显存 (MB)"""
        model_name = task_info.get("model_name", "unknown")
        task_type = task_info.get("task_type", "optimization")
        n_atoms = task_info.get("n_atoms", 500)
        
        # 模型基础显存
        base_memory = self.MODEL_MEMORY_ESTIMATES.get(
            model_name, self.DEFAULT_MODEL_MEMORY_MB
        )
        
        # 原子数显存
        atom_memory = n_atoms * self.MEMORY_PER_ATOM_MB
        
        # 任务类型倍率
        multiplier = self.TASK_TYPE_MULTIPLIERS.get(task_type, 1.0)
        
        total = int((base_memory + atom_memory) * multiplier)
        
        return total
    
    def estimate_memory_detailed(self, task_info: Dict[str, Any]) -> MemoryEstimate:
        """获取详细的显存估算"""
        model_name = task_info.get("model_name", "unknown")
        task_type = task_info.get("task_type", "optimization")
        n_atoms = task_info.get("n_atoms", 500)
        
        base = self.MODEL_MEMORY_ESTIMATES.get(model_name, self.DEFAULT_MODEL_MEMORY_MB)
        atom_mem = n_atoms * self.MEMORY_PER_ATOM_MB
        multiplier = self.TASK_TYPE_MULTIPLIERS.get(task_type, 1.0)
        
        return MemoryEstimate(
            model_base_mb=base,
            atom_memory_mb=atom_mem,
            task_multiplier=multiplier,
            total_mb=int((base + atom_mem) * multiplier)
        )
    
    def update_model_memory_estimate(self, model_name: str, new_estimate_mb: int):
        """更新模型显存估算（用于 OOM 后调整）"""
        old = self.MODEL_MEMORY_ESTIMATES.get(model_name, self.DEFAULT_MODEL_MEMORY_MB)
        self.MODEL_MEMORY_ESTIMATES[model_name] = new_estimate_mb
        logger.info(
            "model_memory_estimate_updated",
            model=model_name,
            old_mb=old,
            new_mb=new_estimate_mb
        )
    
    async def start_scheduling_loop(self):
        """启动调度循环"""
        if self._running:
            logger.warning("scheduler_already_running")
            return
        
        self._running = True
        logger.info("scheduler_started", poll_interval_ms=self.poll_interval_ms)
        
        while self._running:
            try:
                result = await self.schedule_next()
                
                if result.success:
                    # 调度成功后立即尝试下一个
                    continue
                
            except Exception as e:
                logger.error("scheduler_error", error=str(e), exc_info=True)
            
            # 等待下一次轮询
            await asyncio.sleep(self.poll_interval_ms / 1000)
    
    def stop_scheduling_loop(self):
        """停止调度循环"""
        self._running = False
        logger.info("scheduler_stopped")
    
    def get_stats(self) -> dict:
        """获取调度统计"""
        return {
            **self.stats,
            "queue_size": self.queue.size(),
            "queue_by_priority": self.queue.size_by_priority(),
            "gpu_summary": self.gpu_manager.get_summary(),
        }
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        tasks = self.queue.peek(20)
        return {
            "size": self.queue.size(),
            "by_priority": self.queue.size_by_priority(),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "priority": t.priority.name,
                    "position": t.position,
                    "wait_time_seconds": time.time() - t.enqueued_at
                }
                for t in tasks
            ]
        }
