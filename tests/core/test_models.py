"""
模型注册表和加载器测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from core.models.registry import (
    ModelRegistry, ModelInfo, ModelFamily, ModelStatus, 
    get_model_registry, BUILTIN_MODELS
)
from core.models.loader import ModelLoader, LoadedModel


# ===== ModelRegistry 测试 =====

class TestModelRegistry:
    """模型注册表测试"""
    
    def test_get_registry_function(self):
        """通过函数获取注册表"""
        registry = get_model_registry()
        assert registry is not None
        assert isinstance(registry, ModelRegistry)
    
    def test_get_all_models(self):
        """获取所有模型"""
        registry = get_model_registry()
        models = registry.get_all()
        
        assert len(models) > 0
        for model in models:
            assert isinstance(model, ModelInfo)
    
    def test_get_by_family(self):
        """按系列获取模型"""
        registry = get_model_registry()
        mace_models = registry.get_by_family(ModelFamily.MACE)
        
        for model in mace_models:
            assert model.family == ModelFamily.MACE
    
    def test_get_model(self):
        """获取单个模型"""
        registry = get_model_registry()
        models = registry.get_all()
        
        if models:
            model = registry.get(models[0].name)
            assert model is not None
            assert model.name == models[0].name
    
    def test_get_model_not_found(self):
        """获取不存在的模型"""
        registry = get_model_registry()
        model = registry.get("nonexistent_model_xyz_123")
        assert model is None
    
    def test_model_has_required_fields(self):
        """模型包含必需字段"""
        registry = get_model_registry()
        models = registry.get_all()
        
        for model in models:
            assert model.name
            assert model.family
            assert model.display_name
    
    def test_builtin_models_defined(self):
        """内置模型已定义"""
        assert len(BUILTIN_MODELS) > 0
        for name, config in BUILTIN_MODELS.items():
            assert "family" in config
            assert "display_name" in config


# ===== ModelInfo 测试 =====

class TestModelInfo:
    """ModelInfo 数据类测试"""
    
    def test_create_model_info(self):
        """创建模型信息"""
        info = ModelInfo(
            name="test_model",
            family=ModelFamily.MACE,
            display_name="Test Model",
            description="A test model",
        )
        
        assert info.name == "test_model"
        assert info.family == ModelFamily.MACE
        assert info.display_name == "Test Model"
    
    def test_model_info_defaults(self):
        """默认值"""
        info = ModelInfo(
            name="test",
            family=ModelFamily.MACE,
            display_name="Test",
        )
        
        assert info.status == ModelStatus.AVAILABLE
        assert info.memory_gb == 4.0
        assert info.supports_gpu is True
    
    def test_model_info_to_dict(self):
        """转换为字典"""
        info = ModelInfo(
            name="test",
            family=ModelFamily.MACE,
            display_name="Test",
        )
        
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["family"] == "mace"
        assert "status" in d


# ===== ModelFamily 枚举测试 =====

class TestModelFamily:
    """模型系列枚举测试"""
    
    def test_family_values(self):
        """系列值"""
        assert ModelFamily.MACE.value == "mace"
        assert ModelFamily.ORB.value == "orb"
        assert ModelFamily.GRACE.value == "grace"
    
    def test_family_from_string(self):
        """从字符串创建"""
        assert ModelFamily("mace") == ModelFamily.MACE
        assert ModelFamily("orb") == ModelFamily.ORB


# ===== ModelLoader 测试 =====

class TestModelLoader:
    """模型加载器测试"""
    
    def test_create_loader(self):
        """创建加载器"""
        loader = ModelLoader()
        assert loader is not None
    
    def test_loader_config(self):
        """加载器配置"""
        loader = ModelLoader(
            max_models_per_gpu=3,
            idle_timeout_seconds=1800,
        )
        
        assert loader.max_models_per_gpu == 3
        assert loader.idle_timeout_seconds == 1800


# ===== LoadedModel 测试 =====

class TestLoadedModel:
    """已加载模型测试"""
    
    def test_create_loaded_model(self):
        """创建已加载模型"""
        mock_calc = Mock()
        loaded = LoadedModel(
            name="test",
            calculator=mock_calc,
            gpu_id=0,
        )
        
        assert loaded.name == "test"
        assert loaded.gpu_id == 0
        assert loaded.use_count == 0
    
    def test_touch_updates_usage(self):
        """touch 更新使用统计"""
        mock_calc = Mock()
        loaded = LoadedModel(
            name="test",
            calculator=mock_calc,
            gpu_id=0,
        )
        
        initial_count = loaded.use_count
        loaded.touch()
        
        assert loaded.use_count == initial_count + 1
