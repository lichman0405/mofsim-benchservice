"""
GPU 资源管理器

负责 GPU 状态监控、资源分配和释放
参考文档: docs/architecture/gpu_scheduler_design.md 3.2 节
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio
import time
import os

import structlog

logger = structlog.get_logger(__name__)


class GPUStatus(str, Enum):
    """GPU 状态"""
    FREE = "free"       # 空闲可用
    BUSY = "busy"       # 正在执行任务
    ERROR = "error"     # 错误状态
    RESERVED = "reserved"  # 保留（不参与调度）


@dataclass
class GPUState:
    """GPU 状态信息"""
    id: int
    name: str = "Unknown GPU"
    memory_total_mb: int = 0
    memory_used_mb: int = 0
    memory_free_mb: int = 0
    utilization_percent: int = 0
    temperature_c: int = 0
    status: GPUStatus = GPUStatus.FREE
    current_task_id: Optional[str] = None
    loaded_models: List[str] = field(default_factory=list)
    last_task_completed_at: Optional[float] = None
    error_message: Optional[str] = None
    
    @property
    def is_available(self) -> bool:
        """是否可用于新任务"""
        return self.status == GPUStatus.FREE
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "memory_total_mb": self.memory_total_mb,
            "memory_used_mb": self.memory_used_mb,
            "memory_free_mb": self.memory_free_mb,
            "utilization_percent": self.utilization_percent,
            "temperature_c": self.temperature_c,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "loaded_models": self.loaded_models,
            "last_task_completed_at": self.last_task_completed_at,
            "error_message": self.error_message,
        }


class GPUManager:
    """
    GPU 资源管理器
    
    功能：
    - GPU 状态监控（通过 pynvml 或 mock）
    - GPU 分配与释放
    - 模型缓存追踪
    - 负载均衡支持
    """
    
    # 显存安全余量 (MB)
    MEMORY_SAFETY_MARGIN_MB = 2000
    
    # 每个 GPU 最大缓存模型数
    MAX_MODELS_PER_GPU = 2
    
    def __init__(
        self,
        gpu_ids: Optional[List[int]] = None,
        reserved_gpu_ids: Optional[List[int]] = None,
        mock_mode: bool = False
    ):
        """
        初始化 GPU 管理器
        
        Args:
            gpu_ids: 要管理的 GPU ID 列表，None 表示自动检测
            reserved_gpu_ids: 保留的 GPU（不参与调度）
            mock_mode: 是否使用模拟模式（无 GPU 环境）
        """
        self.mock_mode = mock_mode or not self._check_gpu_available()
        self.reserved_gpu_ids = set(reserved_gpu_ids or [])
        
        if self.mock_mode:
            # 模拟模式：创建假 GPU
            self.gpu_ids = gpu_ids or [0]
            self.gpu_states = {
                i: self._create_mock_gpu_state(i) for i in self.gpu_ids
            }
            logger.warning("gpu_manager_mock_mode", gpu_count=len(self.gpu_ids))
        else:
            # 真实模式：从系统获取 GPU 信息
            self._init_nvml()
            self.gpu_ids = gpu_ids or self._detect_gpus()
            self.gpu_states = {
                i: self._init_gpu_state(i) for i in self.gpu_ids
            }
            logger.info("gpu_manager_initialized", gpu_ids=self.gpu_ids)
        
        # 标记保留的 GPU
        for gpu_id in self.reserved_gpu_ids:
            if gpu_id in self.gpu_states:
                self.gpu_states[gpu_id].status = GPUStatus.RESERVED
        
        # 异步锁，每个 GPU 一个
        self._locks: Dict[int, asyncio.Lock] = {
            i: asyncio.Lock() for i in self.gpu_ids
        }
    
    def _check_gpu_available(self) -> bool:
        """检查是否有 GPU 可用"""
        try:
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            return count > 0
        except Exception:
            return False
    
    def _init_nvml(self):
        """初始化 NVML"""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
        except Exception as e:
            logger.warning("nvml_init_failed", error=str(e))
            self.mock_mode = True
    
    def _detect_gpus(self) -> List[int]:
        """自动检测 GPU"""
        try:
            count = self._nvml.nvmlDeviceGetCount()
            return list(range(count))
        except Exception:
            return [0]
    
    def _init_gpu_state(self, gpu_id: int) -> GPUState:
        """初始化单个 GPU 状态"""
        try:
            handle = self._nvml.nvmlDeviceGetHandleByIndex(gpu_id)
            name = self._nvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()
            
            memory = self._nvml.nvmlDeviceGetMemoryInfo(handle)
            
            return GPUState(
                id=gpu_id,
                name=name,
                memory_total_mb=memory.total // 1024 // 1024,
                memory_used_mb=memory.used // 1024 // 1024,
                memory_free_mb=memory.free // 1024 // 1024,
            )
        except Exception as e:
            logger.warning("gpu_init_failed", gpu_id=gpu_id, error=str(e))
            return self._create_mock_gpu_state(gpu_id)
    
    def _create_mock_gpu_state(self, gpu_id: int) -> GPUState:
        """创建模拟 GPU 状态"""
        return GPUState(
            id=gpu_id,
            name=f"Mock GPU {gpu_id}",
            memory_total_mb=24000,  # 模拟 24GB
            memory_used_mb=2000,
            memory_free_mb=22000,
            utilization_percent=0,
            temperature_c=40,
        )
    
    def refresh_states(self):
        """刷新所有 GPU 状态"""
        if self.mock_mode:
            return
        
        try:
            for gpu_id in self.gpu_ids:
                handle = self._nvml.nvmlDeviceGetHandleByIndex(gpu_id)
                memory = self._nvml.nvmlDeviceGetMemoryInfo(handle)
                util = self._nvml.nvmlDeviceGetUtilizationRates(handle)
                temp = self._nvml.nvmlDeviceGetTemperature(
                    handle, self._nvml.NVML_TEMPERATURE_GPU
                )
                
                state = self.gpu_states[gpu_id]
                state.memory_total_mb = memory.total // 1024 // 1024
                state.memory_used_mb = memory.used // 1024 // 1024
                state.memory_free_mb = memory.free // 1024 // 1024
                state.utilization_percent = util.gpu
                state.temperature_c = temp
                
        except Exception as e:
            logger.warning("gpu_refresh_failed", error=str(e))
    
    def get_free_gpus(self) -> List[int]:
        """获取空闲 GPU 列表"""
        return [
            gpu_id for gpu_id, state in self.gpu_states.items()
            if state.status == GPUStatus.FREE
        ]
    
    def get_gpu_with_model(self, model_name: str) -> Optional[int]:
        """获取已加载指定模型的空闲 GPU"""
        for gpu_id, state in self.gpu_states.items():
            if state.status == GPUStatus.FREE and model_name in state.loaded_models:
                return gpu_id
        return None
    
    async def allocate(self, gpu_id: int, task_id: str) -> bool:
        """
        分配 GPU 给任务
        
        Args:
            gpu_id: GPU ID
            task_id: 任务 ID
        
        Returns:
            是否分配成功
        """
        if gpu_id not in self._locks:
            logger.warning("invalid_gpu_id", gpu_id=gpu_id)
            return False
        
        async with self._locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            
            if state.status != GPUStatus.FREE:
                logger.warning(
                    "gpu_not_available",
                    gpu_id=gpu_id,
                    current_status=state.status.value
                )
                return False
            
            state.status = GPUStatus.BUSY
            state.current_task_id = task_id
            
            logger.info(
                "gpu_allocated",
                gpu_id=gpu_id,
                task_id=task_id
            )
            return True
    
    async def release(self, gpu_id: int):
        """
        释放 GPU
        
        Args:
            gpu_id: GPU ID
        """
        if gpu_id not in self._locks:
            return
        
        async with self._locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            old_task_id = state.current_task_id
            
            state.status = GPUStatus.FREE
            state.current_task_id = None
            state.last_task_completed_at = time.time()
            
            logger.info(
                "gpu_released",
                gpu_id=gpu_id,
                released_task_id=old_task_id
            )
    
    async def mark_error(self, gpu_id: int, error_message: str):
        """标记 GPU 为错误状态"""
        if gpu_id not in self._locks:
            return
        
        async with self._locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            state.status = GPUStatus.ERROR
            state.error_message = error_message
            
            logger.error(
                "gpu_marked_error",
                gpu_id=gpu_id,
                error=error_message
            )
    
    async def recover_gpu(self, gpu_id: int) -> bool:
        """尝试恢复 GPU"""
        if gpu_id not in self._locks:
            return False
        
        async with self._locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            
            if state.status != GPUStatus.ERROR:
                return True
            
            # 刷新状态检查
            self.refresh_states()
            
            # 如果可以获取状态，认为已恢复
            if state.memory_total_mb > 0:
                state.status = GPUStatus.FREE
                state.error_message = None
                state.current_task_id = None
                logger.info("gpu_recovered", gpu_id=gpu_id)
                return True
            
            return False
    
    def add_loaded_model(self, gpu_id: int, model_name: str):
        """记录 GPU 上加载的模型"""
        if gpu_id not in self.gpu_states:
            return
        
        state = self.gpu_states[gpu_id]
        
        if model_name not in state.loaded_models:
            # LRU: 如果超过最大数量，移除最早的
            if len(state.loaded_models) >= self.MAX_MODELS_PER_GPU:
                removed = state.loaded_models.pop(0)
                logger.info(
                    "model_evicted_from_cache",
                    gpu_id=gpu_id,
                    model_name=removed
                )
            
            state.loaded_models.append(model_name)
            logger.info(
                "model_added_to_cache",
                gpu_id=gpu_id,
                model_name=model_name
            )
    
    def remove_loaded_model(self, gpu_id: int, model_name: str):
        """移除 GPU 上的模型记录"""
        if gpu_id not in self.gpu_states:
            return
        
        state = self.gpu_states[gpu_id]
        if model_name in state.loaded_models:
            state.loaded_models.remove(model_name)
    
    def check_memory_available(self, gpu_id: int, required_mb: int) -> bool:
        """检查显存是否足够"""
        if gpu_id not in self.gpu_states:
            return False
        
        state = self.gpu_states[gpu_id]
        available = state.memory_free_mb - self.MEMORY_SAFETY_MARGIN_MB
        return available >= required_mb
    
    def get_all_states(self) -> Dict[int, GPUState]:
        """获取所有 GPU 状态"""
        return self.gpu_states.copy()
    
    def get_summary(self) -> dict:
        """获取 GPU 状态摘要"""
        total = len(self.gpu_ids)
        free = len(self.get_free_gpus())
        busy = sum(1 for s in self.gpu_states.values() if s.status == GPUStatus.BUSY)
        error = sum(1 for s in self.gpu_states.values() if s.status == GPUStatus.ERROR)
        reserved = sum(1 for s in self.gpu_states.values() if s.status == GPUStatus.RESERVED)
        
        total_memory_mb = sum(s.memory_total_mb for s in self.gpu_states.values())
        used_memory_mb = sum(s.memory_used_mb for s in self.gpu_states.values())
        
        return {
            "total_gpus": total,
            "free_gpus": free,
            "busy_gpus": busy,
            "error_gpus": error,
            "reserved_gpus": reserved,
            "total_memory_mb": total_memory_mb,
            "used_memory_mb": used_memory_mb,
            "free_memory_mb": total_memory_mb - used_memory_mb,
            "mock_mode": self.mock_mode,
            "gpus": [s.to_dict() for s in self.gpu_states.values()]
        }
    
    def shutdown(self):
        """关闭管理器"""
        if not self.mock_mode and hasattr(self, '_nvml'):
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
