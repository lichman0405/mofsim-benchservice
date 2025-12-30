"""
任务相关数据模型

参考文档: 
- docs/engineering_requirements.md 5.2、5.3 节
- docs/architecture/api_design.md 第三节
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from .response import PaginationInfo


class TaskType(str, Enum):
    """任务类型"""
    OPTIMIZATION = "optimization"
    STABILITY = "stability"
    BULK_MODULUS = "bulk-modulus"
    HEAT_CAPACITY = "heat-capacity"
    INTERACTION_ENERGY = "interaction-energy"
    SINGLE_POINT_ENERGY = "single-point-energy"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class TaskPriority(str, Enum):
    """任务优先级"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class StructureSource(BaseModel):
    """结构来源"""
    source: str = Field(..., description="来源类型: upload, builtin")
    file_id: Optional[str] = Field(None, description="上传文件 ID")
    name: Optional[str] = Field(None, description="内置结构名称")


class CallbackConfig(BaseModel):
    """回调配置"""
    url: str = Field(..., description="回调 URL")
    events: List[str] = Field(
        default=["task.completed", "task.failed"],
        description="回调事件"
    )
    secret: Optional[str] = Field(None, description="回调签名密钥")


class TaskOptions(BaseModel):
    """任务选项"""
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")
    timeout: int = Field(default=3600, ge=60, le=86400, description="超时时间（秒）")
    callback: Optional[CallbackConfig] = Field(None, description="回调配置")


class TaskCreate(BaseModel):
    """任务创建请求"""
    model: str = Field(..., description="模型名称，如 mace_prod")
    structure: StructureSource = Field(..., description="结构来源")
    parameters: Dict[str, Any] = Field(default={}, description="任务参数")
    options: TaskOptions = Field(default_factory=TaskOptions, description="任务选项")


class TaskBatchCreate(BaseModel):
    """批量任务创建请求"""
    tasks: List[TaskCreate] = Field(..., min_length=1, max_length=100, description="任务列表")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: UUID = Field(..., description="任务 ID")
    task_type: str = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    model: str = Field(..., description="使用的模型")
    priority: TaskPriority = Field(..., description="任务优先级")
    
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    position: Optional[int] = Field(None, description="队列位置")
    estimated_wait_seconds: Optional[int] = Field(None, description="预计等待时间")
    
    gpu_id: Optional[int] = Field(None, description="分配的 GPU")
    error_message: Optional[str] = Field(None, description="错误信息")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    items: List[TaskResponse] = Field(..., description="任务列表")
    pagination: PaginationInfo = Field(..., description="分页信息")


class TaskBatchResponse(BaseModel):
    """批量任务创建响应"""
    submitted: int = Field(..., description="成功提交数量")
    failed: int = Field(..., description="失败数量")
    task_ids: List[UUID] = Field(..., description="成功创建的任务 ID")
    errors: List[Dict[str, Any]] = Field(default=[], description="失败详情")


# ===== 任务结果相关 =====

class OptimizationResult(BaseModel):
    """优化任务结果"""
    converged: bool = Field(..., description="是否收敛")
    final_energy_eV: float = Field(..., description="最终能量 (eV)")
    final_fmax: float = Field(..., description="最终最大力 (eV/Å)")
    steps: int = Field(..., description="优化步数")
    initial_volume_A3: float = Field(..., description="初始体积 (Å³)")
    final_volume_A3: float = Field(..., description="最终体积 (Å³)")
    volume_change_percent: float = Field(..., description="体积变化百分比")
    cell_parameters: Dict[str, float] = Field(..., description="晶胞参数 (a, b, c, α, β, γ)")
    rmsd_from_initial: Optional[float] = Field(None, description="与初始结构的 RMSD")


class StabilityResult(BaseModel):
    """稳定性任务结果"""
    stable: bool = Field(..., description="是否稳定")
    final_temperature_K: float = Field(..., description="最终温度 (K)")
    final_pressure_bar: Optional[float] = Field(None, description="最终压力 (bar)")
    volume_stability: float = Field(..., description="体积稳定性指标")
    max_displacement_A: float = Field(..., description="最大原子位移 (Å)")
    coordination_change: Dict[str, Any] = Field(..., description="配位数变化")


class BulkModulusResult(BaseModel):
    """体积模量任务结果"""
    bulk_modulus_GPa: float = Field(..., description="体积模量 (GPa)")
    equilibrium_volume_A3: float = Field(..., description="平衡体积 (Å³)")
    pressure_derivative: float = Field(..., description="模量压力导数 B'")
    fitting_r_squared: float = Field(..., description="拟合 R²")


class HeatCapacityResult(BaseModel):
    """热容任务结果"""
    temperatures: List[float] = Field(..., description="温度列表 (K)")
    heat_capacities: List[float] = Field(..., description="热容列表 (J/mol·K)")
    cv_300K: float = Field(..., description="300K 热容")


class InteractionEnergyResult(BaseModel):
    """相互作用能任务结果"""
    interaction_energy_eV: float = Field(..., description="相互作用能 (eV)")
    binding_site: List[float] = Field(..., description="最佳吸附位点坐标 [x, y, z]")


class SinglePointResult(BaseModel):
    """单点能量任务结果"""
    energy_eV: float = Field(..., description="总能量 (eV)")
    forces: Optional[List[List[float]]] = Field(None, description="原子受力 (N×3)")
    stress: Optional[List[float]] = Field(None, description="应力张量 (6)")
    max_force: Optional[float] = Field(None, description="最大受力")


class TaskMetrics(BaseModel):
    """任务性能指标"""
    duration_seconds: float = Field(..., description="执行时长 (秒)")
    peak_gpu_memory_MB: Optional[int] = Field(None, description="峰值 GPU 显存 (MB)")
    avg_step_time_ms: Optional[float] = Field(None, description="平均步时间 (ms)")


class OutputFiles(BaseModel):
    """输出文件"""
    optimized_structure: Optional[str] = Field(None, description="优化后结构文件路径")
    trajectory: Optional[str] = Field(None, description="轨迹文件路径")
    log_file: Optional[str] = Field(None, description="日志文件路径")


class TaskResultResponse(BaseModel):
    """任务结果响应"""
    task_id: UUID = Field(..., description="任务 ID")
    task_type: str = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    model: str = Field(..., description="使用的模型")
    structure_name: str = Field(..., description="结构名称")
    
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    result: Dict[str, Any] = Field(..., description="任务结果（结构因类型而异）")
    output_files: OutputFiles = Field(..., description="输出文件")
    metrics: TaskMetrics = Field(..., description="性能指标")
