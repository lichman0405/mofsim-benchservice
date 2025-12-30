"""
模型管理 API 路由

参考文档: docs/engineering_requirements.md 3.3 节
"""
from fastapi import APIRouter, Path, Query, UploadFile, File, Form, HTTPException
from typing import Optional, List
from uuid import UUID
import structlog

from api.schemas.model import (
    ModelInfo,
    ModelListResponse,
    CustomModelCreate,
    CustomModelResponse,
)
from api.schemas.response import APIResponse
from core.models.registry import get_model_registry, ModelStatus, ModelFamily
from core.models.loader import get_model_loader

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("", response_model=APIResponse[ModelListResponse])
async def list_models(
    family: Optional[str] = Query(None, description="按模型系列过滤"),
    status: Optional[str] = Query(None, description="按状态过滤 (available, loaded, disabled)"),
):
    """
    获取所有可用模型列表
    
    返回内置模型和自定义模型
    """
    registry = get_model_registry()
    
    models = registry.get_all()
    
    # 过滤
    if family:
        try:
            family_enum = ModelFamily(family)
            models = [m for m in models if m.family == family_enum]
        except ValueError:
            pass
    
    if status:
        try:
            status_enum = ModelStatus(status)
            models = [m for m in models if m.status == status_enum]
        except ValueError:
            pass
    
    # 转换为响应格式
    model_infos = []
    for m in models:
        model_infos.append(ModelInfo(
            name=m.name,
            framework=m.family.value,
            description=m.description,
            is_custom=m.is_custom,
            is_loaded=m.status == ModelStatus.LOADED,
            loaded_gpu_id=m.loaded_on_gpus[0] if m.loaded_on_gpus else None,
            with_d3=m.config.get("with_d3", False),
            config=m.config,
        ))
    
    return APIResponse(
        success=True,
        code=200,
        message="获取模型列表成功",
        data=ModelListResponse(models=model_infos, total=len(model_infos)),
    )


@router.get("/summary")
async def get_models_summary():
    """获取模型注册表摘要"""
    registry = get_model_registry()
    summary = registry.get_summary()
    
    return APIResponse(
        success=True,
        code=200,
        message="获取模型摘要成功",
        data=summary,
    )


@router.get("/families")
async def list_model_families():
    """获取所有模型系列"""
    registry = get_model_registry()
    families = registry.list_families()
    
    return APIResponse(
        success=True,
        code=200,
        message="获取模型系列成功",
        data={"families": families},
    )


@router.get("/{model_name}", response_model=APIResponse[ModelInfo])
async def get_model(model_name: str = Path(..., description="模型名称")):
    """获取模型详情"""
    registry = get_model_registry()
    model = registry.get(model_name)
    
    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    
    model_info = ModelInfo(
        name=model.name,
        framework=model.family.value,
        description=model.description,
        is_custom=model.is_custom,
        is_loaded=model.status == ModelStatus.LOADED,
        loaded_gpu_id=model.loaded_on_gpus[0] if model.loaded_on_gpus else None,
        with_d3=model.config.get("with_d3", False),
        config=model.config,
    )
    
    return APIResponse(success=True, code=200, message="获取模型详情成功", data=model_info)


@router.post("/{model_name}/load", response_model=APIResponse)
async def load_model(
    model_name: str = Path(..., description="模型名称"),
    gpu_id: int = Query(0, description="目标 GPU ID"),
):
    """
    预加载模型到 GPU
    
    - 提前加载模型可减少首次任务的启动时间
    """
    registry = get_model_registry()
    
    if not registry.exists(model_name):
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    
    try:
        loader = get_model_loader()
        loaded = loader.load(model_name, gpu_id)
        
        return APIResponse(
            success=True,
            code=200,
            message=f"Model {model_name} loaded on GPU {gpu_id}",
            data={
                "model": model_name,
                "gpu_id": gpu_id,
                "loaded_at": loaded.loaded_at,
            },
        )
    except Exception as e:
        logger.error("model_load_failed", model=model_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")


@router.post("/{model_name}/unload", response_model=APIResponse)
async def unload_model(
    model_name: str = Path(..., description="模型名称"),
    gpu_id: Optional[int] = Query(None, description="GPU ID，None 表示从所有 GPU 卸载"),
):
    """从 GPU 卸载模型，释放显存"""
    registry = get_model_registry()
    
    if not registry.exists(model_name):
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    
    loader = get_model_loader()
    success = loader.unload(model_name, gpu_id)
    
    if success:
        return APIResponse(
            success=True,
            code=200,
            message=f"Model {model_name} unloaded",
        )
    else:
        return APIResponse(
            success=False,
            code=400,
            message=f"Model {model_name} was not loaded",
        )


@router.get("/loaded/list")
async def list_loaded_models():
    """列出所有已加载的模型"""
    loader = get_model_loader()
    loaded = loader.list_loaded()
    
    return APIResponse(
        success=True,
        code=200,
        message="获取已加载模型列表成功",
        data=loaded,
    )


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
