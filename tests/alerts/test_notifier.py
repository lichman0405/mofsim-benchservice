"""
告警通知器测试
"""
import pytest
from datetime import datetime
import tempfile
import os

from alerts.notifier import Alert, AlertNotifier, get_alert_notifier
from alerts.rules import AlertLevel, AlertType, AlertRule, AlertCondition


class TestAlert:
    """Alert 模型测试"""

    def test_alert_creation(self):
        """测试告警创建"""
        alert = Alert(
            id="alert_test123",
            rule_id="gpu_unavailable",
            alert_type="gpu_unavailable",
            level=AlertLevel.WARNING,
            message="GPU memory is low",
            details={"gpu_id": 0, "free_memory_gb": 1.5},
            created_at=datetime.utcnow(),
        )
        
        assert alert.id == "alert_test123"
        assert alert.level == AlertLevel.WARNING
        assert alert.alert_type == "gpu_unavailable"
        assert alert.message == "GPU memory is low"
        assert alert.resolved is False
        assert alert.resolved_at is None

    def test_alert_to_dict(self):
        """测试告警转字典"""
        alert = Alert(
            id="alert_test456",
            rule_id="test_rule",
            alert_type="custom",
            level=AlertLevel.INFO,
            message="Test alert",
            details={"key": "value"},
            created_at=datetime.utcnow(),
        )
        
        data = alert.to_dict()
        
        assert data["id"] == "alert_test456"
        assert data["level"] == "INFO"
        assert data["alert_type"] == "custom"
        assert data["message"] == "Test alert"
        assert data["details"] == {"key": "value"}
        assert data["resolved"] is False
        assert "created_at" in data


class TestAlertNotifier:
    """AlertNotifier 测试"""

    def test_notifier_creation(self):
        """测试通知器创建"""
        notifier = AlertNotifier()
        assert notifier is not None

    def test_notifier_with_config(self):
        """测试自定义通知器配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            notifier = AlertNotifier(
                webhook_url="https://example.com/webhook",
                alert_file_path=alert_file,
                max_history=500,
            )
            
            assert notifier.webhook_url == "https://example.com/webhook"
            assert notifier.max_history == 500

    @pytest.mark.asyncio
    async def test_notify(self):
        """测试发送通知"""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            notifier = AlertNotifier(alert_file_path=alert_file)
            
            # 创建规则
            condition = AlertCondition(
                metric="queue_length",
                operator=">",
                threshold=100,
            )
            rule = AlertRule(
                id="queue_backlog",
                name="Queue Backlog",
                description="Queue is too long",
                alert_type=AlertType.QUEUE_BACKLOG,
                level=AlertLevel.WARNING,
                condition=condition,
                notification_channels=["log"],  # 只用日志，避免 HTTP
            )
            
            metrics = {"queue_length": 150}
            
            alert = await notifier.notify(rule, metrics)
            
            # 检查告警
            assert alert is not None
            assert alert.rule_id == "queue_backlog"
            assert alert.level == AlertLevel.WARNING
            assert "log" in alert.notified_channels

    def test_get_active_alerts_empty(self):
        """测试获取空的活跃告警"""
        notifier = AlertNotifier()
        active = notifier.get_active_alerts()
        assert active == []

    @pytest.mark.asyncio
    async def test_resolve_alert(self):
        """测试解决告警"""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            notifier = AlertNotifier(alert_file_path=alert_file)
            
            # 创建规则
            condition = AlertCondition(
                metric="disk_free_gb",
                operator="<",
                threshold=50,
            )
            rule = AlertRule(
                id="disk_space_low",
                name="Disk Space Low",
                description="Disk space is low",
                alert_type=AlertType.DISK_SPACE_LOW,
                level=AlertLevel.WARNING,
                condition=condition,
                notification_channels=["log"],
            )
            
            metrics = {"disk_free_gb": 30}
            
            # 发送告警
            alert = await notifier.notify(rule, metrics)
            assert alert is not None
            
            # 解决告警
            resolved = notifier.resolve(alert.id, resolved_by="admin")
            assert resolved is not None
            assert resolved.resolved is True
            assert resolved.resolved_at is not None
            assert resolved.resolved_by == "admin"

    def test_resolve_nonexistent_alert(self):
        """测试解决不存在的告警"""
        notifier = AlertNotifier()
        
        resolved = notifier.resolve("nonexistent_id")
        assert resolved is None

    def test_get_stats(self):
        """测试获取统计信息"""
        notifier = AlertNotifier()
        
        stats = notifier.get_stats()
        
        assert "total_alerts" in stats
        assert "active_alerts" in stats
        assert "resolved_alerts" in stats
        assert "by_level" in stats

    @pytest.mark.asyncio
    async def test_get_history(self):
        """测试获取告警历史"""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            notifier = AlertNotifier(alert_file_path=alert_file)
            
            # 创建规则
            condition = AlertCondition(
                metric="available_gpus",
                operator="<",
                threshold=1,
            )
            rule = AlertRule(
                id="gpu_unavailable",
                name="GPU Unavailable",
                description="No GPU available",
                alert_type=AlertType.GPU_UNAVAILABLE,
                level=AlertLevel.CRITICAL,
                condition=condition,
                notification_channels=["log"],
                cooldown_seconds=0,  # 禁用冷却
            )
            
            # 发送多个告警
            for i in range(3):
                rule.last_triggered = None  # 重置冷却
                await notifier.notify(rule, {"available_gpus": 0})
            
            # 获取历史
            history = notifier.get_history()
            assert len(history) >= 3


class TestGetAlertNotifier:
    """get_alert_notifier 单例测试"""

    def test_singleton(self):
        """测试单例模式"""
        notifier1 = get_alert_notifier()
        notifier2 = get_alert_notifier()
        assert notifier1 is notifier2
