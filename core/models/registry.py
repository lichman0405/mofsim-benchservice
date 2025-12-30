"""
模型注册表

管理所有可用的机器学习势能模型
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import yaml
import structlog

logger = structlog.get_logger(__name__)


class ModelStatus(str, Enum):
    """模型状态"""
    AVAILABLE = "available"      # 可用但未加载
    LOADING = "loading"          # 正在加载
    LOADED = "loaded"            # 已加载到 GPU
    UNLOADING = "unloading"      # 正在卸载
    ERROR = "error"              # 加载错误
    DISABLED = "disabled"        # 已禁用


class ModelFamily(str, Enum):
    """模型系列"""
    MACE = "mace"
    ORB = "orb"
    OMAT24 = "omat24"
    GRACE = "grace"
    SEVENNET = "sevennet"
    MATTERSIM = "mattersim"
    CUSTOM = "custom"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str                           # 模型名称（唯一标识）
    family: ModelFamily                 # 模型系列
    display_name: str                   # 显示名称
    description: str = ""               # 描述
    version: str = "1.0"                # 版本
    
    # 模型文件
    model_file: Optional[str] = None    # 模型文件路径
    checkpoint_path: Optional[str] = None  # 检查点路径
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 资源需求
    memory_gb: float = 4.0              # 预估显存需求 (GB)
    supports_gpu: bool = True           # 是否支持 GPU
    supports_cpu: bool = True           # 是否支持 CPU
    
    # 状态
    status: ModelStatus = ModelStatus.AVAILABLE
    loaded_on_gpus: List[int] = field(default_factory=list)
    
    # 元数据
    is_custom: bool = False             # 是否为自定义模型
    custom_model_id: Optional[str] = None  # 自定义模型 ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "family": self.family.value,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "memory_gb": self.memory_gb,
            "supports_gpu": self.supports_gpu,
            "supports_cpu": self.supports_cpu,
            "status": self.status.value,
            "loaded_on_gpus": self.loaded_on_gpus,
            "is_custom": self.is_custom,
        }


# 内置模型定义
BUILTIN_MODELS: Dict[str, Dict[str, Any]] = {
    # MACE 系列
    "mace_prod": {
        "family": ModelFamily.MACE,
        "display_name": "MACE-MP-0 Medium",
        "description": "MACE Materials Project foundation model",
        "model_file": "mace-mpa-0-medium.model",
        "memory_gb": 4.0,
    },
    "mace_prod_b3": {
        "family": ModelFamily.MACE,
        "display_name": "MACE-MP-0b3 Medium",
        "description": "MACE-MP-0b3 foundation model",
        "model_file": "mace-mp-0b3-medium.model",
        "memory_gb": 4.0,
    },
    "mace_prod_omat": {
        "family": ModelFamily.MACE,
        "display_name": "MACE-OMAT-0 Medium",
        "description": "MACE trained on OMAT dataset",
        "model_file": "mace-omat-0-medium.model",
        "memory_gb": 4.0,
    },
    "mace_prod_mof": {
        "family": ModelFamily.MACE,
        "display_name": "MACE4MOF",
        "description": "MACE fine-tuned for MOFs",
        "model_file": "mofs_v1.model",
        "memory_gb": 4.0,
    },
    "mace_prod_matpes": {
        "family": ModelFamily.MACE,
        "display_name": "MACE-MatPES",
        "description": "MACE MatPES r2SCAN OMAT fine-tuned",
        "model_file": "MACE-matpes-r2scan-omat-ft.model",
        "memory_gb": 4.0,
    },
    
    # ORB 系列
    "orb_prod": {
        "family": ModelFamily.ORB,
        "display_name": "ORB-D3-v2",
        "description": "ORB with D3 dispersion correction",
        "memory_gb": 6.0,
    },
    "orb_prod_mp": {
        "family": ModelFamily.ORB,
        "display_name": "ORB-MPTraj-v2",
        "description": "ORB trained on MP trajectories",
        "memory_gb": 6.0,
    },
    "orb_prod_v3": {
        "family": ModelFamily.ORB,
        "display_name": "ORB-v3 Conservative OMAT",
        "description": "ORB v3 conservative inference on OMAT",
        "memory_gb": 8.0,
    },
    "orb_prod_v3_mp": {
        "family": ModelFamily.ORB,
        "display_name": "ORB-v3 Conservative MPA",
        "description": "ORB v3 conservative inference on MPA",
        "memory_gb": 8.0,
    },
    "orb3": {
        "family": ModelFamily.ORB,
        "display_name": "ORB-v3 Direct OMAT",
        "description": "ORB v3 direct inference on OMAT",
        "memory_gb": 6.0,
    },
    
    # OMAT24 系列
    "omat24_prod": {
        "family": ModelFamily.OMAT24,
        "display_name": "eqV2-86M OMAT+MP",
        "description": "EquiformerV2 86M trained on OMAT+MP",
        "checkpoint_path": "eqV2_86M_omat_mp_salex.pt",
        "memory_gb": 8.0,
    },
    "omat24_prod_mp": {
        "family": ModelFamily.OMAT24,
        "display_name": "eqV2-86M MP",
        "description": "EquiformerV2 86M trained on MP",
        "checkpoint_path": "eqV2_dens_86M_mp.pt",
        "memory_gb": 8.0,
    },
    "omat24_prod_esen": {
        "family": ModelFamily.OMAT24,
        "display_name": "eSEN-30M OAM",
        "description": "eSEN 30M trained on OAM",
        "checkpoint_path": "esen_30m_oam.pt",
        "memory_gb": 4.0,
    },
    "omat24_prod_esen_mp": {
        "family": ModelFamily.OMAT24,
        "display_name": "eSEN-30M MPTraj",
        "description": "eSEN 30M trained on MPTraj",
        "checkpoint_path": "esen_30m_mptrj.pt",
        "memory_gb": 4.0,
    },
    
    # GRACE 系列
    "grace_prod": {
        "family": ModelFamily.GRACE,
        "display_name": "GRACE-2L-MP",
        "description": "GRACE 2-layer trained on Materials Project",
        "memory_gb": 4.0,
    },
    "grace_prod_oam": {
        "family": ModelFamily.GRACE,
        "display_name": "GRACE-2L-OAM",
        "description": "GRACE 2-layer trained on OAM",
        "memory_gb": 4.0,
    },
    "grace_prod_omat": {
        "family": ModelFamily.GRACE,
        "display_name": "GRACE-2L-OMAT",
        "description": "GRACE 2-layer trained on OMAT",
        "memory_gb": 4.0,
    },
    
    # SevenNet 系列
    "sevennet_prod": {
        "family": ModelFamily.SEVENNET,
        "display_name": "7net-0",
        "description": "SevenNet base model",
        "memory_gb": 4.0,
    },
    "sevennet_prod_l3i5": {
        "family": ModelFamily.SEVENNET,
        "display_name": "7net-L3I5",
        "description": "SevenNet L3I5 variant",
        "memory_gb": 4.0,
    },
    "sevennet_prod_ompa": {
        "family": ModelFamily.SEVENNET,
        "display_name": "7net-MF-OMPA",
        "description": "SevenNet multi-fidelity OMPA",
        "memory_gb": 6.0,
    },
    "sevennet_prod_ompa_omat": {
        "family": ModelFamily.SEVENNET,
        "display_name": "7net-MF-OMPA-OMAT",
        "description": "SevenNet multi-fidelity OMPA on OMAT",
        "memory_gb": 6.0,
    },
    
    # MatterSim 系列
    "mattersim_prod": {
        "family": ModelFamily.MATTERSIM,
        "display_name": "MatterSim-v1.0.0-5M",
        "description": "MatterSim 5M parameters",
        "memory_gb": 4.0,
    },
}


class ModelRegistry:
    """
    模型注册表
    
    管理所有可用的机器学习势能模型，包括：
    - 内置模型（MACE, ORB, OMAT24, GRACE, SevenNet, MatterSim）
    - 自定义上传模型
    """
    
    def __init__(self, calculators_yaml_path: Optional[Path] = None):
        """
        初始化模型注册表
        
        Args:
            calculators_yaml_path: calculators.yaml 文件路径
        """
        self._models: Dict[str, ModelInfo] = {}
        self._calculators_config: Dict[str, Any] = {}
        
        # 加载 calculators.yaml
        if calculators_yaml_path and calculators_yaml_path.exists():
            with open(calculators_yaml_path) as f:
                self._calculators_config = yaml.safe_load(f) or {}
        
        # 注册内置模型
        self._register_builtin_models()
        
        logger.info(
            "model_registry_initialized",
            n_models=len(self._models),
            families=list(set(m.family.value for m in self._models.values())),
        )
    
    def _register_builtin_models(self):
        """注册所有内置模型"""
        for name, config in BUILTIN_MODELS.items():
            # 合并 calculators.yaml 配置
            yaml_config = self._calculators_config.get(name, {})
            
            model_info = ModelInfo(
                name=name,
                family=config["family"],
                display_name=config["display_name"],
                description=config.get("description", ""),
                model_file=config.get("model_file") or yaml_config.get("model_file"),
                checkpoint_path=config.get("checkpoint_path") or yaml_config.get("checkpoint_path"),
                config=yaml_config,
                memory_gb=config.get("memory_gb", 4.0),
            )
            
            self._models[name] = model_info
    
    def register(self, model_info: ModelInfo) -> None:
        """
        注册模型
        
        Args:
            model_info: 模型信息
        """
        if model_info.name in self._models:
            logger.warning(f"Model {model_info.name} already registered, overwriting")
        
        self._models[model_info.name] = model_info
        logger.info("model_registered", name=model_info.name, family=model_info.family.value)
    
    def unregister(self, name: str) -> bool:
        """
        注销模型
        
        Args:
            name: 模型名称
            
        Returns:
            是否成功注销
        """
        if name in self._models:
            del self._models[name]
            logger.info("model_unregistered", name=name)
            return True
        return False
    
    def get(self, name: str) -> Optional[ModelInfo]:
        """
        获取模型信息
        
        Args:
            name: 模型名称
            
        Returns:
            模型信息，不存在则返回 None
        """
        return self._models.get(name)
    
    def get_all(self) -> List[ModelInfo]:
        """获取所有模型"""
        return list(self._models.values())
    
    def get_by_family(self, family: ModelFamily) -> List[ModelInfo]:
        """
        按模型系列获取
        
        Args:
            family: 模型系列
            
        Returns:
            该系列的所有模型
        """
        return [m for m in self._models.values() if m.family == family]
    
    def get_available(self) -> List[ModelInfo]:
        """获取所有可用（未禁用）的模型"""
        return [m for m in self._models.values() if m.status != ModelStatus.DISABLED]
    
    def get_loaded(self) -> List[ModelInfo]:
        """获取已加载的模型"""
        return [m for m in self._models.values() if m.status == ModelStatus.LOADED]
    
    def update_status(self, name: str, status: ModelStatus, gpu_id: Optional[int] = None) -> bool:
        """
        更新模型状态
        
        Args:
            name: 模型名称
            status: 新状态
            gpu_id: GPU ID（用于 loaded 状态）
            
        Returns:
            是否成功更新
        """
        model = self._models.get(name)
        if not model:
            return False
        
        old_status = model.status
        model.status = status
        
        if status == ModelStatus.LOADED and gpu_id is not None:
            if gpu_id not in model.loaded_on_gpus:
                model.loaded_on_gpus.append(gpu_id)
        elif status == ModelStatus.AVAILABLE:
            if gpu_id is not None and gpu_id in model.loaded_on_gpus:
                model.loaded_on_gpus.remove(gpu_id)
            else:
                model.loaded_on_gpus.clear()
        
        logger.info(
            "model_status_updated",
            name=name,
            old_status=old_status.value,
            new_status=status.value,
            gpu_id=gpu_id,
        )
        
        return True
    
    def exists(self, name: str) -> bool:
        """检查模型是否存在"""
        return name in self._models
    
    def list_names(self) -> List[str]:
        """获取所有模型名称"""
        return list(self._models.keys())
    
    def list_families(self) -> List[str]:
        """获取所有模型系列"""
        return list(set(m.family.value for m in self._models.values()))
    
    def get_summary(self) -> Dict[str, Any]:
        """获取注册表摘要"""
        by_family = {}
        by_status = {}
        
        for model in self._models.values():
            family = model.family.value
            status = model.status.value
            
            by_family[family] = by_family.get(family, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_models": len(self._models),
            "by_family": by_family,
            "by_status": by_status,
            "loaded_models": [m.name for m in self.get_loaded()],
        }


# 全局注册表实例
_registry: Optional[ModelRegistry] = None


def get_model_registry(calculators_yaml_path: Optional[Path] = None) -> ModelRegistry:
    """
    获取全局模型注册表实例
    
    Args:
        calculators_yaml_path: calculators.yaml 文件路径（首次调用时使用）
        
    Returns:
        模型注册表实例
    """
    global _registry
    
    if _registry is None:
        # 默认路径
        if calculators_yaml_path is None:
            calculators_yaml_path = Path(__file__).parent.parent.parent / "mof_benchmark" / "setup" / "calculators.yaml"
        
        _registry = ModelRegistry(calculators_yaml_path)
    
    return _registry
