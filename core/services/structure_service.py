"""
结构文件服务

处理 CIF/XYZ 文件的上传、验证和管理
"""
from typing import Dict, List, Optional, Any, BinaryIO, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import hashlib
import shutil
import tempfile
import time
import uuid
import io

import ase
import ase.io
from ase import Atoms
import structlog

logger = structlog.get_logger(__name__)


class StructureFormat(str, Enum):
    """支持的结构文件格式"""
    CIF = "cif"
    XYZ = "xyz"
    POSCAR = "poscar"
    VASP = "vasp"
    PDB = "pdb"
    JSON = "json"  # ASE JSON format


@dataclass
class StructureInfo:
    """结构信息"""
    id: str                             # 唯一标识
    name: str                           # 结构名称
    format: StructureFormat             # 文件格式
    file_path: Path                     # 文件路径
    
    # 结构属性
    n_atoms: int = 0                    # 原子数
    formula: str = ""                   # 化学式
    elements: List[str] = field(default_factory=list)  # 元素列表
    volume: float = 0.0                 # 体积 (Å³)
    
    # 晶胞参数
    cell_a: float = 0.0
    cell_b: float = 0.0
    cell_c: float = 0.0
    cell_alpha: float = 0.0
    cell_beta: float = 0.0
    cell_gamma: float = 0.0
    
    # 元数据
    source: str = "upload"              # 来源
    uploaded_at: float = field(default_factory=time.time)
    file_hash: str = ""                 # 文件哈希
    file_size: int = 0                  # 文件大小
    
    # 验证状态
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "format": self.format.value,
            "n_atoms": self.n_atoms,
            "formula": self.formula,
            "elements": self.elements,
            "volume_A3": self.volume,
            "cell": {
                "a": self.cell_a,
                "b": self.cell_b,
                "c": self.cell_c,
                "alpha": self.cell_alpha,
                "beta": self.cell_beta,
                "gamma": self.cell_gamma,
            },
            "source": self.source,
            "uploaded_at": self.uploaded_at,
            "file_size": self.file_size,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


class StructureValidationError(Exception):
    """结构验证错误"""
    pass


class StructureService:
    """
    结构文件服务
    
    提供：
    - 结构文件上传
    - 格式验证
    - 结构解析
    - 文件管理
    """
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        ".cif": StructureFormat.CIF,
        ".xyz": StructureFormat.XYZ,
        ".poscar": StructureFormat.POSCAR,
        ".vasp": StructureFormat.VASP,
        ".pdb": StructureFormat.PDB,
        ".json": StructureFormat.JSON,
    }
    
    # ASE 格式映射
    ASE_FORMAT_MAP = {
        StructureFormat.CIF: "cif",
        StructureFormat.XYZ: "xyz",
        StructureFormat.POSCAR: "vasp",
        StructureFormat.VASP: "vasp",
        StructureFormat.PDB: "proteindatabank",
        StructureFormat.JSON: "json",
    }
    
    def __init__(
        self,
        storage_dir: Path,
        max_file_size_mb: int = 100,
        max_atoms: int = 10000,
    ):
        """
        初始化结构服务
        
        Args:
            storage_dir: 结构文件存储目录
            max_file_size_mb: 最大文件大小 (MB)
            max_atoms: 最大原子数
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size_mb * 1024 * 1024  # 转为字节
        self.max_atoms = max_atoms
        
        # 缓存: {structure_id: StructureInfo}
        self._cache: Dict[str, StructureInfo] = {}
        
        logger.info(
            "structure_service_initialized",
            storage_dir=str(self.storage_dir),
            max_file_size_mb=max_file_size_mb,
        )
    
    def upload(
        self,
        file_content: bytes,
        filename: str,
        source: str = "upload",
    ) -> StructureInfo:
        """
        上传结构文件
        
        Args:
            file_content: 文件内容
            filename: 文件名
            source: 来源标识
            
        Returns:
            StructureInfo 实例
            
        Raises:
            StructureValidationError: 验证失败
        """
        # 检查文件大小
        if len(file_content) > self.max_file_size:
            raise StructureValidationError(
                f"File too large: {len(file_content)} bytes > {self.max_file_size} bytes"
            )
        
        # 确定文件格式
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise StructureValidationError(
                f"Unsupported file format: {ext}. Supported: {list(self.SUPPORTED_EXTENSIONS.keys())}"
            )
        
        format_type = self.SUPPORTED_EXTENSIONS[ext]
        
        # 生成唯一 ID
        structure_id = str(uuid.uuid4())
        
        # 计算文件哈希
        file_hash = hashlib.sha256(file_content).hexdigest()[:16]
        
        # 保存文件
        safe_name = self._sanitize_filename(filename)
        file_path = self.storage_dir / f"{structure_id}_{safe_name}"
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 解析和验证结构
        try:
            atoms, validation_errors = self._parse_and_validate(
                file_path, format_type
            )
            
            # 创建 StructureInfo
            structure_info = self._create_structure_info(
                structure_id=structure_id,
                name=Path(filename).stem,
                format_type=format_type,
                file_path=file_path,
                atoms=atoms,
                file_hash=file_hash,
                file_size=len(file_content),
                source=source,
                validation_errors=validation_errors,
            )
            
            # 缓存
            self._cache[structure_id] = structure_info
            
            logger.info(
                "structure_uploaded",
                id=structure_id,
                name=structure_info.name,
                n_atoms=structure_info.n_atoms,
                formula=structure_info.formula,
            )
            
            return structure_info
            
        except Exception as e:
            # 删除已保存的文件
            if file_path.exists():
                file_path.unlink()
            raise StructureValidationError(f"Failed to parse structure: {e}") from e
    
    def upload_from_file(self, file_path: Path, source: str = "local") -> StructureInfo:
        """从本地文件上传"""
        with open(file_path, "rb") as f:
            content = f.read()
        return self.upload(content, file_path.name, source)
    
    def get(self, structure_id: str) -> Optional[StructureInfo]:
        """获取结构信息"""
        return self._cache.get(structure_id)
    
    def get_atoms(self, structure_id: str) -> Optional[Atoms]:
        """
        获取 ASE Atoms 对象
        
        Args:
            structure_id: 结构 ID
            
        Returns:
            ASE Atoms 对象
        """
        info = self.get(structure_id)
        if not info:
            return None
        
        format_str = self.ASE_FORMAT_MAP.get(info.format, info.format.value)
        return ase.io.read(str(info.file_path), format=format_str)
    
    def delete(self, structure_id: str) -> bool:
        """删除结构"""
        info = self._cache.pop(structure_id, None)
        if not info:
            return False
        
        # 删除文件
        if info.file_path.exists():
            info.file_path.unlink()
        
        logger.info("structure_deleted", id=structure_id, name=info.name)
        return True
    
    def list_all(self) -> List[StructureInfo]:
        """列出所有结构"""
        return list(self._cache.values())
    
    def validate(self, structure_id: str) -> Tuple[bool, List[str]]:
        """
        验证结构
        
        Returns:
            (is_valid, errors)
        """
        info = self.get(structure_id)
        if not info:
            return False, ["Structure not found"]
        
        return info.is_valid, info.validation_errors
    
    def _parse_and_validate(
        self,
        file_path: Path,
        format_type: StructureFormat,
    ) -> Tuple[Atoms, List[str]]:
        """解析和验证结构"""
        errors = []
        
        # 读取结构
        format_str = self.ASE_FORMAT_MAP.get(format_type, format_type.value)
        atoms = ase.io.read(str(file_path), format=format_str)
        
        # 验证原子数
        if len(atoms) > self.max_atoms:
            errors.append(f"Too many atoms: {len(atoms)} > {self.max_atoms}")
        
        if len(atoms) == 0:
            errors.append("Structure has no atoms")
        
        # 验证晶胞
        if not atoms.pbc.any():
            errors.append("No periodic boundary conditions")
        
        cell = atoms.get_cell()
        if cell.volume < 1e-6:
            errors.append("Cell volume is too small or zero")
        
        # 检查原子距离
        try:
            from ase.geometry import get_distances
            positions = atoms.get_positions()
            if len(positions) > 1:
                distances = atoms.get_all_distances(mic=True)
                min_dist = distances[distances > 0].min() if distances[distances > 0].size > 0 else float('inf')
                if min_dist < 0.5:
                    errors.append(f"Atoms too close: minimum distance = {min_dist:.2f} Å")
        except Exception:
            pass  # 忽略距离检查错误
        
        return atoms, errors
    
    def _create_structure_info(
        self,
        structure_id: str,
        name: str,
        format_type: StructureFormat,
        file_path: Path,
        atoms: Atoms,
        file_hash: str,
        file_size: int,
        source: str,
        validation_errors: List[str],
    ) -> StructureInfo:
        """创建 StructureInfo"""
        cell = atoms.get_cell()
        lengths = cell.lengths()
        angles = cell.angles()
        
        return StructureInfo(
            id=structure_id,
            name=name,
            format=format_type,
            file_path=file_path,
            n_atoms=len(atoms),
            formula=atoms.get_chemical_formula(),
            elements=list(set(atoms.get_chemical_symbols())),
            volume=atoms.get_volume(),
            cell_a=float(lengths[0]),
            cell_b=float(lengths[1]),
            cell_c=float(lengths[2]),
            cell_alpha=float(angles[0]),
            cell_beta=float(angles[1]),
            cell_gamma=float(angles[2]),
            source=source,
            file_hash=file_hash,
            file_size=file_size,
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors,
        )
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除不安全字符
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        return "".join(c if c in safe_chars else "_" for c in filename)


# 全局服务实例
_service: Optional[StructureService] = None


def get_structure_service(storage_dir: Optional[Path] = None, **kwargs) -> StructureService:
    """获取全局结构服务实例"""
    global _service
    
    if _service is None:
        if storage_dir is None:
            storage_dir = Path("storage/structures")
        _service = StructureService(storage_dir, **kwargs)
    
    return _service
