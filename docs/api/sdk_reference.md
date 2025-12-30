# SDK 参考文档

## 一、概述

本文档提供 MOFSimBench Python SDK 的完整 API 参考。

---

## 二、MOFSimClient

### 2.1 构造函数

```python
class MOFSimClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        debug: bool = False
    ):
        """初始化 MOFSimBench 客户端。
        
        Args:
            base_url: API 基础 URL。默认从环境变量 MOFSIM_BASE_URL 读取。
            api_key: API 密钥。默认从环境变量 MOFSIM_API_KEY 读取。
            timeout: 请求超时时间（秒）。
            max_retries: 最大重试次数。
            debug: 是否启用调试日志。
        
        Example:
            >>> client = MOFSimClient(
            ...     base_url="https://api.example.com/v1",
            ...     api_key="your_key"
            ... )
        """
```

### 2.2 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `optimization` | OptimizationAPI | 优化任务 API |
| `stability` | StabilityAPI | 稳定性分析 API |
| `bulk_modulus` | BulkModulusAPI | 体积模量计算 API |
| `heat_capacity` | HeatCapacityAPI | 热容计算 API |
| `interaction_energy` | InteractionEnergyAPI | 相互作用能 API |
| `single_point` | SinglePointAPI | 单点能量 API |

### 2.3 通用方法

```python
def get_task(self, task_id: str) -> Task:
    """获取任务对象。
    
    Args:
        task_id: 任务 ID
    
    Returns:
        Task: 任务对象
    
    Raises:
        TaskNotFoundError: 任务不存在
    """

def list_tasks(
    self,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Task]:
    """列出任务。
    
    Args:
        status: 状态过滤
        task_type: 任务类型过滤
        model: 模型过滤
        limit: 返回条数
        offset: 偏移量
    
    Returns:
        List[Task]: 任务列表
    """

def cancel_task(self, task_id: str) -> bool:
    """取消任务。
    
    Args:
        task_id: 任务 ID
    
    Returns:
        bool: 是否成功取消
    """

def retry_task(self, task_id: str) -> Task:
    """重试失败的任务。
    
    Args:
        task_id: 原任务 ID
    
    Returns:
        Task: 新任务对象
    """

def wait_all(
    self,
    tasks: List[Task],
    timeout: int = 3600,
    progress_bar: bool = False
) -> List[TaskResult]:
    """等待多个任务完成。
    
    Args:
        tasks: 任务列表
        timeout: 超时时间（秒）
        progress_bar: 是否显示进度条
    
    Returns:
        List[TaskResult]: 结果列表
    """

async def wait_all_async(
    self,
    tasks: List[Task],
    timeout: int = 3600
) -> List[TaskResult]:
    """异步等待多个任务完成。"""

def list_models(self) -> List[Model]:
    """列出可用模型。"""

def get_model(self, model_id: str) -> Model:
    """获取模型详情。"""

def upload_structure(
    self,
    file_path: str,
    name: Optional[str] = None
) -> str:
    """上传结构文件。
    
    Args:
        file_path: 文件路径
        name: 可选名称
    
    Returns:
        str: 文件 ID
    """

def list_builtin_structures(self) -> List[Structure]:
    """列出内置结构。"""

def get_system_stats(self) -> SystemStats:
    """获取系统状态。"""

def get_gpu_status(self) -> List[GPUStatus]:
    """获取 GPU 状态。"""
```

---

## 三、任务 API

### 3.1 OptimizationAPI

```python
class OptimizationAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        fmax: float = 0.001,
        max_steps: int = 500,
        optimizer: str = "LBFGS",
        trajectory_interval: int = 10,
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交优化任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径或内置结构名称
            fmax: 力收敛阈值 (eV/Å)
            max_steps: 最大优化步数
            optimizer: 优化器 (LBFGS, BFGS, FIRE)
            trajectory_interval: 轨迹保存间隔
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        
        Example:
            >>> task = client.optimization.submit(
            ...     model="mace_off_prod",
            ...     structure="./my_mof.cif",
            ...     fmax=0.001
            ... )
        """
```

### 3.2 StabilityAPI

```python
class StabilityAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        temperature_k: float = 300,
        timestep_fs: float = 1.0,
        total_steps: int = 1000,
        equilibration_steps: int = 100,
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交稳定性分析任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径或内置结构名称
            temperature_k: 模拟温度 (K)
            timestep_fs: 时间步长 (fs)
            total_steps: 总步数
            equilibration_steps: 平衡步数
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        """
```

### 3.3 BulkModulusAPI

```python
class BulkModulusAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        strain_range: float = 0.05,
        num_points: int = 5,
        fitting_method: str = "birch_murnaghan",
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交体积模量计算任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径
            strain_range: 应变范围
            num_points: 采样点数
            fitting_method: 拟合方法 (birch_murnaghan, murnaghan, vinet)
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        """
```

### 3.4 HeatCapacityAPI

```python
class HeatCapacityAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        temperature_range: Tuple[float, float] = (100, 500),
        temperature_step: float = 50,
        supercell: Tuple[int, int, int] = (2, 2, 2),
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交热容计算任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径
            temperature_range: 温度范围 (K)
            temperature_step: 温度步长 (K)
            supercell: 超胞大小
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        """
```

### 3.5 InteractionEnergyAPI

```python
class InteractionEnergyAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        adsorbate: str = "CO2",
        grid_spacing: float = 0.5,
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交相互作用能计算任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径
            adsorbate: 吸附质分子
            grid_spacing: 网格间距 (Å)
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        """
```

### 3.6 SinglePointAPI

```python
class SinglePointAPI:
    def submit(
        self,
        model: str,
        structure: Union[str, Path],
        compute_forces: bool = True,
        compute_stress: bool = False,
        priority: str = "NORMAL",
        webhook_url: Optional[str] = None
    ) -> Task:
        """提交单点能量计算任务。
        
        Args:
            model: 模型名称
            structure: 结构文件路径
            compute_forces: 是否计算力
            compute_stress: 是否计算应力
            priority: 优先级
            webhook_url: 完成回调 URL
        
        Returns:
            Task: 任务对象
        """
```

---

## 四、Task 类

```python
class Task:
    """任务对象"""
    
    @property
    def id(self) -> str:
        """任务 ID"""
    
    @property
    def task_type(self) -> str:
        """任务类型"""
    
    @property
    def status(self) -> str:
        """当前状态"""
    
    @property
    def progress(self) -> int:
        """进度百分比 (0-100)"""
    
    @property
    def model(self) -> str:
        """使用的模型"""
    
    @property
    def created_at(self) -> datetime:
        """创建时间"""
    
    @property
    def started_at(self) -> Optional[datetime]:
        """开始时间"""
    
    @property
    def completed_at(self) -> Optional[datetime]:
        """完成时间"""
    
    @property
    def gpu_id(self) -> Optional[int]:
        """分配的 GPU ID"""
    
    def refresh(self) -> "Task":
        """刷新任务状态。
        
        Returns:
            Task: 更新后的任务对象
        """
    
    def wait(
        self,
        timeout: int = 3600,
        poll_interval: int = 5
    ) -> TaskResult:
        """等待任务完成。
        
        Args:
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
        
        Returns:
            TaskResult: 任务结果
        
        Raises:
            TimeoutError: 等待超时
        """
    
    async def wait_async(
        self,
        timeout: int = 3600,
        poll_interval: int = 5
    ) -> TaskResult:
        """异步等待任务完成。"""
    
    def cancel(self) -> bool:
        """取消任务。
        
        Returns:
            bool: 是否成功取消
        """
    
    def get_logs(
        self,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """获取任务日志。"""
    
    def get_result(self) -> TaskResult:
        """获取任务结果。
        
        Raises:
            TaskNotCompletedError: 任务未完成
        """
```

---

## 五、结果类

### 5.1 TaskResult 基类

```python
class TaskResult:
    """任务结果基类"""
    
    @property
    def task_id(self) -> str:
        """任务 ID"""
    
    @property
    def success(self) -> bool:
        """是否成功"""
    
    @property
    def status(self) -> str:
        """最终状态"""
    
    @property
    def error(self) -> Optional[str]:
        """错误信息"""
    
    @property
    def execution_time_seconds(self) -> float:
        """执行时间"""
```

### 5.2 OptimizationResult

```python
class OptimizationResult(TaskResult):
    """优化任务结果"""
    
    @property
    def converged(self) -> bool:
        """是否收敛"""
    
    @property
    def steps(self) -> int:
        """优化步数"""
    
    @property
    def final_energy_eV(self) -> float:
        """最终能量 (eV)"""
    
    @property
    def max_force_eV_A(self) -> float:
        """最大力 (eV/Å)"""
    
    @property
    def energy_history(self) -> List[float]:
        """能量历史"""
    
    def save_structure(
        self,
        file_path: str,
        format: str = "cif"
    ) -> None:
        """保存优化后的结构。
        
        Args:
            file_path: 保存路径
            format: 文件格式 (cif, xyz, poscar)
        """
    
    def get_trajectory(self) -> List[Atoms]:
        """获取优化轨迹。
        
        Returns:
            List[Atoms]: ASE Atoms 列表
        """
```

### 5.3 StabilityResult

```python
class StabilityResult(TaskResult):
    """稳定性分析结果"""
    
    @property
    def stable(self) -> bool:
        """是否稳定"""
    
    @property
    def instability_reason(self) -> Optional[str]:
        """不稳定原因"""
    
    @property
    def max_displacement_A(self) -> float:
        """最大位移 (Å)"""
    
    @property
    def temperature_drift_K(self) -> float:
        """温度漂移 (K)"""
    
    @property
    def energy_drift_eV(self) -> float:
        """能量漂移 (eV)"""
```

### 5.4 BulkModulusResult

```python
class BulkModulusResult(TaskResult):
    """体积模量计算结果"""
    
    @property
    def bulk_modulus_GPa(self) -> float:
        """体积模量 (GPa)"""
    
    @property
    def equilibrium_volume_A3(self) -> float:
        """平衡体积 (Å³)"""
    
    @property
    def equilibrium_energy_eV(self) -> float:
        """平衡能量 (eV)"""
    
    @property
    def pressure_derivative(self) -> float:
        """压力导数 B'"""
    
    @property
    def volumes(self) -> List[float]:
        """采样体积"""
    
    @property
    def energies(self) -> List[float]:
        """对应能量"""
```

### 5.5 HeatCapacityResult

```python
class HeatCapacityResult(TaskResult):
    """热容计算结果"""
    
    @property
    def temperatures(self) -> List[float]:
        """温度列表 (K)"""
    
    @property
    def heat_capacities(self) -> List[float]:
        """热容列表 (J/(mol·K))"""
    
    @property
    def heat_capacity_at_300K(self) -> float:
        """300K 时的热容"""
    
    def plot(self, save_path: Optional[str] = None) -> None:
        """绘制热容-温度曲线"""
```

### 5.6 InteractionEnergyResult

```python
class InteractionEnergyResult(TaskResult):
    """相互作用能结果"""
    
    @property
    def interaction_energy_eV(self) -> float:
        """相互作用能 (eV)"""
    
    @property
    def adsorbate(self) -> str:
        """吸附质"""
    
    @property
    def binding_site(self) -> Tuple[float, float, float]:
        """最佳吸附位点坐标"""
```

### 5.7 SinglePointResult

```python
class SinglePointResult(TaskResult):
    """单点能量结果"""
    
    @property
    def energy_eV(self) -> float:
        """能量 (eV)"""
    
    @property
    def forces(self) -> Optional[np.ndarray]:
        """力 (N_atoms x 3)"""
    
    @property
    def max_force_eV_A(self) -> Optional[float]:
        """最大力"""
    
    @property
    def stress(self) -> Optional[np.ndarray]:
        """应力张量"""
```

---

## 六、数据类

### 6.1 Model

```python
class Model:
    """模型信息"""
    
    id: str
    name: str
    family: str
    version: str
    description: str
    supported_elements: List[str]
    max_atoms: int
    d3_available: bool
    citation: str
```

### 6.2 Structure

```python
class Structure:
    """结构信息"""
    
    name: str
    formula: str
    n_atoms: int
    category: str
    file_id: str
```

### 6.3 GPUStatus

```python
class GPUStatus:
    """GPU 状态"""
    
    id: int
    name: str
    status: str  # free, busy, error
    memory_used_mb: int
    memory_total_mb: int
    current_task: Optional[str]
    loaded_models: List[str]
```

---

## 七、异常类

```python
class MOFSimError(Exception):
    """基础异常类"""
    message: str
    code: int
    details: dict

class AuthenticationError(MOFSimError):
    """认证错误"""

class AuthorizationError(MOFSimError):
    """权限错误"""

class TaskNotFoundError(MOFSimError):
    """任务不存在"""

class ValidationError(MOFSimError):
    """验证错误"""

class RateLimitError(MOFSimError):
    """速率限制"""
    retry_after: int

class ServerError(MOFSimError):
    """服务器错误"""

class TimeoutError(MOFSimError):
    """超时错误"""

class TaskNotCompletedError(MOFSimError):
    """任务未完成"""
```

---

## 八、TUI 扩展接口

```python
class TUIExtension:
    """TUI 扩展基类"""
    
    @property
    def name(self) -> str:
        """扩展名称"""
        raise NotImplementedError
    
    @property
    def description(self) -> str:
        """扩展描述"""
        raise NotImplementedError
    
    def render(self, console: Console) -> Panel:
        """渲染扩展面板。
        
        Args:
            console: Rich Console 对象
        
        Returns:
            Panel: 渲染的面板
        """
        raise NotImplementedError
    
    def handle_input(self, key: str) -> bool:
        """处理键盘输入。
        
        Args:
            key: 按键
        
        Returns:
            bool: 是否处理了该输入
        """
        return False

# 注册扩展
from mofsim_sdk.tui import register_extension

@register_extension
class MyExtension(TUIExtension):
    name = "my_extension"
    description = "我的自定义扩展"
    
    def render(self, console):
        return Panel("自定义内容")
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
