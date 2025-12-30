"""
数据库 CRUD 操作模块
"""
from .task import TaskCRUD
from .structure import StructureCRUD

__all__ = [
    "TaskCRUD",
    "StructureCRUD",
]
