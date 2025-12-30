"""
告警规则引擎

参考文档: docs/engineering_requirements.md 7.2 节
定义内置告警规则和自定义规则支持
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import structlog

logger = structlog.get_logger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertType(str, Enum):
    """告警类型"""
    GPU_UNAVAILABLE = "gpu_unavailable"
    GPU_MEMORY_LOW = "gpu_memory_low"
    GPU_TEMP_HIGH = "gpu_temp_high"
    QUEUE_BACKLOG = "queue_backlog"
    TASK_FAILURES = "task_failures"
    DISK_SPACE_LOW = "disk_space_low"
    WORKER_OFFLINE = "worker_offline"
    API_SLOW = "api_slow"
    CUSTOM = "custom"


@dataclass
class AlertCondition:
    """告警条件"""
    metric: str  # 指标名称
    operator: str  # 比较运算符: >, <, >=, <=, ==, !=
    threshold: float  # 阈值
    
    def evaluate(self, value: float) -> bool:
        """评估条件"""
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return value == self.threshold
        elif self.operator == "!=":
            return value != self.threshold
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
        }


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    description: str
    alert_type: AlertType
    level: AlertLevel
    condition: AlertCondition
    enabled: bool = True
    cooldown_seconds: int = 300  # 冷却时间，避免重复告警
    notification_channels: List[str] = field(default_factory=lambda: ["log", "webhook"])
    
    # 运行时状态
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def can_trigger(self) -> bool:
        """检查是否可以触发（考虑冷却时间）"""
        if not self.enabled:
            return False
        
        if self.last_triggered is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_triggered).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "condition": self.condition.to_dict(),
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "notification_channels": self.notification_channels,
            "last_triggered": self.last_triggered.isoformat() + "Z" if self.last_triggered else None,
            "trigger_count": self.trigger_count,
        }


# 内置告警规则
BUILTIN_RULES: List[AlertRule] = [
    AlertRule(
        id="gpu_unavailable",
        name="GPU 不可用",
        description="GPU 设备丢失或驱动错误",
        alert_type=AlertType.GPU_UNAVAILABLE,
        level=AlertLevel.CRITICAL,
        condition=AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        ),
        cooldown_seconds=60,
    ),
    AlertRule(
        id="gpu_memory_low",
        name="GPU 显存不足",
        description="GPU 可用显存低于 2GB",
        alert_type=AlertType.GPU_MEMORY_LOW,
        level=AlertLevel.WARNING,
        condition=AlertCondition(
            metric="min_gpu_free_memory_gb",
            operator="<",
            threshold=2.0,
        ),
        cooldown_seconds=300,
    ),
    AlertRule(
        id="gpu_temp_high",
        name="GPU 温度过高",
        description="GPU 温度超过 85°C",
        alert_type=AlertType.GPU_TEMP_HIGH,
        level=AlertLevel.WARNING,
        condition=AlertCondition(
            metric="max_gpu_temp",
            operator=">",
            threshold=85,
        ),
        cooldown_seconds=300,
    ),
    AlertRule(
        id="queue_backlog",
        name="任务队列积压",
        description="等待中的任务超过 100 个",
        alert_type=AlertType.QUEUE_BACKLOG,
        level=AlertLevel.WARNING,
        condition=AlertCondition(
            metric="queue_length",
            operator=">",
            threshold=100,
        ),
        cooldown_seconds=600,
    ),
    AlertRule(
        id="task_failures",
        name="任务连续失败",
        description="最近任务连续失败超过 5 次",
        alert_type=AlertType.TASK_FAILURES,
        level=AlertLevel.WARNING,
        condition=AlertCondition(
            metric="consecutive_failures",
            operator=">",
            threshold=5,
        ),
        cooldown_seconds=300,
    ),
    AlertRule(
        id="disk_space_low",
        name="磁盘空间不足",
        description="可用磁盘空间低于 50GB",
        alert_type=AlertType.DISK_SPACE_LOW,
        level=AlertLevel.WARNING,
        condition=AlertCondition(
            metric="disk_free_gb",
            operator="<",
            threshold=50,
        ),
        cooldown_seconds=3600,
    ),
    AlertRule(
        id="worker_offline",
        name="Worker 离线",
        description="Celery Worker 心跳丢失",
        alert_type=AlertType.WORKER_OFFLINE,
        level=AlertLevel.CRITICAL,
        condition=AlertCondition(
            metric="active_workers",
            operator="<",
            threshold=1,
        ),
        cooldown_seconds=60,
    ),
]


class AlertRuleEngine:
    """
    告警规则引擎
    
    功能:
    - 管理告警规则（内置 + 自定义）
    - 评估规则条件
    - 触发告警
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._load_builtin_rules()
    
    def _load_builtin_rules(self) -> None:
        """加载内置规则"""
        for rule in BUILTIN_RULES:
            self._rules[rule.id] = rule
        logger.info("alert_rules_loaded", count=len(BUILTIN_RULES))
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取规则"""
        return self._rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """列出所有规则"""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加自定义规则"""
        self._rules[rule.id] = rule
        logger.info("alert_rule_added", rule_id=rule.id, name=rule.name)
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info("alert_rule_removed", rule_id=rule_id)
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            return True
        return False
    
    def evaluate(self, metrics: Dict[str, float]) -> List[AlertRule]:
        """
        评估所有规则
        
        Args:
            metrics: 当前指标值
        
        Returns:
            触发的规则列表
        """
        triggered = []
        
        for rule in self._rules.values():
            if not rule.can_trigger():
                continue
            
            metric_value = metrics.get(rule.condition.metric)
            if metric_value is None:
                continue
            
            if rule.condition.evaluate(metric_value):
                rule.last_triggered = datetime.utcnow()
                rule.trigger_count += 1
                triggered.append(rule)
                
                logger.info(
                    "alert_rule_triggered",
                    rule_id=rule.id,
                    name=rule.name,
                    level=rule.level.value,
                    metric=rule.condition.metric,
                    value=metric_value,
                    threshold=rule.condition.threshold,
                )
        
        return triggered


# 全局单例
_rule_engine: Optional[AlertRuleEngine] = None


def get_rule_engine() -> AlertRuleEngine:
    """获取规则引擎单例"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = AlertRuleEngine()
    return _rule_engine
