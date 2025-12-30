"""
任务相关 API 路由

参考文档: docs/architecture/api_design.md 第三节
"""
from fastapi import APIRouter, Query, Path, HTTPException
from typing import Optional
from uuid import UUID

from api.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskResultResponse,
    TaskBatchCreate,
    TaskBatchResponse,
)
from api.schemas.response import APIResponse

router = APIRouter()


@router.post("/optimization", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_optimization_task(request: TaskCreate):
    """
    提交结构优化任务
    
    - 使用 BFGS 优化器配合 FrechetCellFilter 进行全松弛
    - 返回任务 ID 和队列位置
    """
    # TODO: Phase 2 实现任务提交逻辑
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/stability", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_stability_task(request: TaskCreate):
    """
    提交 MD 稳定性模拟任务
    
    - 支持 opt → NVT → NPT 三阶段
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/bulk-modulus", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_bulk_modulus_task(request: TaskCreate):
    """提交体积模量计算任务"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/heat-capacity", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_heat_capacity_task(request: TaskCreate):
    """提交热容计算任务（基于 phonopy）"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/interaction-energy", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_interaction_energy_task(request: TaskCreate):
    """提交相互作用能计算任务"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/single-point-energy", response_model=APIResponse[TaskResponse], status_code=202)
async def submit_single_point_task(request: TaskCreate):
    """提交单点能量计算任务"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/batch", response_model=APIResponse[TaskBatchResponse], status_code=202)
async def submit_batch_tasks(request: TaskBatchCreate):
    """批量提交任务"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.get("", response_model=APIResponse[TaskListResponse])
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态过滤"),
):
    """
    获取任务列表
    
    - 支持分页
    - 支持按状态过滤
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.get("/{task_id}", response_model=APIResponse[TaskResponse])
async def get_task(task_id: UUID = Path(..., description="任务 ID")):
    """获取任务详情"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.get("/{task_id}/result", response_model=APIResponse[TaskResultResponse])
async def get_task_result(task_id: UUID = Path(..., description="任务 ID")):
    """获取任务执行结果"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.post("/{task_id}/cancel", response_model=APIResponse)
async def cancel_task(task_id: UUID = Path(..., description="任务 ID")):
    """
    取消任务
    
    - 仅可取消 QUEUED 或 RUNNING 状态的任务
    """
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: UUID = Path(..., description="任务 ID"),
    level: Optional[str] = Query(None, description="日志级别过滤"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
):
    """获取任务日志"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 2")
