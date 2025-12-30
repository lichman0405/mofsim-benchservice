"""
结构服务测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from core.services.structure_service import StructureService, StructureFormat, StructureInfo


# ===== StructureService 测试 =====

class TestStructureService:
    """结构服务测试"""
    
    def test_create_service(self):
        """创建服务实例"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StructureService(storage_dir=tmpdir)
            assert service is not None
    
    def test_supported_formats(self):
        """支持的格式"""
        # 检查 StructureFormat 枚举
        assert StructureFormat.CIF.value == "cif"
        assert StructureFormat.XYZ.value == "xyz"
        assert StructureFormat.POSCAR.value == "poscar"
    
    def test_format_enum(self):
        """格式枚举"""
        assert StructureFormat.CIF == StructureFormat("cif")
        assert StructureFormat.XYZ == StructureFormat("xyz")


# ===== StructureInfo 测试 =====

class TestStructureInfo:
    """StructureInfo 数据类测试"""
    
    def test_create_info(self):
        """创建结构信息"""
        info = StructureInfo(
            id="struct-123",
            name="test.cif",
            format=StructureFormat.CIF,
            file_path=Path("/path/to/test.cif"),
            n_atoms=100,
            formula="Cu2O3",
        )
        
        assert info.id == "struct-123"
        assert info.name == "test.cif"
        assert info.format == StructureFormat.CIF
        assert info.n_atoms == 100
    
    def test_info_to_dict(self):
        """转换为字典"""
        info = StructureInfo(
            id="struct-123",
            name="test.cif",
            format=StructureFormat.CIF,
            file_path=Path("/path/to/test.cif"),
        )
        
        d = info.to_dict()
        assert d["id"] == "struct-123"
        assert d["name"] == "test.cif"
        assert d["format"] == "cif"
    
    def test_info_defaults(self):
        """默认值"""
        info = StructureInfo(
            id="test",
            name="test.cif",
            format=StructureFormat.CIF,
            file_path=Path("/test.cif"),
        )
        
        assert info.n_atoms == 0
        assert info.formula == ""
        assert info.is_valid is True


# ===== CIF 文件测试 =====

class TestCIFParsing:
    """CIF 文件解析测试"""
    
    @pytest.fixture
    def sample_cif_content(self):
        """示例 CIF 内容"""
        return """data_test
_cell_length_a   10.0
_cell_length_b   10.0
_cell_length_c   10.0
_cell_angle_alpha   90.0
_cell_angle_beta    90.0
_cell_angle_gamma   90.0
_symmetry_space_group_name_H-M   'P 1'

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Cu1 Cu 0.0 0.0 0.0
Cu2 Cu 0.5 0.5 0.5
"""
    
    def test_cif_file_creation(self, sample_cif_content):
        """CIF 文件创建"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
            f.write(sample_cif_content)
            temp_path = f.name
        
        try:
            assert os.path.exists(temp_path)
            with open(temp_path) as f:
                content = f.read()
            assert "Cu1" in content
        finally:
            os.unlink(temp_path)
