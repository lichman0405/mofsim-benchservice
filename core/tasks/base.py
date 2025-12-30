"""
任务执行器基类

定义统一的任务执行接口和通用功能
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
from pathlib import Path
import time
import traceback

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TaskContext:
    """任务执行上下文"""
    task_id: UUID
    task_type: str
    model_name: str
    gpu_id: Optional[int] = None
    work_dir: Optional[Path] = None
    structure_path: Optional[Path] = None
    structure_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 3600  # 默认 1 小时超时
    
    # 运行时信息
    start_time: Optional[float] = None
    peak_memory_mb: Optional[int] = None
    
    def log_context(self) -> Dict[str, Any]:
        """返回用于日志的上下文"""
        return {
            "task_id": str(self.task_id),
            "task_type": self.task_type,
            "model": self.model_name,
            "gpu_id": self.gpu_id,
        }


@dataclass 
class TaskResult:
    """任务执行结果"""
    success: bool
    task_id: UUID
    task_type: str
    
    # 结果数据（任务类型特定）
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 输出文件
    output_files: Dict[str, str] = field(default_factory=dict)
    
    # 性能指标
    duration_seconds: float = 0.0
    peak_memory_mb: Optional[int] = None
    
    # 错误信息
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "task_id": str(self.task_id),
            "task_type": self.task_type,
            "data": self.data,
            "output_files": self.output_files,
            "duration_seconds": self.duration_seconds,
            "peak_memory_mb": self.peak_memory_mb,
            "error_message": self.error_message,
        }


class TaskExecutor(ABC):
    """
    任务执行器基类
    
    所有任务类型都需要继承此类并实现 execute 方法。
    提供统一的执行流程：
    1. 准备（setup）
    2. 执行（execute）
    3. 清理（cleanup）
    """
    
    # 子类需要覆盖
    task_type: str = "base"
    
    # 默认参数
    default_parameters: Dict[str, Any] = {}
    
    def __init__(self, calculator=None):
        """
        初始化执行器
        
        Args:
            calculator: ASE Calculator 实例（可选，也可在 run 时传入）
        """
        self.calculator = calculator
        self._logger = logger.bind(executor=self.__class__.__name__)
    
    @abstractmethod
    def execute(self, atoms, context: TaskContext) -> Dict[str, Any]:
        """
        执行任务核心逻辑
        
        Args:
            atoms: ASE Atoms 对象（已附加 calculator）
            context: 任务上下文
            
        Returns:
            任务结果数据字典
        """
        pass
    
    def setup(self, context: TaskContext) -> None:
        """
        执行前准备
        
        可覆盖此方法进行任务特定的初始化
        """
        context.start_time = time.time()
        
        self._logger.info(
            "task_setup",
            **context.log_context()
        )
    
    def cleanup(self, context: TaskContext) -> None:
        """
        执行后清理
        
        可覆盖此方法进行资源清理
        """
        self._logger.info(
            "task_cleanup",
            **context.log_context()
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和合并参数
        
        Args:
            parameters: 用户提供的参数
            
        Returns:
            合并后的参数（默认参数 + 用户参数）
        """
        merged = self.default_parameters.copy()
        merged.update(parameters)
        return merged
    
    def run(
        self,
        atoms,
        context: TaskContext,
        calculator=None,
    ) -> TaskResult:
        """
        执行任务的完整流程
        
        Args:
            atoms: ASE Atoms 对象
            context: 任务上下文
            calculator: 可选的 calculator（覆盖实例 calculator）
            
        Returns:
            TaskResult 任务结果
        """
        start_time = time.time()
        
        # 使用提供的 calculator 或实例 calculator
        calc = calculator or self.calculator
        if calc is None:
            return TaskResult(
                success=False,
                task_id=context.task_id,
                task_type=self.task_type,
                error_message="No calculator provided",
                duration_seconds=time.time() - start_time,
            )
        
        # 附加 calculator 到 atoms
        atoms.calc = calc
        
        try:
            # 准备
            self.setup(context)
            
            # 验证参数
            validated_params = self.validate_parameters(context.parameters)
            context.parameters = validated_params
            
            self._logger.info(
                "task_executing",
                parameters=validated_params,
                **context.log_context()
            )
            
            # 执行核心逻辑
            result_data = self.execute(atoms, context)
            
            duration = time.time() - start_time
            
            self._logger.info(
                "task_completed",
                duration_seconds=round(duration, 2),
                **context.log_context()
            )
            
            return TaskResult(
                success=True,
                task_id=context.task_id,
                task_type=self.task_type,
                data=result_data.get("result", {}),
                output_files=result_data.get("output_files", {}),
                duration_seconds=duration,
                peak_memory_mb=context.peak_memory_mb,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_tb = traceback.format_exc()
            
            self._logger.error(
                "task_failed",
                error=str(e),
                duration_seconds=round(duration, 2),
                **context.log_context()
            )
            
            return TaskResult(
                success=False,
                task_id=context.task_id,
                task_type=self.task_type,
                error_message=str(e),
                error_traceback=error_tb,
                duration_seconds=duration,
                peak_memory_mb=context.peak_memory_mb,
            )
            
        finally:
            # 清理
            self.cleanup(context)
    
    def get_output_path(self, context: TaskContext, filename: str) -> Path:
        """获取输出文件路径"""
        if context.work_dir:
            return context.work_dir / filename
        return Path(filename)
    
    @staticmethod
    def get_atoms_info(atoms) -> Dict[str, Any]:
        """获取原子结构信息"""
        cell = atoms.get_cell()
        return {
            "n_atoms": len(atoms),
            "chemical_formula": atoms.get_chemical_formula(),
            "volume_A3": atoms.get_volume(),
            "cell_parameters": {
                "a": float(cell.lengths()[0]),
                "b": float(cell.lengths()[1]),
                "c": float(cell.lengths()[2]),
                "alpha": float(cell.angles()[0]),
                "beta": float(cell.angles()[1]),
                "gamma": float(cell.angles()[2]),
            }
        }
