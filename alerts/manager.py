"""
告警管理器

参考文档: docs/engineering_requirements.md 第七节
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class AlertManager:
    """
    告警管理器
    
    功能:
    - 规则评估
    - 告警触发
    - 通知发送
    - 告警聚合
    """
    
    def __init__(self):
        self._rules: Dict[str, Dict] = {}
        self._active_alerts: Dict[str, Dict] = {}
    
    def register_rule(self, rule_id: str, rule: Dict[str, Any]) -> None:
        """注册告警规则"""
        self._rules[rule_id] = rule
        logger.info("alert_rule_registered", rule_id=rule_id, rule_name=rule.get("name"))
    
    def evaluate_rules(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        评估所有规则
        
        Args:
            metrics: 当前指标值
                - queue_length: 队列长度
                - gpu_utilization: GPU 利用率
                - error_rate: 错误率
        
        Returns:
            触发的告警列表
        """
        triggered = []
        
        for rule_id, rule in self._rules.items():
            if not rule.get("enabled", True):
                continue
            
            if self._evaluate_condition(rule["condition"], metrics):
                alert = self._create_alert(rule_id, rule, metrics)
                triggered.append(alert)
                self._active_alerts[alert["id"]] = alert
        
        return triggered
    
    def _evaluate_condition(self, condition: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """评估单个条件"""
        metric = condition.get("metric")
        op = condition.get("op")
        value = condition.get("value")
        
        if metric not in metrics:
            return False
        
        current = metrics[metric]
        
        if op == ">":
            return current > value
        elif op == "<":
            return current < value
        elif op == ">=":
            return current >= value
        elif op == "<=":
            return current <= value
        elif op == "==":
            return current == value
        
        return False
    
    def _create_alert(self, rule_id: str, rule: Dict, metrics: Dict) -> Dict[str, Any]:
        """创建告警"""
        import uuid
        
        return {
            "id": str(uuid.uuid4()),
            "rule_id": rule_id,
            "level": rule.get("level", "WARNING"),
            "alert_type": rule.get("type", "threshold"),
            "message": rule.get("message", f"规则 {rule.get('name')} 触发"),
            "details": {
                "condition": rule.get("condition"),
                "metrics": metrics,
            },
            "created_at": datetime.utcnow().isoformat(),
            "resolved": False,
        }
    
    def resolve_alert(self, alert_id: str, resolved_by: Optional[str] = None) -> bool:
        """解决告警"""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id]["resolved"] = True
            self._active_alerts[alert_id]["resolved_at"] = datetime.utcnow().isoformat()
            self._active_alerts[alert_id]["resolved_by"] = resolved_by
            logger.info("alert_resolved", alert_id=alert_id, resolved_by=resolved_by)
            return True
        return False
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        return [a for a in self._active_alerts.values() if not a.get("resolved")]
    
    async def send_notification(self, alert: Dict[str, Any], channels: List[str]) -> None:
        """
        发送告警通知
        
        TODO: Phase 6 实现具体通知渠道
        """
        for channel in channels:
            logger.info(
                "alert_notification_sent",
                alert_id=alert["id"],
                channel=channel,
            )
