"""
系统管理 API 路由

参考文档: docs/engineering_requirements.md 3.5 节
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio

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
from core.services.log_service import get_log_service
from logging_config.archive import get_archive_manager

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


@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, description="日志级别过滤"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
):
    """
    获取系统日志
    
    返回最近的系统日志条目
    """
    log_service = get_log_service()
    logs = log_service.get_system_logs(limit=limit, level=level)
    
    return APIResponse(
        success=True,
        code=200,
        message="获取系统日志成功",
        data={
            "logs": [log.to_dict() for log in logs],
            "count": len(logs),
        }
    )


@router.get("/logs/stream")
async def stream_system_logs():
    """
    系统日志实时流 (Server-Sent Events)
    
    通过 SSE 推送系统日志
    """
    log_service = get_log_service()
    
    async def generate():
        """SSE 事件生成器"""
        subscriber_id, queue = log_service.subscribe_system()
        
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.dumps(entry.to_dict(), ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            log_service.unsubscribe_system(subscriber_id)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/logs/stats")
async def get_log_stats():
    """获取日志统计信息"""
    log_service = get_log_service()
    archive_manager = get_archive_manager()
    
    return APIResponse(
        success=True,
        code=200,
        message="获取日志统计成功",
        data={
            "service": log_service.get_stats(),
            "archive": archive_manager.get_archive_stats(),
        }
    )


@router.post("/logs/archive")
async def trigger_log_archive():
    """
    触发日志归档
    
    手动触发日志压缩和归档操作
    """
    archive_manager = get_archive_manager()
    stats = archive_manager.archive()
    
    return APIResponse(
        success=True,
        code=200,
        message="日志归档完成",
        data=stats
    )


@router.get("/logs/archives")
async def list_log_archives():
    """列出所有日志归档"""
    archive_manager = get_archive_manager()
    archives = archive_manager.list_archives()
    
    return APIResponse(
        success=True,
        code=200,
        message="获取归档列表成功",
        data={"archives": archives}
    )

