"""
任务 API 测试 (旧占位符测试)

此测试文件中的 501 测试已被 test_task_api.py 取代。
保留健康检查等通用测试。

使用 pytest 运行:
    pytest tests/api/test_tasks.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    # 覆盖依赖以避免外部依赖
    from api.dependencies import get_db, get_priority_queue, get_gpu_manager
    from core.scheduler import GPUManager
    from core.scheduler.priority_queue import MockPriorityQueue
    
    def override_get_db():
        return MagicMock()
    
    def override_get_queue():
        return MockPriorityQueue()
    
    def override_gpu_manager():
        return GPUManager(gpu_ids=[0, 1], mock_mode=True)
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_priority_queue] = override_get_queue
    app.dependency_overrides[get_gpu_manager] = override_gpu_manager
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestHealthCheck:
    """健康检查测试"""
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "version" in data["data"]


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
    
    def test_gpu_status(self, client):
        """测试 GPU 状态"""
        response = client.get("/api/v1/system/gpus")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "gpus" in data["data"]
