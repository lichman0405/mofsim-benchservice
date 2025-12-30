"""
任务基类

提供通用的任务生命周期管理，集成 GPU 资源管理和模型加载
"""
from typing import Dict, Any, Optional, Type
from pathlib import Path
import os
import time
import tempfile
import traceback

from celery import Task
import ase.io
import structlog

from core.tasks.base import TaskExecutor, TaskContext, TaskResult
from core.scheduler.gpu_manager import GPUManager
from workers.worker_manager import get_worker_env

logger = structlog.get_logger(__name__)


class BaseModelTask(Task):
    """
    模型任务基类
    
    提供:
    - GPU 资源管理
    - 模型加载/卸载
    - 状态更新
    - 错误处理
    - 与 core/tasks 执行器集成
    """
    abstract = True
    
    # Celery 重试配置
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    max_retries = 3
    
    # 子类需要指定
    executor_class: Optional[Type[TaskExecutor]] = None
    
    # 运行时状态
    _calculator = None
    _gpu_id = None
    _gpu_manager: Optional[GPUManager] = None
    
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
        # 释放 GPU
        self._release_gpu()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败"""
        logger.error(
            "task_failed",
            task_id=task_id,
            error=str(exc),
            exc_info=True,
        )
        self._release_gpu()
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试"""
        logger.warning(
            "task_retrying",
            task_id=task_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        self._release_gpu()
    
    def run_with_executor(
        self,
        task_id: str,
        model_name: str,
        structure_path: str,
        parameters: Dict[str, Any],
        gpu_id: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        使用执行器运行任务
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 任务参数
            gpu_id: 指定 GPU ID
            timeout: 超时时间
            
        Returns:
            任务结果字典
        """
        if self.executor_class is None:
            raise NotImplementedError("Subclass must define executor_class")
        
        # 分配 GPU
        if gpu_id is None:
            gpu_id = self._allocate_gpu(model_name)
        self._gpu_id = gpu_id
        
        # 设置 CUDA 环境
        if gpu_id is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        
        try:
            # 加载结构
            atoms = ase.io.read(structure_path)
            structure_name = Path(structure_path).stem
            
            # 加载计算器
            calculator = self._load_calculator(model_name, gpu_id)
            atoms.set_calculator(calculator)
            
            # 创建工作目录
            work_dir = Path(tempfile.mkdtemp(prefix=f"task_{task_id}_"))
            
            # 创建执行上下文
            context = TaskContext(
                task_id=task_id,
                model_name=model_name,
                gpu_id=gpu_id,
                parameters=parameters,
                work_dir=work_dir,
                structure_name=structure_name,
                timeout=timeout,
            )
            
            # 创建并运行执行器
            executor = self.executor_class()
            result = executor.run(atoms, context)
            
            # 转换结果
            return {
                "success": result.success,
                "data": result.data,
                "output_files": result.output_files,
                "duration_seconds": result.duration,
                "error": result.error,
            }
            
        except Exception as e:
            logger.error(
                "executor_failed",
                task_id=task_id,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "success": False,
                "data": {},
                "output_files": {},
                "duration_seconds": time.perf_counter() - self._start_time,
                "error": str(e),
            }
    
    def _load_calculator(self, model_name: str, gpu_id: Optional[int] = None):
        """
        加载 ASE 计算器
        
        支持的模型:
        - MACE, MACE-MP, MACE-OFF
        - ORB
        - OMAT24
        - GRACE
        - SevenNet
        - MatterSim
        """
        from mof_benchmark.setup.calculator import get_calculator
        
        logger.info(
            "loading_calculator",
            model_name=model_name,
            gpu_id=gpu_id,
        )
        
        self._calculator = get_calculator(model_name)
        return self._calculator
    
    def _allocate_gpu(self, model_name: str) -> Optional[int]:
        """分配 GPU 资源"""
        # 检查是否由 worker 环境指定
        worker_env = get_worker_env()
        if worker_env and worker_env.gpu_id is not None:
            return worker_env.gpu_id
        
        # 使用 GPU 管理器分配
        try:
            if self._gpu_manager is None:
                self._gpu_manager = GPUManager()
            
            gpu = self._gpu_manager.allocate_gpu(model_name)
            if gpu:
                return gpu.id
        except Exception as e:
            logger.warning(f"GPU allocation failed: {e}, using CPU")
        
        return None
    
    def _release_gpu(self):
        """释放 GPU 资源"""
        if self._gpu_id is not None and self._gpu_manager:
            try:
                self._gpu_manager.release_gpu(self._gpu_id)
            except Exception as e:
                logger.warning(f"GPU release failed: {e}")
            finally:
                self._gpu_id = None
    
    def update_task_status(self, task_id: str, status: str, **kwargs):
        """
        更新任务状态到数据库
        
        TODO: 集成数据库更新
        """
        logger.info(
            "task_status_update",
            task_id=task_id,
            status=status,
            **kwargs
        )
