"""
数据模型定义

使用 dataclass 定义 API 返回的数据结构，提供完整的类型注解。
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        )
    
    def is_success(self) -> bool:
        """是否成功"""
        return self == TaskStatus.COMPLETED


class TaskType(str, Enum):
    """任务类型枚举"""
    OPTIMIZATION = "optimization"
    STABILITY = "stability"
    BULK_MODULUS = "bulk-modulus"
    HEAT_CAPACITY = "heat-capacity"
    INTERACTION_ENERGY = "interaction-energy"
    SINGLE_POINT = "single-point"


class Priority(str, Enum):
    """任务优先级"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


@dataclass
class TaskInfo:
    """
    任务基本信息
    
    Attributes:
        task_id: 任务唯一标识符
        task_type: 任务类型
        status: 当前状态
        model: 使用的模型名称
        priority: 任务优先级
        created_at: 创建时间
        started_at: 开始执行时间
        completed_at: 完成时间
        progress: 执行进度 (0-100)
        error_message: 错误信息（如果失败）
    """
    task_id: str
    task_type: str
    status: str
    model: str
    priority: str = "NORMAL"
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    gpu_id: Optional[int] = None
    structure_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def status_enum(self) -> TaskStatus:
        """获取状态枚举"""
        return TaskStatus(self.status)
    
    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self.status_enum.is_terminal()
    
    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.status_enum.is_success()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskInfo":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", data.get("id", "")),
            task_type=data.get("task_type", data.get("type", "")),
            status=data.get("status", "PENDING"),
            model=data.get("model", ""),
            priority=data.get("priority", "NORMAL"),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress=data.get("progress", 0.0),
            error_message=data.get("error_message"),
            gpu_id=data.get("gpu_id"),
            structure_id=data.get("structure_id"),
            parameters=data.get("parameters", {}),
        )


@dataclass
class TaskResult:
    """
    任务执行结果
    
    不同任务类型有不同的结果字段，通过 result_data 获取原始数据。
    """
    task_id: str
    task_type: str
    status: str
    result_data: Dict[str, Any] = field(default_factory=dict)
    
    # 通用结果字段
    execution_time: Optional[float] = None
    gpu_time: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", data.get("id", "")),
            task_type=data.get("task_type", data.get("type", "")),
            status=data.get("status", "COMPLETED"),
            result_data=data.get("result", data),
            execution_time=data.get("execution_time"),
            gpu_time=data.get("gpu_time"),
        )
    
    # ===== 优化结果属性 =====
    
    @property
    def initial_energy(self) -> Optional[float]:
        """初始能量 (eV)"""
        return self.result_data.get("initial_energy")
    
    @property
    def final_energy(self) -> Optional[float]:
        """最终能量 (eV)"""
        return self.result_data.get("final_energy")
    
    @property
    def energy_change(self) -> Optional[float]:
        """能量变化 (eV)"""
        if self.initial_energy is not None and self.final_energy is not None:
            return self.final_energy - self.initial_energy
        return None
    
    @property
    def optimization_steps(self) -> Optional[int]:
        """优化步数"""
        return self.result_data.get("n_steps") or self.result_data.get("steps")
    
    @property
    def converged(self) -> Optional[bool]:
        """是否收敛"""
        return self.result_data.get("converged")
    
    @property
    def final_fmax(self) -> Optional[float]:
        """最终最大力 (eV/Å)"""
        return self.result_data.get("fmax") or self.result_data.get("final_fmax")
    
    @property
    def optimized_structure_file(self) -> Optional[str]:
        """优化后结构文件路径"""
        return self.result_data.get("output_file") or self.result_data.get("structure_file")
    
    # ===== 稳定性结果属性 =====
    
    @property
    def is_stable(self) -> Optional[bool]:
        """是否稳定"""
        return self.result_data.get("is_stable")
    
    @property
    def stability_score(self) -> Optional[float]:
        """稳定性得分"""
        return self.result_data.get("stability_score")
    
    @property
    def trajectory_file(self) -> Optional[str]:
        """轨迹文件路径"""
        return self.result_data.get("trajectory_file")
    
    @property
    def final_temperature(self) -> Optional[float]:
        """最终温度 (K)"""
        return self.result_data.get("final_temperature")
    
    @property
    def final_pressure(self) -> Optional[float]:
        """最终压力 (GPa)"""
        return self.result_data.get("final_pressure")
    
    # ===== 体积模量结果属性 =====
    
    @property
    def bulk_modulus(self) -> Optional[float]:
        """体积模量 (GPa)"""
        return self.result_data.get("bulk_modulus") or self.result_data.get("K0")
    
    @property
    def bulk_modulus_derivative(self) -> Optional[float]:
        """体积模量压力导数 K'"""
        return self.result_data.get("bulk_modulus_derivative") or self.result_data.get("K0_prime")
    
    @property
    def equilibrium_volume(self) -> Optional[float]:
        """平衡体积 (Å³)"""
        return self.result_data.get("equilibrium_volume") or self.result_data.get("V0")
    
    @property
    def equilibrium_energy(self) -> Optional[float]:
        """平衡能量 (eV)"""
        return self.result_data.get("equilibrium_energy") or self.result_data.get("E0")
    
    @property
    def fitting_r_squared(self) -> Optional[float]:
        """拟合 R² 值"""
        return self.result_data.get("r_squared") or self.result_data.get("fit_quality")
    
    # ===== 热容结果属性 =====
    
    @property
    def heat_capacity(self) -> Optional[float]:
        """热容 Cv (J/mol/K)"""
        return self.result_data.get("heat_capacity") or self.result_data.get("Cv")
    
    @property
    def entropy(self) -> Optional[float]:
        """熵 (J/mol/K)"""
        return self.result_data.get("entropy")
    
    @property
    def free_energy(self) -> Optional[float]:
        """自由能 (eV)"""
        return self.result_data.get("free_energy")
    
    # ===== 相互作用能结果属性 =====
    
    @property
    def interaction_energy(self) -> Optional[float]:
        """相互作用能 (eV)"""
        return self.result_data.get("interaction_energy")
    
    @property
    def binding_energy(self) -> Optional[float]:
        """结合能 (eV)"""
        return self.result_data.get("binding_energy")
    
    # ===== 单点能结果属性 =====
    
    @property
    def energy(self) -> Optional[float]:
        """总能量 (eV)"""
        return self.result_data.get("energy")
    
    @property
    def forces(self) -> Optional[List[List[float]]]:
        """原子力 (eV/Å)"""
        return self.result_data.get("forces")
    
    @property
    def stress(self) -> Optional[List[List[float]]]:
        """应力张量 (eV/Å³)"""
        return self.result_data.get("stress")


@dataclass
class StructureInfo:
    """
    结构文件信息
    
    Attributes:
        structure_id: 结构唯一标识符
        filename: 原始文件名
        format: 文件格式 (cif, xyz, poscar, pdb)
        n_atoms: 原子数
        formula: 化学式
        uploaded_at: 上传时间
    """
    structure_id: str
    filename: str
    format: str
    n_atoms: int = 0
    formula: str = ""
    space_group: Optional[str] = None
    cell_volume: Optional[float] = None
    uploaded_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructureInfo":
        """从字典创建"""
        return cls(
            structure_id=data.get("structure_id", data.get("id", "")),
            filename=data.get("filename", data.get("name", "")),
            format=data.get("format", data.get("file_format", "")),
            n_atoms=data.get("n_atoms", 0),
            formula=data.get("formula", ""),
            space_group=data.get("space_group"),
            cell_volume=data.get("cell_volume"),
            uploaded_at=data.get("uploaded_at", data.get("created_at")),
        )


@dataclass
class ModelInfo:
    """
    模型信息
    
    Attributes:
        name: 模型名称
        family: 模型系列 (mace, orb, fairchem, etc.)
        description: 模型描述
        supported_tasks: 支持的任务类型列表
        is_loaded: 是否已加载到 GPU
        gpu_id: 加载的 GPU ID
    """
    name: str
    family: str
    description: str = ""
    supported_tasks: List[str] = field(default_factory=list)
    is_loaded: bool = False
    gpu_id: Optional[int] = None
    memory_usage: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """从字典创建"""
        return cls(
            name=data.get("name", ""),
            family=data.get("family", ""),
            description=data.get("description", ""),
            supported_tasks=data.get("supported_tasks", []),
            is_loaded=data.get("is_loaded", False),
            gpu_id=data.get("gpu_id"),
            memory_usage=data.get("memory_usage"),
        )


@dataclass
class GPUInfo:
    """
    GPU 状态信息
    
    Attributes:
        gpu_id: GPU ID
        name: GPU 名称
        memory_total: 总显存 (GB)
        memory_used: 已用显存 (GB)
        memory_free: 可用显存 (GB)
        utilization: GPU 利用率 (%)
        temperature: 温度 (°C)
        is_available: 是否可用
        current_task: 当前运行的任务 ID
    """
    gpu_id: int
    name: str
    memory_total: float
    memory_used: float
    memory_free: float
    utilization: float = 0.0
    temperature: float = 0.0
    is_available: bool = True
    current_task: Optional[str] = None
    loaded_models: List[str] = field(default_factory=list)
    
    @property
    def memory_usage_percent(self) -> float:
        """显存使用百分比"""
        if self.memory_total > 0:
            return (self.memory_used / self.memory_total) * 100
        return 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GPUInfo":
        """从字典创建"""
        return cls(
            gpu_id=data.get("gpu_id", data.get("id", 0)),
            name=data.get("name", "Unknown GPU"),
            memory_total=data.get("memory_total", 0),
            memory_used=data.get("memory_used", 0),
            memory_free=data.get("memory_free", 0),
            utilization=data.get("utilization", 0),
            temperature=data.get("temperature", 0),
            is_available=data.get("is_available", True),
            current_task=data.get("current_task"),
            loaded_models=data.get("loaded_models", []),
        )


@dataclass
class QueueInfo:
    """
    任务队列状态信息
    
    Attributes:
        total_pending: 待处理任务数
        total_running: 运行中任务数
        by_priority: 按优先级分组的任务数
        estimated_wait_time: 预计等待时间 (秒)
    """
    total_pending: int = 0
    total_running: int = 0
    total_completed: int = 0
    total_failed: int = 0
    by_priority: Dict[str, int] = field(default_factory=dict)
    by_task_type: Dict[str, int] = field(default_factory=dict)
    estimated_wait_time: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueInfo":
        """从字典创建"""
        return cls(
            total_pending=data.get("total_pending", data.get("pending", 0)),
            total_running=data.get("total_running", data.get("running", 0)),
            total_completed=data.get("total_completed", data.get("completed", 0)),
            total_failed=data.get("total_failed", data.get("failed", 0)),
            by_priority=data.get("by_priority", {}),
            by_task_type=data.get("by_task_type", {}),
            estimated_wait_time=data.get("estimated_wait_time"),
        )


@dataclass
class PaginatedResult:
    """
    分页结果
    
    Attributes:
        items: 当前页数据
        total: 总数
        page: 当前页码
        page_size: 每页大小
        total_pages: 总页数
    """
    items: List[Any]
    total: int
    page: int
    page_size: int
    
    @property
    def total_pages(self) -> int:
        """总页数"""
        if self.page_size > 0:
            return (self.total + self.page_size - 1) // self.page_size
        return 0
    
    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_class: type = dict) -> "PaginatedResult":
        """从字典创建"""
        items_data = data.get("items", [])
        if item_class != dict and hasattr(item_class, "from_dict"):
            items = [item_class.from_dict(item) for item in items_data]
        else:
            items = items_data
        
        pagination = data.get("pagination", {})
        return cls(
            items=items,
            total=pagination.get("total", len(items)),
            page=pagination.get("page", 1),
            page_size=pagination.get("page_size", len(items)),
        )
