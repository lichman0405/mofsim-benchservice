"""
告警 API 路由

参考文档: docs/engineering_requirements.md 3.5 节、第七节
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from api.schemas.alert import (
    AlertRuleListResponse,
    AlertHistoryResponse,
    ActiveAlertResponse,
)
from api.schemas.response import APIResponse

router = APIRouter()


@router.get("/rules", response_model=APIResponse[AlertRuleListResponse])
async def list_alert_rules():
    """获取告警规则列表"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 6")


@router.get("/history", response_model=APIResponse[AlertHistoryResponse])
async def get_alert_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    level: Optional[str] = Query(None, description="按级别过滤 (CRITICAL, WARNING, INFO)"),
):
    """获取告警历史"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 6")


@router.get("/active", response_model=APIResponse[ActiveAlertResponse])
async def get_active_alerts():
    """获取当前活跃（未解决）的告警"""
    raise HTTPException(status_code=501, detail="Not implemented yet - Phase 6")
