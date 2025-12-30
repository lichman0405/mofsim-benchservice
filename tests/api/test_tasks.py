"""
任务 API 测试

使用 pytest 运行:
    pytest tests/api/test_tasks.py -v
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestHealthCheck:
    """健康检查测试"""
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "version" in data["data"]


class TestTaskSubmission:
    """任务提交测试"""
    
    def test_submit_optimization_returns_501(self, client):
        """测试优化任务提交（占位符返回 501）"""
        response = client.post(
            "/api/v1/tasks/optimization",
            json={
                "model": "mace_prod",
                "structure": {"source": "builtin", "name": "HKUST-1"},
                "parameters": {"fmax": 0.05},
            }
        )
        # 当前为占位符实现，应返回 501
        assert response.status_code == 501
    
    def test_submit_stability_returns_501(self, client):
        """测试稳定性任务提交"""
        response = client.post(
            "/api/v1/tasks/stability",
            json={
                "model": "orb_v2",
                "structure": {"source": "builtin", "name": "MOF-5"},
                "parameters": {"temperature": 300},
            }
        )
        assert response.status_code == 501


class TestTaskList:
    """任务列表测试"""
    
    def test_list_tasks_returns_501(self, client):
        """测试任务列表（占位符）"""
        response = client.get("/api/v1/tasks")
        assert response.status_code == 501


class TestModels:
    """模型 API 测试"""
    
    def test_list_models_returns_501(self, client):
        """测试模型列表（占位符）"""
        response = client.get("/api/v1/models")
        assert response.status_code == 501


class TestStructures:
    """结构 API 测试"""
    
    def test_list_structures_returns_501(self, client):
        """测试结构列表（占位符）"""
        response = client.get("/api/v1/structures")
        assert response.status_code == 501


class TestSystem:
    """系统 API 测试"""
    
    def test_gpu_status_returns_501(self, client):
        """测试 GPU 状态（占位符）"""
        response = client.get("/api/v1/system/gpus")
        assert response.status_code == 501
