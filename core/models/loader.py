"""
模型加载器

加载和卸载机器学习势能模型
"""
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import os
import time
import threading
import structlog

from ase.calculators.calculator import Calculator

from .registry import ModelInfo, ModelStatus, ModelFamily, get_model_registry

logger = structlog.get_logger(__name__)


@dataclass
class LoadedModel:
    """已加载的模型"""
    name: str
    calculator: Calculator
    gpu_id: int
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    
    def touch(self):
        """更新最后使用时间"""
        self.last_used = time.time()
        self.use_count += 1


class ModelLoader:
    """
    模型加载器
    
    负责：
    - 加载模型到 GPU
    - 卸载模型释放显存
    - 管理模型缓存
    - 支持模型预热
    """
    
    def __init__(
        self,
        models_dir: Optional[Path] = None,
        max_models_per_gpu: int = 2,
        idle_timeout_seconds: int = 3600,
    ):
        """
        初始化模型加载器
        
        Args:
            models_dir: 模型文件目录
            max_models_per_gpu: 每个 GPU 最大加载模型数
            idle_timeout_seconds: 空闲超时自动卸载时间
        """
        self.models_dir = models_dir or Path(__file__).parent.parent.parent / "mof_benchmark" / "setup"
        self.max_models_per_gpu = max_models_per_gpu
        self.idle_timeout_seconds = idle_timeout_seconds
        
        # 已加载模型: {(model_name, gpu_id): LoadedModel}
        self._loaded: Dict[tuple, LoadedModel] = {}
        self._lock = threading.RLock()
        
        # 模型加载函数注册
        self._loaders: Dict[ModelFamily, Callable] = {
            ModelFamily.MACE: self._load_mace,
            ModelFamily.ORB: self._load_orb,
            ModelFamily.OMAT24: self._load_omat24,
            ModelFamily.GRACE: self._load_grace,
            ModelFamily.SEVENNET: self._load_sevennet,
            ModelFamily.MATTERSIM: self._load_mattersim,
            ModelFamily.CUSTOM: self._load_custom,
        }
        
        logger.info(
            "model_loader_initialized",
            models_dir=str(self.models_dir),
            max_models_per_gpu=max_models_per_gpu,
        )
    
    def load(
        self,
        model_name: str,
        gpu_id: int = 0,
        force_reload: bool = False,
    ) -> LoadedModel:
        """
        加载模型到指定 GPU
        
        Args:
            model_name: 模型名称
            gpu_id: GPU ID
            force_reload: 是否强制重新加载
            
        Returns:
            LoadedModel 实例
            
        Raises:
            ValueError: 模型不存在
            RuntimeError: 加载失败
        """
        key = (model_name, gpu_id)
        
        with self._lock:
            # 检查是否已加载
            if key in self._loaded and not force_reload:
                loaded = self._loaded[key]
                loaded.touch()
                logger.debug("model_cache_hit", model=model_name, gpu_id=gpu_id)
                return loaded
            
            # 获取模型信息
            registry = get_model_registry()
            model_info = registry.get(model_name)
            
            if not model_info:
                raise ValueError(f"Model not found: {model_name}")
            
            # 更新状态
            registry.update_status(model_name, ModelStatus.LOADING)
            
            try:
                # 设置 CUDA 设备
                os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
                
                # 加载模型
                loader = self._loaders.get(model_info.family)
                if not loader:
                    raise ValueError(f"No loader for model family: {model_info.family}")
                
                logger.info(
                    "loading_model",
                    model=model_name,
                    family=model_info.family.value,
                    gpu_id=gpu_id,
                )
                
                start_time = time.time()
                calculator = loader(model_info)
                load_time = time.time() - start_time
                
                # 创建 LoadedModel
                loaded = LoadedModel(
                    name=model_name,
                    calculator=calculator,
                    gpu_id=gpu_id,
                )
                
                self._loaded[key] = loaded
                
                # 更新状态
                registry.update_status(model_name, ModelStatus.LOADED, gpu_id)
                
                logger.info(
                    "model_loaded",
                    model=model_name,
                    gpu_id=gpu_id,
                    load_time_seconds=round(load_time, 2),
                )
                
                return loaded
                
            except Exception as e:
                registry.update_status(model_name, ModelStatus.ERROR)
                logger.error(
                    "model_load_failed",
                    model=model_name,
                    error=str(e),
                )
                raise RuntimeError(f"Failed to load model {model_name}: {e}") from e
    
    def unload(self, model_name: str, gpu_id: Optional[int] = None) -> bool:
        """
        卸载模型
        
        Args:
            model_name: 模型名称
            gpu_id: GPU ID，None 表示卸载所有 GPU 上的该模型
            
        Returns:
            是否成功卸载
        """
        with self._lock:
            keys_to_remove = []
            
            for key, loaded in self._loaded.items():
                if loaded.name == model_name:
                    if gpu_id is None or loaded.gpu_id == gpu_id:
                        keys_to_remove.append(key)
            
            if not keys_to_remove:
                return False
            
            registry = get_model_registry()
            
            for key in keys_to_remove:
                loaded = self._loaded.pop(key)
                
                # 清理计算器
                try:
                    del loaded.calculator
                except:
                    pass
                
                # 更新状态
                registry.update_status(model_name, ModelStatus.AVAILABLE, loaded.gpu_id)
                
                logger.info(
                    "model_unloaded",
                    model=model_name,
                    gpu_id=loaded.gpu_id,
                )
            
            # 尝试释放 GPU 显存
            self._cleanup_gpu_memory()
            
            return True
    
    def get(self, model_name: str, gpu_id: int) -> Optional[LoadedModel]:
        """
        获取已加载的模型
        
        Args:
            model_name: 模型名称
            gpu_id: GPU ID
            
        Returns:
            LoadedModel 或 None
        """
        with self._lock:
            loaded = self._loaded.get((model_name, gpu_id))
            if loaded:
                loaded.touch()
            return loaded
    
    def get_calculator(self, model_name: str, gpu_id: int = 0) -> Calculator:
        """
        获取模型计算器（自动加载）
        
        Args:
            model_name: 模型名称
            gpu_id: GPU ID
            
        Returns:
            ASE Calculator
        """
        loaded = self.get(model_name, gpu_id)
        if not loaded:
            loaded = self.load(model_name, gpu_id)
        return loaded.calculator
    
    def list_loaded(self) -> Dict[str, Any]:
        """列出所有已加载模型"""
        with self._lock:
            result = {}
            for (model_name, gpu_id), loaded in self._loaded.items():
                if model_name not in result:
                    result[model_name] = []
                result[model_name].append({
                    "gpu_id": gpu_id,
                    "loaded_at": loaded.loaded_at,
                    "last_used": loaded.last_used,
                    "use_count": loaded.use_count,
                })
            return result
    
    def cleanup_idle(self) -> int:
        """
        清理空闲模型
        
        Returns:
            清理的模型数量
        """
        now = time.time()
        to_unload = []
        
        with self._lock:
            for key, loaded in self._loaded.items():
                idle_time = now - loaded.last_used
                if idle_time > self.idle_timeout_seconds:
                    to_unload.append((loaded.name, loaded.gpu_id))
        
        count = 0
        for model_name, gpu_id in to_unload:
            if self.unload(model_name, gpu_id):
                count += 1
                logger.info(
                    "idle_model_unloaded",
                    model=model_name,
                    gpu_id=gpu_id,
                )
        
        return count
    
    def _cleanup_gpu_memory(self):
        """清理 GPU 显存"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        
        try:
            import gc
            gc.collect()
        except:
            pass
    
    # ================== 模型加载函数 ==================
    
    def _load_mace(self, model_info: ModelInfo) -> Calculator:
        """加载 MACE 模型"""
        from mace.calculators import mace_mp
        
        config = model_info.config
        device = config.get("device", "cuda")
        precision = config.get("precision", "float32")
        
        model_file = model_info.model_file
        if model_file:
            model_path = self.models_dir / model_file
            if model_path.exists():
                return mace_mp(
                    model=str(model_path),
                    device=device,
                    default_dtype=precision,
                )
        
        # 使用预训练模型
        return mace_mp(
            model="medium",
            device=device,
            default_dtype=precision,
        )
    
    def _load_orb(self, model_info: ModelInfo) -> Calculator:
        """加载 ORB 模型"""
        from orb_models.forcefield import pretrained
        from orb_models.forcefield.calculator import ORBCalculator
        
        config = model_info.config
        model_name = config.get("model_name", "orb-d3-v2")
        model_kwargs = config.get("model_kwargs", {})
        
        orbff = pretrained.orb_v2(model_name, **model_kwargs)
        return ORBCalculator(orbff, device="cuda")
    
    def _load_omat24(self, model_info: ModelInfo) -> Calculator:
        """加载 OMAT24/EquiformerV2 模型"""
        from fairchem.core import OCPCalculator
        
        config = model_info.config
        checkpoint = model_info.checkpoint_path or config.get("checkpoint_path")
        
        checkpoint_path = self.models_dir / checkpoint if checkpoint else None
        
        return OCPCalculator(
            checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
            cpu=False,
        )
    
    def _load_grace(self, model_info: ModelInfo) -> Calculator:
        """加载 GRACE 模型"""
        from grace.calculator import GraceCalculator
        
        config = model_info.config
        model_name = config.get("model_name", "GRACE-2L-MP-r6")
        
        return GraceCalculator(model=model_name)
    
    def _load_sevennet(self, model_info: ModelInfo) -> Calculator:
        """加载 SevenNet 模型"""
        from sevenn.sevennet_calculator import SevenNetCalculator
        
        config = model_info.config
        model_name = config.get("model_name", "7net-0")
        kwargs = config.get("kwargs", {})
        
        return SevenNetCalculator(model=model_name, **kwargs)
    
    def _load_mattersim(self, model_info: ModelInfo) -> Calculator:
        """加载 MatterSim 模型"""
        from mattersim.forcefield import MatterSimCalculator
        
        config = model_info.config
        load_path = config.get("load_path", "MatterSim-v1.0.0-5M.pth")
        
        return MatterSimCalculator(load_path=load_path)
    
    def _load_custom(self, model_info: ModelInfo) -> Calculator:
        """加载自定义模型"""
        # 自定义模型需要指定加载方式
        raise NotImplementedError("Custom model loading not implemented")


# 全局加载器实例
_loader: Optional[ModelLoader] = None


def get_model_loader(**kwargs) -> ModelLoader:
    """获取全局模型加载器实例"""
    global _loader
    
    if _loader is None:
        _loader = ModelLoader(**kwargs)
    
    return _loader
