"""
模型相关数据模型

参考文档: docs/engineering_requirements.md 3.3、3.4 节
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ModelInfo(BaseModel):
    """模型信息"""
    name: str = Field(..., description="模型名称")
    framework: str = Field(..., description="模型框架 (mace, orb, omat24, grace, sevennet, mattersim)")
    description: Optional[str] = Field(None, description="模型描述")
    
    is_custom: bool = Field(default=False, description="是否为自定义模型")
    is_loaded: bool = Field(default=False, description="是否已加载到 GPU")
    loaded_gpu_id: Optional[int] = Field(None, description="加载到的 GPU ID")
    
    supported_elements: Optional[List[str]] = Field(None, description="支持的元素列表")
    with_d3: bool = Field(default=False, description="是否启用 D3 校正")
    
    config: Dict[str, Any] = Field(default={}, description="模型配置")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[ModelInfo] = Field(..., description="模型列表")
    total: int = Field(..., description="模型总数")


class CustomModelCreate(BaseModel):
    """自定义模型创建请求"""
    name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    framework: str = Field(..., description="模型框架")
    description: Optional[str] = Field(None, description="模型描述")
    with_d3: bool = Field(default=False, description="是否启用 D3 校正")
    config: Dict[str, Any] = Field(default={}, description="额外配置")


class CustomModelResponse(BaseModel):
    """自定义模型响应"""
    id: UUID = Field(..., description="模型 ID")
    name: str = Field(..., description="模型名称")
    framework: str = Field(..., description="模型框架")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(..., description="文件大小 (bytes)")
    
    is_validated: bool = Field(default=False, description="是否已验证")
    validation_message: Optional[str] = Field(None, description="验证消息")
    
    created_at: datetime = Field(..., description="创建时间")
