"""
模型管理 API 路由

参考文档: docs/engineering_requirements.md 3.3 节
"""
from fastapi import APIRouter, Path, Query, UploadFile, File, Form, HTTPException
from typing import Optional
from uuid import UUID

from api.schemas.model import (
    ModelInfo,
    ModelListResponse,
    CustomModelCreate,
    CustomModelResponse,
)
from api.schemas.response import APIResponse

router = APIRouter()


@router.get("", response_model=APIResponse[ModelListResponse])
async def list_models():
    """
    获取所有可用模型列表
    
    返回内置模型和自定义模型
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.get("/{model_name}", response_model=APIResponse[ModelInfo])
async def get_model(model_name: str = Path(..., description="模型名称")):
    """获取模型详情"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.post("/{model_name}/load", response_model=APIResponse)
async def load_model(
    model_name: str = Path(..., description="模型名称"),
    gpu_id: Optional[int] = Query(None, description="目标 GPU ID"),
):
    """
    预加载模型到 GPU
    
    - 提前加载模型可减少首次任务的启动时间
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.post("/{model_name}/unload", response_model=APIResponse)
async def unload_model(model_name: str = Path(..., description="模型名称")):
    """从 GPU 卸载模型，释放显存"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.post("/custom", response_model=APIResponse[CustomModelResponse])
async def upload_custom_model(
    file: UploadFile = File(..., description="模型文件 (.model, .pt, .pth)"),
    name: str = Form(..., description="模型名称"),
    framework: str = Form(..., description="模型框架 (mace, orb, sevennet, pytorch)"),
    description: Optional[str] = Form(None, description="模型描述"),
    with_d3: bool = Form(False, description="是否启用 D3 校正"),
):
    """
    上传自定义模型
    
    支持的格式:
    - MACE: .model
    - ORB/SevenNet: .pt, .pth
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.get("/custom", response_model=APIResponse[ModelListResponse])
async def list_custom_models():
    """获取已上传的自定义模型列表"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.delete("/custom/{model_id}", response_model=APIResponse)
async def delete_custom_model(model_id: UUID = Path(..., description="模型 ID")):
    """删除自定义模型"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")


@router.post("/custom/{model_id}/validate", response_model=APIResponse)
async def validate_custom_model(model_id: UUID = Path(..., description="模型 ID")):
    """
    验证自定义模型
    
    测试模型是否可正常加载和推理
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 3")
