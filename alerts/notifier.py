"""
告警通知器

参考文档: docs/engineering_requirements.md 7.3 节
通过多种渠道发送告警通知
"""
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
import structlog

from .rules import AlertRule, AlertLevel

logger = structlog.get_logger(__name__)


@dataclass
class Alert:
    """告警实例"""
    id: str
    rule_id: str
    alert_type: str
    level: AlertLevel
    message: str
    details: Dict[str, Any]
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    notified_channels: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "alert_type": self.alert_type,
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() + "Z",
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() + "Z" if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "notified_channels": self.notified_channels,
        }


class AlertNotifier:
    """
    告警通知器
    
    功能:
    - 多渠道通知（日志、Webhook、文件）
    - 告警记录存储
    - 告警解决管理
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        alert_file_path: str = "logs/alerts.log",
        max_history: int = 1000,
    ):
        self.webhook_url = webhook_url
        self.alert_file_path = Path(alert_file_path)
        self.max_history = max_history
        
        # 告警历史
        self._alerts: List[Alert] = []
        self._active_alerts: Dict[str, Alert] = {}
        
        # 确保目录存在
        self.alert_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def notify(
        self,
        rule: AlertRule,
        metrics: Dict[str, float],
    ) -> Alert:
        """
        发送告警通知
        
        Args:
            rule: 触发的规则
            metrics: 当前指标值
        
        Returns:
            创建的告警实例
        """
        # 创建告警
        alert = Alert(
            id=f"alert_{uuid.uuid4().hex[:12]}",
            rule_id=rule.id,
            alert_type=rule.alert_type.value,
            level=rule.level,
            message=self._format_message(rule, metrics),
            details={
                "rule_name": rule.name,
                "condition": rule.condition.to_dict(),
                "metrics": metrics,
                "trigger_count": rule.trigger_count,
            },
            created_at=datetime.utcnow(),
        )
        
        # 通过各渠道发送
        for channel in rule.notification_channels:
            try:
                if channel == "log":
                    await self._notify_log(alert)
                elif channel == "webhook":
                    await self._notify_webhook(alert)
                elif channel == "file":
                    await self._notify_file(alert)
                
                alert.notified_channels.append(channel)
            except Exception as e:
                logger.error(
                    "alert_notification_failed",
                    alert_id=alert.id,
                    channel=channel,
                    error=str(e),
                )
        
        # 保存告警
        self._save_alert(alert)
        
        return alert
    
    def _format_message(self, rule: AlertRule, metrics: Dict[str, float]) -> str:
        """格式化告警消息"""
        metric_value = metrics.get(rule.condition.metric, "N/A")
        return (
            f"{rule.name}: {rule.description} "
            f"(当前值: {metric_value}, 阈值: {rule.condition.operator} {rule.condition.threshold})"
        )
    
    async def _notify_log(self, alert: Alert) -> None:
        """通过日志通知"""
        log_method = logger.critical if alert.level == AlertLevel.CRITICAL else (
            logger.warning if alert.level == AlertLevel.WARNING else logger.info
        )
        
        log_method(
            "alert_triggered",
            alert_id=alert.id,
            alert_type=alert.alert_type,
            level=alert.level.value,
            message=alert.message,
            details=alert.details,
        )
    
    async def _notify_webhook(self, alert: Alert) -> None:
        """通过 Webhook 通知"""
        if not self.webhook_url:
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json={
                        "type": "alert",
                        "alert": alert.to_dict(),
                    },
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "MOFSimBench-Alert/1.0",
                    },
                )
                
                if not response.is_success:
                    logger.warning(
                        "alert_webhook_failed",
                        alert_id=alert.id,
                        status=response.status_code,
                    )
        except Exception as e:
            logger.error(
                "alert_webhook_error",
                alert_id=alert.id,
                error=str(e),
            )
            raise
    
    async def _notify_file(self, alert: Alert) -> None:
        """写入告警文件"""
        try:
            with open(self.alert_file_path, "a", encoding="utf-8") as f:
                line = json.dumps(alert.to_dict(), ensure_ascii=False)
                f.write(line + "\n")
        except Exception as e:
            logger.error(
                "alert_file_write_failed",
                alert_id=alert.id,
                error=str(e),
            )
            raise
    
    def _save_alert(self, alert: Alert) -> None:
        """保存告警到历史"""
        self._alerts.append(alert)
        self._active_alerts[alert.id] = alert
        
        # 限制历史大小
        if len(self._alerts) > self.max_history:
            self._alerts = self._alerts[-self.max_history:]
    
    def resolve(
        self,
        alert_id: str,
        resolved_by: str = "system",
    ) -> Optional[Alert]:
        """
        解决告警
        
        Args:
            alert_id: 告警 ID
            resolved_by: 解决者
        
        Returns:
            解决的告警（如果找到）
        """
        alert = self._active_alerts.pop(alert_id, None)
        if alert:
            alert.resolved = True
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = resolved_by
            
            logger.info(
                "alert_resolved",
                alert_id=alert_id,
                resolved_by=resolved_by,
            )
        
        return alert
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = list(self._active_alerts.values())
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts
    
    def get_history(
        self,
        level: Optional[AlertLevel] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """获取告警历史"""
        alerts = self._alerts[:]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # 按时间倒序
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return alerts[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取通知器统计"""
        total = len(self._alerts)
        active = len(self._active_alerts)
        
        by_level = {}
        for level in AlertLevel:
            by_level[level.value] = len([a for a in self._alerts if a.level == level])
        
        return {
            "total_alerts": total,
            "active_alerts": active,
            "resolved_alerts": total - active,
            "by_level": by_level,
            "webhook_configured": self.webhook_url is not None,
        }


# 全局单例
_alert_notifier: Optional[AlertNotifier] = None


def get_alert_notifier() -> AlertNotifier:
    """获取告警通知器单例"""
    global _alert_notifier
    if _alert_notifier is None:
        _alert_notifier = AlertNotifier()
    return _alert_notifier


def setup_alert_system(
    webhook_url: Optional[str] = None,
    check_interval: float = 60.0,
) -> None:
    """
    设置告警系统
    
    连接检查器和通知器
    """
    from .checker import get_alert_checker
    
    notifier = get_alert_notifier()
    if webhook_url:
        notifier.webhook_url = webhook_url
    
    checker = get_alert_checker()
    checker.check_interval = check_interval
    
    # 注册告警回调
    async def on_alert(rule: AlertRule, metrics: Dict[str, float]):
        await notifier.notify(rule, metrics)
    
    # 同步包装
    def sync_callback(rule: AlertRule, metrics: Dict[str, float]):
        asyncio.create_task(on_alert(rule, metrics))
    
    checker.on_alert(sync_callback)
    
    logger.info(
        "alert_system_configured",
        webhook=webhook_url is not None,
        interval=check_interval,
    )
