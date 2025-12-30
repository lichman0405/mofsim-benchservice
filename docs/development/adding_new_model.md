# 添加新模型指南

## 一、概述

本文档指导开发者如何为 MOFSimBench 集成新的机器学习势能模型（MLIP）。

---

## 二、模型架构

### 2.1 现有模型

| 模型家族 | 可用模型 | 来源 |
|---------|---------|------|
| MACE | mace_off_prod, mace_mpa_prod | mace-torch |
| ORB | orb_v2_prod, orb_v2_mpa_prod | orb-models |
| OMAT24 | omat24_prod | fairchem |
| GRACE | grace_2l_oat_prod | sevenn |
| MatterSim | mattersim_prod | mattersim |
| SevenNet | 7net_prod | sevenn |
| PosEGNN | posegnn_prod | posegnn |
| MatGL | matgl_prod | matgl |

### 2.2 Calculator 接口

所有模型通过 ASE Calculator 接口统一访问：

```python
from ase.calculators.calculator import Calculator

class MLIPCalculator(Calculator):
    implemented_properties = ['energy', 'forces', 'stress']
    
    def calculate(self, atoms, properties, system_changes):
        # 计算能量、力、应力
        ...
```

---

## 三、添加新模型步骤

### 步骤 1：创建模型配置

在 `mof_benchmark/setup/calculators.yaml` 添加配置：

```yaml
# 新模型配置
new_model_prod:
  type: new_model
  name: "New Model Production"
  version: "1.0.0"
  checkpoint: "path/to/checkpoint.pt"
  device: "cuda"
  dtype: "float32"
  
  # 模型特定参数
  model_params:
    hidden_dim: 256
    num_layers: 6
  
  # D3 校正（如需要）
  d3_correction:
    enabled: true
    xc: "pbe"
    damping: "bj"
  
  # 资源需求
  resources:
    memory_mb: 8000
    supports_batch: true
    max_batch_size: 32
```

### 步骤 2：实现 Calculator 包装器

在 `mof_benchmark/setup/calculators/` 创建包装器：

```python
# mof_benchmark/setup/calculators/new_model.py

import torch
from ase.calculators.calculator import Calculator, all_changes
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

class NewModelCalculator(Calculator):
    """新模型的 ASE Calculator 包装器"""
    
    implemented_properties = ['energy', 'forces', 'stress']
    
    default_parameters = {
        'device': 'cuda',
        'dtype': 'float32',
    }
    
    def __init__(
        self,
        checkpoint: str,
        device: str = 'cuda',
        dtype: str = 'float32',
        d3_correction: bool = False,
        **kwargs
    ):
        """初始化计算器
        
        Args:
            checkpoint: 模型检查点路径
            device: 计算设备
            dtype: 数据类型
            d3_correction: 是否使用 D3 校正
        """
        super().__init__(**kwargs)
        
        self.device = torch.device(device)
        self.dtype = getattr(torch, dtype)
        self.checkpoint = checkpoint
        self.d3_correction = d3_correction
        
        # 加载模型
        self._load_model()
        
        # 可选：D3 校正
        if d3_correction:
            self._init_d3()
        
        logger.info(
            "Calculator 初始化完成",
            model="new_model",
            device=str(self.device),
            dtype=str(self.dtype)
        )
    
    def _load_model(self):
        """加载模型"""
        from new_model_lib import load_model  # 导入模型库
        
        self.model = load_model(
            self.checkpoint,
            device=self.device,
            dtype=self.dtype
        )
        self.model.eval()
        
        logger.info("模型加载完成", checkpoint=self.checkpoint)
    
    def _init_d3(self):
        """初始化 D3 校正"""
        from torch_dftd.torch_dftd3_calculator import TorchDFTD3Calculator
        
        self.d3_calc = TorchDFTD3Calculator(
            xc="pbe",
            damping="bj",
            device=self.device
        )
    
    def calculate(
        self,
        atoms=None,
        properties=['energy', 'forces'],
        system_changes=all_changes
    ):
        """执行计算"""
        super().calculate(atoms, properties, system_changes)
        
        # 1. 转换为模型输入格式
        inputs = self._atoms_to_input(atoms)
        
        # 2. 执行推理
        with torch.no_grad():
            outputs = self.model(inputs)
        
        # 3. 提取结果
        energy = outputs['energy'].item()
        forces = outputs['forces'].cpu().numpy()
        
        if 'stress' in properties:
            stress = outputs['stress'].cpu().numpy()
        else:
            stress = None
        
        # 4. 应用 D3 校正
        if self.d3_correction:
            d3_results = self.d3_calc.get_properties(atoms)
            energy += d3_results['energy']
            forces += d3_results['forces']
            if stress is not None:
                stress += d3_results['stress']
        
        # 5. 存储结果
        self.results['energy'] = energy
        self.results['forces'] = forces
        if stress is not None:
            self.results['stress'] = stress
    
    def _atoms_to_input(self, atoms) -> Dict[str, torch.Tensor]:
        """将 ASE Atoms 转换为模型输入"""
        positions = torch.tensor(
            atoms.get_positions(),
            dtype=self.dtype,
            device=self.device
        )
        
        atomic_numbers = torch.tensor(
            atoms.get_atomic_numbers(),
            dtype=torch.long,
            device=self.device
        )
        
        cell = torch.tensor(
            atoms.get_cell()[:],
            dtype=self.dtype,
            device=self.device
        )
        
        return {
            'positions': positions,
            'atomic_numbers': atomic_numbers,
            'cell': cell,
            'pbc': atoms.get_pbc()
        }
```

### 步骤 3：注册模型工厂

在 `mof_benchmark/setup/calculator.py` 注册：

```python
# mof_benchmark/setup/calculator.py

from mof_benchmark.setup.calculators.new_model import NewModelCalculator

# 模型工厂注册表
CALCULATOR_FACTORIES = {
    "mace": create_mace_calculator,
    "orb": create_orb_calculator,
    "omat24": create_omat24_calculator,
    "new_model": create_new_model_calculator,  # 新增
}

def create_new_model_calculator(config: dict) -> Calculator:
    """创建新模型计算器"""
    return NewModelCalculator(
        checkpoint=config["checkpoint"],
        device=config.get("device", "cuda"),
        dtype=config.get("dtype", "float32"),
        d3_correction=config.get("d3_correction", {}).get("enabled", False),
        **config.get("model_params", {})
    )
```

### 步骤 4：添加模型元数据

在 `core/models/registry.py` 注册：

```python
# core/models/registry.py

MODEL_REGISTRY = {
    "new_model_prod": ModelInfo(
        id="new_model_prod",
        name="New Model Production",
        family="new_model",
        version="1.0.0",
        description="新模型的描述",
        supported_elements=["H", "C", "N", "O", ...],
        max_atoms=5000,
        estimated_memory_mb=8000,
        supports_stress=True,
        supports_batch=True,
        d3_available=True,
        citation="Author et al., Journal, 2024"
    ),
}
```

---

## 四、自定义模型上传支持

### 4.1 上传接口

```python
# api/routers/models.py

@router.post("/upload")
async def upload_custom_model(
    model_file: UploadFile,
    config: CustomModelConfig,
    model_service: ModelService = Depends()
):
    """上传自定义模型"""
    
    # 验证文件
    if not model_file.filename.endswith(('.pt', '.pth', '.ckpt')):
        raise HTTPException(400, "不支持的文件格式")
    
    # 保存文件
    model_path = await model_service.save_model_file(model_file)
    
    # 验证模型
    try:
        await model_service.validate_model(model_path, config)
    except ModelValidationError as e:
        await model_service.delete_model_file(model_path)
        raise HTTPException(400, f"模型验证失败: {e}")
    
    # 注册模型
    model_id = await model_service.register_model(
        path=model_path,
        config=config
    )
    
    return {"model_id": model_id}
```

### 4.2 自定义模型配置

```python
# api/schemas/models.py

class CustomModelConfig(BaseModel):
    """自定义模型配置"""
    
    name: str = Field(..., description="模型名称")
    model_type: str = Field(..., description="模型类型")
    
    # 模型特定配置
    model_params: dict = Field(default_factory=dict)
    
    # 支持的元素
    supported_elements: Optional[List[str]] = None
    
    # 资源需求
    estimated_memory_mb: int = Field(default=8000)
    max_atoms: int = Field(default=1000)
```

---

## 五、测试新模型

### 5.1 基础测试

```python
# tests/unit/test_new_model_calculator.py

import pytest
from ase.build import bulk
from mof_benchmark.setup.calculators.new_model import NewModelCalculator

@pytest.fixture
def calculator():
    return NewModelCalculator(
        checkpoint="path/to/test_checkpoint.pt",
        device="cpu"
    )

class TestNewModelCalculator:
    def test_calculate_energy(self, calculator):
        atoms = bulk('Cu', 'fcc', a=3.6)
        atoms.calc = calculator
        
        energy = atoms.get_potential_energy()
        
        assert isinstance(energy, float)
        assert not np.isnan(energy)
    
    def test_calculate_forces(self, calculator):
        atoms = bulk('Cu', 'fcc', a=3.6)
        atoms.calc = calculator
        
        forces = atoms.get_forces()
        
        assert forces.shape == (len(atoms), 3)
        assert not np.any(np.isnan(forces))
```

### 5.2 与参考计算对比

```python
def test_energy_against_reference():
    """与 DFT 参考数据对比"""
    from ase.io import read
    
    # 加载参考结构和能量
    atoms = read("tests/data/reference_structure.cif")
    reference_energy = -1234.567  # DFT 参考能量
    
    # 计算
    atoms.calc = NewModelCalculator(...)
    predicted_energy = atoms.get_potential_energy()
    
    # 验证误差范围
    mae = abs(predicted_energy - reference_energy)
    assert mae < 0.1  # 误差 < 0.1 eV
```

---

## 六、性能优化

### 6.1 批量计算支持

```python
class NewModelCalculator(Calculator):
    def calculate_batch(
        self,
        atoms_list: List[Atoms],
        properties=['energy', 'forces']
    ) -> List[Dict]:
        """批量计算"""
        # 准备批量输入
        batch_inputs = [self._atoms_to_input(a) for a in atoms_list]
        batch_inputs = self._collate_batch(batch_inputs)
        
        # 批量推理
        with torch.no_grad():
            outputs = self.model(batch_inputs)
        
        # 解包结果
        return self._unbatch_outputs(outputs, len(atoms_list))
```

### 6.2 模型预热

```python
def warmup(self, sample_atoms: Atoms, n_warmup: int = 3):
    """预热模型，优化 CUDA 内核"""
    for _ in range(n_warmup):
        self.calculate(sample_atoms, ['energy', 'forces'])
    
    torch.cuda.synchronize()
    logger.info("模型预热完成")
```

---

## 七、检查清单

- [ ] 添加模型配置到 `calculators.yaml`
- [ ] 实现 ASE Calculator 包装器
- [ ] 注册到模型工厂
- [ ] 添加模型元数据
- [ ] 实现 D3 校正支持（如需要）
- [ ] 编写单元测试
- [ ] 与参考数据对比验证
- [ ] 测试 GPU 内存使用
- [ ] 更新模型目录文档
- [ ] 更新 CHANGELOG

---

## 八、常见问题

### 8.1 内存不足

- 检查 `estimated_memory_mb` 配置是否准确
- 考虑使用混合精度（`dtype: float16`）
- 限制批量大小

### 8.2 数值不稳定

- 检查模型输入预处理
- 验证原子类型映射
- 检查周期性边界条件处理

### 8.3 速度慢

- 确保使用 GPU
- 启用批量计算
- 检查是否有不必要的 CPU-GPU 数据传输

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
