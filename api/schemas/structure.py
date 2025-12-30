"""
结构相关数据模型

参考文档: docs/architecture/database_design.md 3.4 节
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from .response import PaginationInfo


class StructureInfo(BaseModel):
    """结构信息"""
    id: UUID = Field(..., description="结构 ID")
    name: str = Field(..., description="结构名称")
    original_name: str = Field(..., description="原始文件名")
    format: str = Field(..., description="文件格式 (cif, xyz)")
    file_size: int = Field(..., description="文件大小 (bytes)")
    
    n_atoms: Optional[int] = Field(None, description="原子数")
    formula: Optional[str] = Field(None, description="化学式")
    
    is_builtin: bool = Field(default=False, description="是否为内置结构")
    created_at: datetime = Field(..., description="创建时间")


class StructureListResponse(BaseModel):
    """结构列表响应"""
    items: List[StructureInfo] = Field(..., description="结构列表")
    pagination: Optional[PaginationInfo] = Field(None, description="分页信息")


class StructureUploadResponse(BaseModel):
    """结构上传响应"""
    id: UUID = Field(..., description="结构 ID")
    name: str = Field(..., description="结构名称")
    format: str = Field(..., description="文件格式")
    n_atoms: int = Field(..., description="原子数")
    formula: str = Field(..., description="化学式")
    checksum: str = Field(..., description="文件 SHA256 校验和")
