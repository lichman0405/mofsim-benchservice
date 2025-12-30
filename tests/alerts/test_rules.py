"""
告警规则引擎测试
"""
import pytest

from alerts.rules import (
    AlertRuleEngine,
    AlertRule,
    AlertCondition,
    AlertLevel,
    AlertType,
    BUILTIN_RULES,
    get_rule_engine,
)


class TestAlertLevel:
    """AlertLevel 测试"""

    def test_level_values(self):
        """测试告警级别值"""
        assert AlertLevel.CRITICAL.value == "CRITICAL"
        assert AlertLevel.WARNING.value == "WARNING"
        assert AlertLevel.INFO.value == "INFO"

    def test_level_severity(self):
        """测试级别严重程度排序"""
        severity = [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.CRITICAL]
        # CRITICAL 应该最严重
        assert severity.index(AlertLevel.CRITICAL) > severity.index(AlertLevel.WARNING)
        assert severity.index(AlertLevel.WARNING) > severity.index(AlertLevel.INFO)


class TestAlertType:
    """AlertType 测试"""

    def test_builtin_types(self):
        """测试内置告警类型"""
        expected_types = [
            "gpu_unavailable",
            "gpu_memory_low",
            "gpu_temp_high",
            "queue_backlog",
            "task_failures",
            "disk_space_low",
            "worker_offline",
        ]
        for type_name in expected_types:
            assert hasattr(AlertType, type_name.upper())


class TestAlertCondition:
    """AlertCondition 测试"""

    def test_less_than_operator(self):
        """测试小于运算符"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        assert condition.evaluate(0) is True
        assert condition.evaluate(1) is False
        assert condition.evaluate(2) is False

    def test_greater_than_operator(self):
        """测试大于运算符"""
        condition = AlertCondition(
            metric="max_gpu_temp",
            operator=">",
            threshold=85,
        )
        assert condition.evaluate(90) is True
        assert condition.evaluate(85) is False
        assert condition.evaluate(80) is False

    def test_less_equal_operator(self):
        """测试小于等于运算符"""
        condition = AlertCondition(
            metric="disk_free_gb",
            operator="<=",
            threshold=50,
        )
        assert condition.evaluate(30) is True
        assert condition.evaluate(50) is True
        assert condition.evaluate(60) is False

    def test_greater_equal_operator(self):
        """测试大于等于运算符"""
        condition = AlertCondition(
            metric="queue_length",
            operator=">=",
            threshold=100,
        )
        assert condition.evaluate(150) is True
        assert condition.evaluate(100) is True
        assert condition.evaluate(50) is False

    def test_equal_operator(self):
        """测试等于运算符"""
        condition = AlertCondition(
            metric="active_workers",
            operator="==",
            threshold=0,
        )
        assert condition.evaluate(0) is True
        assert condition.evaluate(1) is False

    def test_not_equal_operator(self):
        """测试不等于运算符"""
        condition = AlertCondition(
            metric="status",
            operator="!=",
            threshold=1,
        )
        assert condition.evaluate(0) is True
        assert condition.evaluate(1) is False

    def test_condition_to_dict(self):
        """测试条件转字典"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        data = condition.to_dict()
        
        assert data["metric"] == "available_gpus"
        assert data["operator"] == "<"
        assert data["threshold"] == 1


class TestAlertRule:
    """AlertRule 测试"""

    def test_rule_creation(self):
        """测试规则创建"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        rule = AlertRule(
            id="test_rule",
            name="Test Rule",
            description="A test rule",
            alert_type=AlertType.GPU_UNAVAILABLE,
            level=AlertLevel.CRITICAL,
            condition=condition,
            cooldown_seconds=60,
            enabled=True,
        )
        
        assert rule.id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.level == AlertLevel.CRITICAL
        assert rule.enabled is True

    def test_rule_can_trigger(self):
        """测试规则触发条件"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        rule = AlertRule(
            id="gpu_check",
            name="GPU Check",
            description="Check GPU availability",
            alert_type=AlertType.GPU_UNAVAILABLE,
            level=AlertLevel.CRITICAL,
            condition=condition,
        )
        
        # 首次可以触发
        assert rule.can_trigger() is True

    def test_disabled_rule_cannot_trigger(self):
        """测试禁用规则不能触发"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        rule = AlertRule(
            id="gpu_check",
            name="GPU Check",
            description="Check GPU availability",
            alert_type=AlertType.GPU_UNAVAILABLE,
            level=AlertLevel.CRITICAL,
            condition=condition,
            enabled=False,
        )
        
        assert rule.can_trigger() is False

    def test_rule_to_dict(self):
        """测试规则转字典"""
        condition = AlertCondition(
            metric="available_gpus",
            operator="<",
            threshold=1,
        )
        rule = AlertRule(
            id="test_rule",
            name="Test Rule",
            description="A test rule",
            alert_type=AlertType.GPU_UNAVAILABLE,
            level=AlertLevel.CRITICAL,
            condition=condition,
        )
        
        data = rule.to_dict()
        
        assert data["id"] == "test_rule"
        assert data["name"] == "Test Rule"
        assert data["level"] == "CRITICAL"
        assert data["alert_type"] == "gpu_unavailable"
        assert "condition" in data


class TestAlertRuleEngine:
    """AlertRuleEngine 测试"""

    def test_builtin_rules_loaded(self):
        """测试内置规则加载"""
        engine = AlertRuleEngine()
        rules = engine.list_rules()
        
        assert len(rules) == len(BUILTIN_RULES)
        
        rule_names = [r.name for r in rules]
        assert "GPU 不可用" in rule_names

    def test_add_custom_rule(self):
        """测试添加自定义规则"""
        engine = AlertRuleEngine()
        initial_count = len(engine.list_rules())
        
        condition = AlertCondition(
            metric="custom_metric",
            operator=">",
            threshold=100,
        )
        rule = AlertRule(
            id="custom_rule",
            name="Custom Rule",
            description="A custom rule",
            alert_type=AlertType.CUSTOM,
            level=AlertLevel.INFO,
            condition=condition,
        )
        
        engine.add_rule(rule)
        assert len(engine.list_rules()) == initial_count + 1

    def test_get_rule(self):
        """测试获取规则"""
        engine = AlertRuleEngine()
        rules = engine.list_rules()
        
        if rules:
            rule = engine.get_rule(rules[0].id)
            assert rule is not None
            assert rule.id == rules[0].id

    def test_get_rule_not_found(self):
        """测试获取不存在的规则"""
        engine = AlertRuleEngine()
        rule = engine.get_rule("nonexistent-id")
        assert rule is None

    def test_enable_disable_rule(self):
        """测试启用禁用规则"""
        engine = AlertRuleEngine()
        rules = engine.list_rules()
        
        if rules:
            rule_id = rules[0].id
            
            # 禁用
            engine.disable_rule(rule_id)
            rule = engine.get_rule(rule_id)
            assert rule.enabled is False
            
            # 启用
            engine.enable_rule(rule_id)
            rule = engine.get_rule(rule_id)
            assert rule.enabled is True

    def test_remove_rule(self):
        """测试移除规则"""
        engine = AlertRuleEngine()
        
        # 添加自定义规则
        condition = AlertCondition(
            metric="test",
            operator="<",
            threshold=1,
        )
        rule = AlertRule(
            id="to_remove",
            name="To Remove",
            description="A rule to remove",
            alert_type=AlertType.CUSTOM,
            level=AlertLevel.INFO,
            condition=condition,
        )
        engine.add_rule(rule)
        
        rule_id = rule.id
        assert engine.get_rule(rule_id) is not None
        
        # 移除
        success = engine.remove_rule(rule_id)
        assert success is True
        assert engine.get_rule(rule_id) is None

    def test_evaluate(self):
        """测试评估所有规则"""
        engine = AlertRuleEngine()
        
        # 提供会触发告警的指标
        metrics = {
            "available_gpus": 0,  # 触发 gpu_unavailable
            "min_gpu_free_memory_gb": 1.0,  # 触发 gpu_memory_low
            "queue_length": 50,  # 不触发
            "disk_free_gb": 100,  # 不触发
            "active_workers": 2,  # 不触发
        }
        
        triggered_rules = engine.evaluate(metrics)
        
        # 应该有一些规则被触发
        assert len(triggered_rules) >= 1
        
        # 检查是否触发了正确的规则
        rule_ids = [r.id for r in triggered_rules]
        assert "gpu_unavailable" in rule_ids


class TestGetRuleEngine:
    """get_rule_engine 单例测试"""

    def test_singleton(self):
        """测试单例模式"""
        engine1 = get_rule_engine()
        engine2 = get_rule_engine()
        assert engine1 is engine2
