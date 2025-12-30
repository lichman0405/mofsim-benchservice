"""
Prometheus 指标测试
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.metrics import (
    increment_request,
    increment_task,
    increment_alert,
    _metrics_state,
)


client = TestClient(app)


class TestMetricsEndpoint:
    """/metrics 端点测试"""

    def test_metrics_endpoint_exists(self):
        """测试指标端点存在"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_metrics_format(self):
        """测试指标格式符合 Prometheus 规范"""
        response = client.get("/metrics")
        content = response.text
        
        # 应包含 HELP 和 TYPE 注释
        assert "# HELP" in content
        assert "# TYPE" in content
        
        # 应包含应用信息指标
        assert "mofsimbench_info" in content
        assert "mofsimbench_uptime_seconds" in content

    def test_metrics_contains_app_info(self):
        """测试包含应用信息"""
        response = client.get("/metrics")
        content = response.text
        
        # 版本和环境应该在标签中
        assert 'version="' in content
        assert 'environment="' in content

    def test_metrics_contains_http_metrics(self):
        """测试包含 HTTP 请求指标"""
        response = client.get("/metrics")
        content = response.text
        
        assert "mofsimbench_http_requests_total" in content

    def test_metrics_contains_task_metrics(self):
        """测试包含任务指标"""
        response = client.get("/metrics")
        content = response.text
        
        assert "mofsimbench_tasks_submitted_total" in content
        assert "mofsimbench_tasks_completed_total" in content
        assert "mofsimbench_tasks_failed_total" in content


class TestMetricsHelpers:
    """指标辅助函数测试"""

    def test_increment_request(self):
        """测试请求计数器"""
        initial = _metrics_state["requests_total"]
        
        increment_request(200, "/api/v1/tasks", 0.05)
        
        assert _metrics_state["requests_total"] == initial + 1
        assert "200" in _metrics_state["requests_by_status"]

    def test_increment_task_submitted(self):
        """测试任务提交计数器"""
        initial = _metrics_state["tasks_submitted_total"]
        
        increment_task("optimization", "submitted")
        
        assert _metrics_state["tasks_submitted_total"] == initial + 1

    def test_increment_task_completed(self):
        """测试任务完成计数器"""
        initial = _metrics_state["tasks_completed_total"]
        
        increment_task("stability", "completed")
        
        assert _metrics_state["tasks_completed_total"] == initial + 1

    def test_increment_task_failed(self):
        """测试任务失败计数器"""
        initial = _metrics_state["tasks_failed_total"]
        
        increment_task("bulk_modulus", "failed")
        
        assert _metrics_state["tasks_failed_total"] == initial + 1

    def test_increment_alert_triggered(self):
        """测试告警触发计数器"""
        initial = _metrics_state["alerts_triggered_total"]
        
        increment_alert(resolved=False)
        
        assert _metrics_state["alerts_triggered_total"] == initial + 1

    def test_increment_alert_resolved(self):
        """测试告警解决计数器"""
        initial = _metrics_state["alerts_resolved_total"]
        
        increment_alert(resolved=True)
        
        assert _metrics_state["alerts_resolved_total"] == initial + 1


class TestHealthCheckEnhanced:
    """增强健康检查测试"""

    def test_health_check_root(self):
        """测试根健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_health_check_api(self):
        """测试 API 健康检查"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "status" in data["data"]
        assert "version" in data["data"]
        assert "uptime_seconds" in data["data"]
        assert "components" in data["data"]

    def test_health_check_components(self):
        """测试健康检查包含组件状态"""
        response = client.get("/api/v1/health")
        data = response.json()
        
        components = data["data"]["components"]
        
        # 应包含 GPU 和队列状态
        assert "gpu" in components
        assert "queue" in components
        
        # GPU 组件应有状态
        assert "status" in components["gpu"]
