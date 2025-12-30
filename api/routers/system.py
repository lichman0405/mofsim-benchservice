"""
系统管理 API 路由

参考文档: docs/engineering_requirements.md 3.5 节
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from api.schemas.system import (
    HealthResponse,
    GPUStatusResponse,
    GPUInfo,
    QueueStatusResponse,
    QueueInfo,
    SystemConfigResponse,
)
from api.schemas.response import APIResponse
from api.dependencies import get_gpu_manager, get_priority_queue, get_scheduler
from core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/gpus", response_model=APIResponse[GPUStatusResponse])
async def get_gpu_status(gpu_manager=Depends(get_gpu_manager)):
    """
    获取各 GPU 使用情况
    
    返回:
    - 显存使用量
    - 温度
    - 当前运行的任务
    """
    # 刷新 GPU 状态
    gpu_manager.refresh_states()
    
    gpus = []
    available_count = 0
    
    for gpu_id, state in gpu_manager.gpu_states.items():
        gpus.append(GPUInfo(
            gpu_id=state.id,
            name=state.name,
            memory_total_MB=state.memory_total_mb,
            memory_used_MB=state.memory_used_mb,
            memory_free_MB=state.memory_free_mb,
            temperature_C=state.temperature_c if state.temperature_c > 0 else None,
            utilization_percent=state.utilization_percent if state.utilization_percent >= 0 else None,
            current_task_id=state.current_task_id,
            loaded_models=state.loaded_models,
        ))
        
        if state.is_available:
            available_count += 1
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=GPUStatusResponse(
            gpus=gpus,
            total_gpus=len(gpus),
            available_gpus=available_count,
        )
    )


@router.get("/queue", response_model=APIResponse[QueueStatusResponse])
async def get_queue_status(
    queue=Depends(get_priority_queue),
    gpu_manager=Depends(get_gpu_manager)
):
    """
    获取任务队列状态
    
    返回各优先级队列的任务数量
    """
    # 获取队列统计
    size_by_priority = queue.size_by_priority()
    
    queues = [
        QueueInfo(priority=priority, count=count)
        for priority, count in size_by_priority.items()
    ]
    
    # 计算运行中的任务数（忙碌的 GPU 数量）
    running_count = sum(
        1 for state in gpu_manager.gpu_states.values()
        if state.current_task_id is not None
    )
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=QueueStatusResponse(
            queues=queues,
            total_pending=queue.size(),
            total_running=running_count,
            total_completed_today=0,  # TODO: 从数据库获取
        )
    )


@router.get("/config", response_model=APIResponse[SystemConfigResponse])
async def get_system_config(gpu_manager=Depends(get_gpu_manager)):
    """获取当前系统配置（脱敏）"""
    from core.scheduler import Scheduler
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=SystemConfigResponse(
            gpu_count=len(gpu_manager.gpu_ids),
            max_concurrent_tasks=len(gpu_manager.gpu_ids),  # 每 GPU 一个任务
            default_timeout=settings.celery.task_soft_timeout,
            supported_models=list(Scheduler.MODEL_MEMORY_ESTIMATES.keys()),
            version=settings.version,
        )
    )


@router.get("/scheduler/stats")
async def get_scheduler_stats(scheduler=Depends(get_scheduler)):
    """获取调度器统计信息"""
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=scheduler.get_stats()
    )

