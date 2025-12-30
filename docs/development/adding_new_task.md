# 添加新任务类型指南

## 一、概述

本文档指导开发者如何为 MOFSimBench 添加新的计算任务类型。

---

## 二、任务类型架构

### 2.1 现有任务类型

| 任务类型 | 说明 | 核心模块 |
|---------|------|---------|
| optimization | 几何优化 | `mof_benchmark/analysis/optimization/` |
| stability | 稳定性分析 | `mof_benchmark/analysis/stability/` |
| bulk-modulus | 体积模量计算 | `mof_benchmark/analysis/bulk_modulus/` |
| heat-capacity | 热容计算 | `mof_benchmark/analysis/heat_capacity/` |
| interaction-energy | 相互作用能 | `mof_benchmark/analysis/interaction_energy/` |
| single-point-energy | 单点能量 | 基于 ASE Calculator |

### 2.2 任务类型类图

```
TaskExecutor (抽象基类)
├── OptimizationExecutor
├── StabilityExecutor
├── BulkModulusExecutor
├── HeatCapacityExecutor
├── InteractionEnergyExecutor
├── SinglePointExecutor
└── [YourNewExecutor]
```

---

## 三、添加新任务步骤

### 步骤 1：定义任务参数 Schema

在 `api/schemas/tasks/` 创建参数定义：

```python
# api/schemas/tasks/new_task.py

from pydantic import BaseModel, Field
from typing import Optional, List
from api.schemas.base import TaskBaseRequest

class NewTaskParameters(BaseModel):
    """新任务的参数定义"""
    
    param1: float = Field(
        default=0.01,
        description="参数1说明",
        ge=0.0,
        le=1.0
    )
    param2: int = Field(
        default=100,
        description="参数2说明"
    )
    optional_param: Optional[str] = Field(
        default=None,
        description="可选参数"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "param1": 0.05,
                "param2": 200
            }
        }

class NewTaskRequest(TaskBaseRequest):
    """新任务请求"""
    parameters: NewTaskParameters = Field(default_factory=NewTaskParameters)

class NewTaskResult(BaseModel):
    """新任务结果"""
    
    success: bool
    value: float
    unit: str
    additional_data: Optional[dict] = None
```

### 步骤 2：实现任务执行器

在 `core/tasks/executors/` 创建执行器：

```python
# core/tasks/executors/new_task_executor.py

import structlog
from typing import Dict, Any
from ase import Atoms

from core.tasks.base import TaskExecutor, TaskContext, TaskResult
from api.schemas.tasks.new_task import NewTaskParameters, NewTaskResult

logger = structlog.get_logger(__name__)

class NewTaskExecutor(TaskExecutor):
    """新任务执行器"""
    
    task_type = "new-task"
    
    # 预估内存需求（MB）
    estimated_memory_mb = 8000
    
    # 支持的模型类型
    supported_models = ["mace", "orb", "omat24"]
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> NewTaskParameters:
        """验证参数"""
        return NewTaskParameters(**parameters)
    
    async def execute(self, context: TaskContext) -> TaskResult:
        """执行任务"""
        log = logger.bind(task_id=context.task_id)
        
        # 1. 解析参数
        params = self.validate_parameters(context.parameters)
        log.info("参数验证通过", params=params.dict())
        
        # 2. 获取结构
        atoms: Atoms = context.atoms
        log.info("结构已加载", n_atoms=len(atoms))
        
        # 3. 获取计算器
        calculator = context.calculator
        atoms.calc = calculator
        
        # 4. 执行计算
        log.info("开始计算")
        
        try:
            # ===== 核心计算逻辑 =====
            result_value = self._perform_calculation(atoms, params)
            # ========================
            
            # 5. 构建结果
            result = NewTaskResult(
                success=True,
                value=result_value,
                unit="eV",
                additional_data={
                    "n_atoms": len(atoms),
                    "parameters": params.dict()
                }
            )
            
            log.info("计算完成", result=result.dict())
            
            return TaskResult(
                success=True,
                result=result.dict(),
                output_files={}
            )
            
        except Exception as e:
            log.error("计算失败", error=str(e), exc_info=True)
            return TaskResult(
                success=False,
                error_message=str(e)
            )
    
    def _perform_calculation(
        self, 
        atoms: Atoms, 
        params: NewTaskParameters
    ) -> float:
        """核心计算逻辑"""
        # 实现具体的计算逻辑
        energy = atoms.get_potential_energy()
        
        # 根据参数进行进一步计算
        # ...
        
        return energy
```

### 步骤 3：注册任务类型

在 `core/tasks/__init__.py` 注册：

```python
# core/tasks/__init__.py

from core.tasks.executors.optimization import OptimizationExecutor
from core.tasks.executors.new_task_executor import NewTaskExecutor

# 任务执行器注册表
TASK_EXECUTORS = {
    "optimization": OptimizationExecutor,
    "stability": StabilityExecutor,
    "bulk-modulus": BulkModulusExecutor,
    "heat-capacity": HeatCapacityExecutor,
    "interaction-energy": InteractionEnergyExecutor,
    "single-point-energy": SinglePointExecutor,
    "new-task": NewTaskExecutor,  # 新增
}

def get_executor(task_type: str) -> TaskExecutor:
    """获取任务执行器"""
    if task_type not in TASK_EXECUTORS:
        raise ValueError(f"未知任务类型: {task_type}")
    return TASK_EXECUTORS[task_type]()
```

### 步骤 4：添加 API 路由

在 `api/routers/tasks.py` 添加路由：

```python
# api/routers/tasks.py

from api.schemas.tasks.new_task import NewTaskRequest, NewTaskResult

@router.post(
    "/new-task",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交新任务",
    description="执行新类型的计算任务"
)
async def submit_new_task(
    request: NewTaskRequest,
    task_service: TaskService = Depends(get_task_service)
) -> TaskSubmitResponse:
    """提交新任务"""
    task_id = await task_service.submit(
        task_type="new-task",
        model=request.model,
        structure=request.structure,
        parameters=request.parameters.dict(),
        priority=request.priority,
        webhook_url=request.webhook_url
    )
    
    return TaskSubmitResponse(
        success=True,
        data={"task_id": task_id},
        message="任务已提交"
    )
```

### 步骤 5：添加 Celery 任务

在 `workers/tasks/new_task.py` 定义 Celery 任务：

```python
# workers/tasks/new_task.py

from celery import shared_task
from core.tasks import get_executor
from workers.base import GPUTask

@shared_task(bind=True, base=GPUTask)
def execute_new_task(self, task_id: str, gpu_id: int):
    """执行新任务的 Celery 任务"""
    executor = get_executor("new-task")
    return self.run_on_gpu(executor, task_id, gpu_id)
```

---

## 四、测试新任务

### 4.1 单元测试

```python
# tests/unit/test_new_task_executor.py

import pytest
from core.tasks.executors.new_task_executor import NewTaskExecutor
from api.schemas.tasks.new_task import NewTaskParameters

class TestNewTaskExecutor:
    def test_validate_parameters_success(self):
        executor = NewTaskExecutor()
        params = executor.validate_parameters({
            "param1": 0.05,
            "param2": 200
        })
        
        assert params.param1 == 0.05
        assert params.param2 == 200
    
    def test_validate_parameters_invalid(self):
        executor = NewTaskExecutor()
        
        with pytest.raises(ValueError):
            executor.validate_parameters({
                "param1": -1.0  # 无效值
            })
```

### 4.2 集成测试

```python
# tests/integration/test_new_task.py

import pytest

@pytest.mark.gpu
async def test_new_task_execution():
    from core.tasks import get_executor
    from core.tasks.base import TaskContext
    
    executor = get_executor("new-task")
    context = TaskContext(
        task_id="test_001",
        atoms=...,
        calculator=...,
        parameters={"param1": 0.05}
    )
    
    result = await executor.execute(context)
    
    assert result.success
    assert "value" in result.result
```

---

## 五、文档更新

添加新任务后，需要更新以下文档：

1. **API 参考**：`docs/api/api_reference.md`
2. **任务类型说明**：`docs/user/task_types_reference.md`
3. **SDK 文档**：`docs/api/sdk_reference.md`
4. **CHANGELOG**：`docs/CHANGELOG.md`

---

## 六、检查清单

- [ ] 定义参数 Schema（带验证和示例）
- [ ] 实现任务执行器
- [ ] 注册任务类型
- [ ] 添加 API 路由
- [ ] 添加 Celery 任务
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 更新 API 文档
- [ ] 更新用户文档
- [ ] 更新 CHANGELOG

---

## 七、示例：添加声子计算任务

以下是添加声子（Phonon）计算任务的完整示例：

### 7.1 参数 Schema

```python
# api/schemas/tasks/phonon.py

class PhononParameters(BaseModel):
    supercell: List[int] = Field(
        default=[2, 2, 2],
        description="超胞尺寸"
    )
    displacement: float = Field(
        default=0.01,
        description="位移量（Å）"
    )
    symmetry_precision: float = Field(
        default=1e-5,
        description="对称性精度"
    )
```

### 7.2 执行器

```python
# core/tasks/executors/phonon_executor.py

from phonopy import Phonopy

class PhononExecutor(TaskExecutor):
    task_type = "phonon"
    estimated_memory_mb = 16000  # 声子计算需要更多内存
    
    async def execute(self, context: TaskContext) -> TaskResult:
        params = self.validate_parameters(context.parameters)
        
        # 使用 phonopy 进行声子计算
        phonon = Phonopy(
            context.atoms,
            supercell_matrix=np.diag(params.supercell)
        )
        phonon.generate_displacements(distance=params.displacement)
        
        # 计算力
        forces = []
        for disp_atoms in phonon.supercells_with_displacements:
            disp_atoms.calc = context.calculator
            f = disp_atoms.get_forces()
            forces.append(f)
        
        phonon.forces = forces
        phonon.produce_force_constants()
        
        # 计算热力学性质
        phonon.run_thermal_properties(t_step=10, t_max=1000)
        
        return TaskResult(
            success=True,
            result={
                "frequencies": phonon.get_frequencies().tolist(),
                "thermal_properties": phonon.get_thermal_properties_dict()
            }
        )
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
