"""
API 路由器测试

测试核心 API 路由功能。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


# ===== Models API 测试 =====

class TestModelsAPI:
    """模型 API 测试"""
    
    def test_list_models(self):
        """列出模型"""
        response = client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "models" in data["data"]
        assert len(data["data"]["models"]) > 0
    
    def test_list_models_with_family(self):
        """按系列过滤模型"""
        response = client.get("/api/v1/models?family=mace")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_nonexistent_model(self):
        """模型不存在"""
        response = client.get("/api/v1/models/nonexistent_model_xyz_123")
        assert response.status_code == 404


# ===== Structures API 测试 =====

class TestStructuresAPI:
    """结构 API 测试"""
    
    def test_list_structures(self):
        """列出结构"""
        response = client.get("/api/v1/structures")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_list_builtin_structures(self):
        """列出内置结构"""
        response = client.get("/api/v1/structures/builtin")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ===== System API 测试 =====

class TestSystemAPI:
    """系统 API 测试"""
    
    def test_get_gpus(self):
        """获取 GPU 状态"""
        response = client.get("/api/v1/system/gpus")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "gpus" in data["data"]
    
    def test_get_queue(self):
        """获取队列状态"""
        response = client.get("/api/v1/system/queue")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ===== Health API 测试 =====

class TestHealthAPI:
    """健康检查 API 测试"""
    
    def test_health_check(self):
        """基本健康检查"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        # 检查响应结构
        assert "code" in data or "success" in data
    
    def test_liveness(self):
        """存活检查"""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200


# ===== Metrics API 测试 =====

class TestMetricsAPI:
    """指标 API 测试"""
    
    def test_metrics_summary(self):
        """指标摘要"""
        response = client.get("/api/v1/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_task_metrics(self):
        """任务指标"""
        response = client.get("/api/v1/metrics/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
