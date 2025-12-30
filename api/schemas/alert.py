"""
告警相关数据模型

参考文档: docs/engineering_requirements.md 第七节
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from .response import PaginationInfo


class AlertLevel(str):
    """告警级别"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertRule(BaseModel):
    """告警规则"""
    id: UUID = Field(..., description="规则 ID")
    name: str = Field(..., description="规则名称")
    condition: Dict[str, Any] = Field(..., description="触发条件")
    level: str = Field(..., description="告警级别")
    enabled: bool = Field(..., description="是否启用")


class AlertRuleListResponse(BaseModel):
    """告警规则列表响应"""
    rules: List[AlertRule] = Field(..., description="规则列表")
    total: int = Field(..., description="规则总数")


class AlertInfo(BaseModel):
    """告警信息"""
    id: UUID = Field(..., description="告警 ID")
    rule_id: Optional[UUID] = Field(None, description="触发的规则 ID")
    level: str = Field(..., description="告警级别")
    alert_type: str = Field(..., description="告警类型")
    message: str = Field(..., description="告警消息")
    details: Dict[str, Any] = Field(default={}, description="详细信息")
    
    resolved: bool = Field(..., description="是否已解决")
    resolved_at: Optional[datetime] = Field(None, description="解决时间")
    
    created_at: datetime = Field(..., description="创建时间")


class AlertHistoryResponse(BaseModel):
    """告警历史响应"""
    items: List[AlertInfo] = Field(..., description="告警列表")
    pagination: PaginationInfo = Field(..., description="分页信息")


class ActiveAlertResponse(BaseModel):
    """活跃告警响应"""
    alerts: List[AlertInfo] = Field(..., description="活跃告警列表")
    total: int = Field(..., description="活跃告警数量")
