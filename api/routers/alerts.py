"""
告警 API 路由

参考文档: docs/engineering_requirements.md 3.5 节、第七节
"""
from fastapi import APIRouter, Query, Path, HTTPException, Body
from typing import Optional

from api.schemas.alert import (
    AlertRule as AlertRuleSchema,
    AlertRuleListResponse,
    AlertHistoryResponse,
    ActiveAlertResponse,
    AlertInfo,
)
from api.schemas.response import APIResponse, PaginationInfo
from alerts import get_rule_engine, get_alert_notifier, AlertLevel

router = APIRouter()


@router.get("/rules", response_model=APIResponse[AlertRuleListResponse])
async def list_alert_rules():
    """
    获取告警规则列表
    
    返回所有已配置的告警规则，包括内置规则和自定义规则。
    """
    rule_engine = get_rule_engine()
    rules = rule_engine.list_rules()
    
    rule_schemas = []
    for rule in rules:
        rule_schemas.append(AlertRuleSchema(
            id=rule.id,
            name=rule.name,
            description=rule.description,
            condition={
                "metric": rule.condition.metric,
                "operator": rule.condition.operator,
                "threshold": rule.condition.threshold,
            },
            level=rule.level.value,
            enabled=rule.enabled,
        ))
    
    return APIResponse(
        success=True,
        data=AlertRuleListResponse(
            rules=rule_schemas,
            total=len(rule_schemas),
        ),
    )


@router.get("/rules/{rule_id}", response_model=APIResponse[AlertRuleSchema])
async def get_alert_rule(
    rule_id: str = Path(..., description="规则 ID"),
):
    """获取单个告警规则详情"""
    rule_engine = get_rule_engine()
    rule = rule_engine.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    return APIResponse(
        success=True,
        data=AlertRuleSchema(
            id=rule.id,
            name=rule.name,
            description=rule.description,
            condition={
                "metric": rule.condition.metric,
                "operator": rule.condition.operator,
                "threshold": rule.condition.threshold,
            },
            level=rule.level.value,
            enabled=rule.enabled,
        ),
    )


@router.put("/rules/{rule_id}/enable", response_model=APIResponse[dict])
async def enable_alert_rule(
    rule_id: str = Path(..., description="规则 ID"),
):
    """启用告警规则"""
    rule_engine = get_rule_engine()
    success = rule_engine.enable_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    return APIResponse(
        success=True,
        data={"message": f"Rule {rule_id} enabled"},
    )


@router.put("/rules/{rule_id}/disable", response_model=APIResponse[dict])
async def disable_alert_rule(
    rule_id: str = Path(..., description="规则 ID"),
):
    """禁用告警规则"""
    rule_engine = get_rule_engine()
    success = rule_engine.disable_rule(rule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    
    return APIResponse(
        success=True,
        data={"message": f"Rule {rule_id} disabled"},
    )


@router.get("/history", response_model=APIResponse[AlertHistoryResponse])
async def get_alert_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    level: Optional[str] = Query(None, description="按级别过滤 (CRITICAL, WARNING, INFO)"),
    resolved: Optional[bool] = Query(None, description="按是否解决过滤"),
):
    """
    获取告警历史
    
    支持分页和过滤。可按告警级别、是否解决进行筛选。
    """
    notifier = get_alert_notifier()
    
    # 解析级别过滤
    level_filter = None
    if level:
        try:
            level_filter = AlertLevel(level.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid level: {level}. Valid values: CRITICAL, WARNING, INFO"
            )
    
    all_alerts = notifier.get_history(level=level_filter, resolved=resolved)
    
    # 分页
    total = len(all_alerts)
    start = (page - 1) * page_size
    end = start + page_size
    page_alerts = all_alerts[start:end]
    
    # 转换为 schema
    alert_infos = []
    for alert in page_alerts:
        alert_infos.append(AlertInfo(
            id=alert.id,
            rule_id=alert.rule_id,
            level=alert.level.value,
            alert_type=alert.alert_type,
            message=alert.message,
            details=alert.details,
            resolved=alert.resolved,
            resolved_at=alert.resolved_at,
            created_at=alert.created_at,
        ))
    
    return APIResponse(
        success=True,
        data=AlertHistoryResponse(
            items=alert_infos,
            pagination=PaginationInfo(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
            ),
        ),
    )


@router.get("/active", response_model=APIResponse[ActiveAlertResponse])
async def get_active_alerts():
    """
    获取当前活跃（未解决）的告警
    
    返回所有尚未解决的告警，按时间倒序排列。
    """
    notifier = get_alert_notifier()
    active = notifier.get_active_alerts()
    
    alert_infos = []
    for alert in active:
        alert_infos.append(AlertInfo(
            id=alert.id,
            rule_id=alert.rule_id,
            level=alert.level.value,
            alert_type=alert.alert_type,
            message=alert.message,
            details=alert.details,
            resolved=alert.resolved,
            resolved_at=alert.resolved_at,
            created_at=alert.created_at,
        ))
    
    return APIResponse(
        success=True,
        data=ActiveAlertResponse(
            alerts=alert_infos,
            total=len(alert_infos),
        ),
    )


@router.post("/{alert_id}/resolve", response_model=APIResponse[dict])
async def resolve_alert(
    alert_id: str = Path(..., description="告警 ID"),
    resolved_by: str = Body("api_user", description="解决者"),
):
    """
    解决（确认）告警
    
    将告警标记为已解决状态。
    """
    notifier = get_alert_notifier()
    resolved = notifier.resolve(alert_id, resolved_by=resolved_by)
    
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    
    return APIResponse(
        success=True,
        data={
            "message": f"Alert {alert_id} resolved",
            "resolved_by": resolved_by,
        },
    )


@router.get("/stats", response_model=APIResponse[dict])
async def get_alert_stats():
    """
    获取告警统计信息
    
    返回告警数量统计（按级别、是否解决分组）。
    """
    notifier = get_alert_notifier()
    stats = notifier.get_stats()
    
    return APIResponse(
        success=True,
        data=stats,
    )
