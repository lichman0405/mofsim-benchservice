"""
任务相关 API 路由

参考文档: docs/architecture/api_design.md 第三节
"""
from fastapi import APIRouter, Query, Path, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID
import math
import asyncio
import json

from sqlalchemy.orm import Session

from api.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskResultResponse,
    TaskBatchCreate,
    TaskBatchResponse,
    TaskType,
    TaskStatus,
    TaskPriority,
    TaskMetrics,
    OutputFiles,
)
from api.schemas.response import APIResponse, PaginationInfo
from api.dependencies import get_db, get_priority_queue, get_gpu_manager
from api.middleware.error_handler import TaskNotFoundError
from core.services import TaskService
from core.services.log_service import get_log_service, TaskLogService
from db.models import TaskType as DBTaskType, TaskPriority as DBPriority

router = APIRouter()


def get_task_service(
    db: Session = Depends(get_db),
    queue = Depends(get_priority_queue),
    gpu_manager = Depends(get_gpu_manager),
) -> TaskService:
    """获取任务服务"""
    return TaskService(db=db, queue=queue, gpu_manager=gpu_manager)


def task_to_response(task, position: Optional[int] = None) -> TaskResponse:
    """将数据库 Task 转换为响应模型"""
    estimated_wait = None
    if position is not None and position > 0:
        estimated_wait = position * 300  # 每个任务约 5 分钟
    
    return TaskResponse(
        task_id=task.id,
        task_type=task.task_type.value,
        status=TaskStatus(task.status.value),
        model=task.model_name,
        priority=TaskPriority(task.priority.value),
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        position=position,
        estimated_wait_seconds=estimated_wait,
        gpu_id=task.gpu_id,
        error_message=task.error_message,
    )


@router.post("/optimization", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_optimization_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """
    提交结构优化任务
    
    - 使用 BFGS 优化器配合 FrechetCellFilter 进行全松弛
    - 返回任务 ID 和队列位置
    """
    task = service.submit_task(
        task_type=DBTaskType.OPTIMIZATION,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/stability", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_stability_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """
    提交 MD 稳定性模拟任务
    
    - 支持 opt → NVT → NPT 三阶段
    """
    task = service.submit_task(
        task_type=DBTaskType.STABILITY,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/bulk-modulus", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_bulk_modulus_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """提交体积模量计算任务"""
    task = service.submit_task(
        task_type=DBTaskType.BULK_MODULUS,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/heat-capacity", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_heat_capacity_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """提交热容计算任务（基于 phonopy）"""
    task = service.submit_task(
        task_type=DBTaskType.HEAT_CAPACITY,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/interaction-energy", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_interaction_energy_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """提交相互作用能计算任务"""
    task = service.submit_task(
        task_type=DBTaskType.INTERACTION_ENERGY,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/single-point-energy", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_single_point_task(
    request: TaskCreate,
    service: TaskService = Depends(get_task_service)
):
    """提交单点能量计算任务"""
    task = service.submit_task(
        task_type=DBTaskType.SINGLE_POINT_ENERGY,
        model_name=request.model,
        structure_id=UUID(request.structure.file_id) if request.structure.file_id else None,
        structure_name=request.structure.name,
        parameters=request.parameters,
        priority=DBPriority(request.options.priority.value),
        callback_url=request.options.callback.url if request.options.callback else None,
        callback_events=request.options.callback.events if request.options.callback else None,
        timeout=request.options.timeout,
    )
    
    position = service.get_queue_position(task.id)
    
    return APIResponse(
        success=True,
        code=202,
        message="任务已提交",
        data=task_to_response(task, position)
    )


@router.post("/batch", response_model=APIResponse[TaskBatchResponse], status_code=202)
async def submit_batch_tasks(
    request: TaskBatchCreate,
    task_type: str = Query(..., description="任务类型"),
    service: TaskService = Depends(get_task_service)
):
    """批量提交任务"""
    db_task_type = DBTaskType(task_type)
    
    # 转换请求数据
    tasks_data = []
    for task_req in request.tasks:
        tasks_data.append({
            "model": task_req.model,
            "structure": {
                "file_id": task_req.structure.file_id,
                "name": task_req.structure.name,
            },
            "parameters": task_req.parameters,
            "options": {
                "priority": task_req.options.priority.value,
                "timeout": task_req.options.timeout,
                "callback": {
                    "url": task_req.options.callback.url,
                    "events": task_req.options.callback.events,
                } if task_req.options.callback else None,
            }
        })
    
    successful_tasks, errors = service.submit_batch(db_task_type, tasks_data)
    
    return APIResponse(
        success=True,
        code=202,
        message=f"批量任务已提交: {len(successful_tasks)} 成功, {len(errors)} 失败",
        data=TaskBatchResponse(
            submitted=len(successful_tasks),
            failed=len(errors),
            task_ids=[t.id for t in successful_tasks],
            errors=errors,
        )
    )


@router.get("", response_model=APIResponse[TaskListResponse])
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    task_type: Optional[str] = Query(None, description="按任务类型过滤"),
    model: Optional[str] = Query(None, description="按模型过滤"),
    service: TaskService = Depends(get_task_service)
):
    """
    获取任务列表
    
    - 支持分页
    - 支持按状态、类型、模型过滤
    """
    tasks, total = service.list_tasks(
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        model_name=model,
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=TaskListResponse(
            items=[task_to_response(t) for t in tasks],
            pagination=PaginationInfo(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
            )
        )
    )


@router.get("/{task_id}", response_model=APIResponse[TaskResponse])
async def get_task(
    task_id: UUID = Path(..., description="任务 ID"),
    service: TaskService = Depends(get_task_service)
):
    """获取任务详情"""
    task, position = service.get_task_with_queue_position(task_id)
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=task_to_response(task, position)
    )


@router.get("/{task_id}/result", response_model=APIResponse[TaskResultResponse])
async def get_task_result(
    task_id: UUID = Path(..., description="任务 ID"),
    service: TaskService = Depends(get_task_service)
):
    """获取任务执行结果"""
    task = service.get_task(task_id)
    
    # 检查任务是否完成
    if task.status not in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, 
                           "COMPLETED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Task is still {task.status}, result not available yet"
        )
    
    # 构建结果响应
    duration = task.duration_seconds or 0
    if not duration and task.started_at and task.completed_at:
        duration = (task.completed_at - task.started_at).total_seconds()
    
    return APIResponse(
        success=True,
        code=200,
        message="查询成功",
        data=TaskResultResponse(
            task_id=task.id,
            task_type=task.task_type.value,
            status=TaskStatus(task.status.value),
            model=task.model_name,
            structure_name=task.structure_name or "unknown",
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            result=task.result or {},
            output_files=OutputFiles(
                optimized_structure=task.output_files.get("optimized_structure") if task.output_files else None,
                trajectory=task.output_files.get("trajectory") if task.output_files else None,
                log_file=task.output_files.get("log_file") if task.output_files else None,
            ),
            metrics=TaskMetrics(
                duration_seconds=duration,
                peak_gpu_memory_MB=task.peak_memory_mb,
                avg_step_time_ms=None,
            )
        )
    )


@router.post("/{task_id}/cancel", response_model=APIResponse)
async def cancel_task(
    task_id: UUID = Path(..., description="任务 ID"),
    service: TaskService = Depends(get_task_service)
):
    """
    取消任务
    
    - 仅可取消 PENDING, QUEUED, ASSIGNED, RUNNING 状态的任务
    """
    try:
        task = service.cancel_task(task_id)
        return APIResponse(
            success=True,
            code=200,
            message="任务已取消",
            data={"task_id": str(task.id), "status": task.status.value}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: UUID = Path(..., description="任务 ID"),
    level: Optional[str] = Query(None, description="日志级别过滤 (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: TaskService = Depends(get_task_service)
):
    """
    获取任务日志
    
    支持按级别过滤和分页查询
    """
    # 确保任务存在
    task = service.get_task(task_id)
    
    # 获取日志
    log_service = get_log_service()
    logs = log_service.get_task_logs(
        task_id=str(task_id),
        level=level,
        limit=limit,
        offset=offset,
    )
    
    return APIResponse(
        success=True,
        code=200,
        message="获取任务日志成功",
        data={
            "task_id": str(task_id),
            "logs": [log.to_dict() for log in logs],
            "count": len(logs),
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/{task_id}/logs/stream")
async def stream_task_logs(
    task_id: UUID = Path(..., description="任务 ID"),
    include_history: bool = Query(True, description="是否包含历史日志"),
    history_limit: int = Query(50, ge=0, le=500, description="历史日志条数"),
    service: TaskService = Depends(get_task_service)
):
    """
    实时日志流 (Server-Sent Events)
    
    通过 SSE 推送任务执行过程中的实时日志
    客户端可通过 EventSource API 订阅
    
    示例:
    ```javascript
    const evtSource = new EventSource('/api/v1/tasks/{task_id}/logs/stream');
    evtSource.onmessage = (event) => {
        console.log(JSON.parse(event.data));
    };
    ```
    """
    # 确保任务存在
    task = service.get_task(task_id)
    
    log_service = get_log_service()
    
    async def generate():
        """SSE 事件生成器"""
        async for entry in log_service.stream_task_logs(
            task_id=str(task_id),
            include_history=include_history,
            history_limit=history_limit,
        ):
            # SSE 格式: data: {...}\n\n
            if entry.message == "heartbeat":
                yield f": heartbeat\n\n"
            else:
                data = json.dumps(entry.to_dict(), ensure_ascii=False)
                yield f"data: {data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )

