"""
系统管理 API 路由

参考文档: docs/engineering_requirements.md 3.5 节
"""
from fastapi import APIRouter, HTTPException

from api.schemas.system import (
    HealthResponse,
    GPUStatusResponse,
    QueueStatusResponse,
    SystemConfigResponse,
)
from api.schemas.response import APIResponse

router = APIRouter()


@router.get("/gpus", response_model=APIResponse[GPUStatusResponse])
async def get_gpu_status():
    """
    获取各 GPU 使用情况
    
    返回:
    - 显存使用量
    - 温度
    - 当前运行的任务
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 5")


@router.get("/queue", response_model=APIResponse[QueueStatusResponse])
async def get_queue_status():
    """
    获取任务队列状态
    
    返回各优先级队列的任务数量
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 5")


@router.get("/config", response_model=APIResponse[SystemConfigResponse])
async def get_system_config():
    """获取当前系统配置（脱敏）"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 5")
