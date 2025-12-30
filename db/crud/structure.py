"""
结构文件 CRUD 操作
"""
from typing import Optional, List
from uuid import UUID
import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from db.models import Structure


class StructureCRUD:
    """结构文件 CRUD 操作"""
    
    @staticmethod
    def create(
        db: Session,
        name: str,
        original_name: str,
        format: str,
        file_path: str,
        file_size: int,
        checksum: str,
        n_atoms: Optional[int] = None,
        formula: Optional[str] = None,
        is_builtin: bool = False,
    ) -> Structure:
        """创建结构记录"""
        structure = Structure(
            name=name,
            original_name=original_name,
            format=format,
            file_path=file_path,
            file_size=file_size,
            checksum=checksum,
            n_atoms=n_atoms,
            formula=formula,
            is_builtin=is_builtin,
        )
        
        db.add(structure)
        db.commit()
        db.refresh(structure)
        
        return structure
    
    @staticmethod
    def get_by_id(db: Session, structure_id: UUID) -> Optional[Structure]:
        """根据 ID 获取结构"""
        return db.query(Structure).filter(Structure.id == structure_id).first()
    
    @staticmethod
    def get_by_checksum(db: Session, checksum: str) -> Optional[Structure]:
        """根据校验和获取结构（用于去重）"""
        return db.query(Structure).filter(Structure.checksum == checksum).first()
    
    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Structure]:
        """根据名称获取结构"""
        return db.query(Structure).filter(Structure.name == name).first()
    
    @staticmethod
    def get_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        is_builtin: Optional[bool] = None,
    ) -> tuple:
        """获取结构列表"""
        query = db.query(Structure)
        
        if is_builtin is not None:
            query = query.filter(Structure.is_builtin == is_builtin)
        
        total = query.count()
        structures = query.order_by(Structure.name) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()
        
        return structures, total
    
    @staticmethod
    def get_builtin_structures(db: Session) -> List[Structure]:
        """获取所有内置结构"""
        return db.query(Structure) \
            .filter(Structure.is_builtin == True) \
            .order_by(Structure.name) \
            .all()
    
    @staticmethod
    def delete(db: Session, structure_id: UUID) -> bool:
        """删除结构记录"""
        structure = db.query(Structure).filter(Structure.id == structure_id).first()
        if not structure:
            return False
        
        db.delete(structure)
        db.commit()
        return True
    
    @staticmethod
    def calculate_checksum(file_path: str) -> str:
        """计算文件 SHA256 校验和"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
