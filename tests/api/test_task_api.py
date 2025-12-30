"""
任务 API 测试
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient


# Mock 模块在导入前
@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    return MagicMock()


@pytest.fixture
def mock_priority_queue():
    """Mock 优先级队列"""
    from core.scheduler.priority_queue import MockPriorityQueue
    return MockPriorityQueue()


@pytest.fixture
def mock_gpu_manager():
    """Mock GPU 管理器"""
    from core.scheduler import GPUManager
    return GPUManager(gpu_ids=[0, 1], mock_mode=True)


@pytest.fixture
def test_client(mock_db_session, mock_priority_queue, mock_gpu_manager):
    """测试客户端"""
    from api.dependencies import get_db, get_priority_queue, get_gpu_manager
    from api.main import app
    
    # 覆盖依赖
    def override_get_db():
        return mock_db_session
    
    def override_get_queue():
        return mock_priority_queue
    
    def override_gpu_manager():
        return mock_gpu_manager
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_priority_queue] = override_get_queue
    app.dependency_overrides[get_gpu_manager] = override_gpu_manager
    
    client = TestClient(app)
    
    yield client
    
    # 清理
    app.dependency_overrides.clear()


class TestSubmitTask:
    """提交任务测试"""
    
    def test_submit_optimization_task_success(self, test_client, mock_db_session):
        """测试成功提交优化任务"""
        # 准备 mock 任务返回
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.task_type.value = "optimization"
        mock_task.status.value = "QUEUED"
        mock_task.model_name = "mace-mp-0-medium"
        mock_task.priority.value = "NORMAL"
        mock_task.created_at = datetime.now()
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.gpu_id = None
        mock_task.error_message = None
        
        # Mock TaskCRUD.create
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.create.return_value = mock_task
            mock_crud.update_status.return_value = mock_task
            
            response = test_client.post(
                "/api/v1/tasks/optimization",
                json={
                    "model": "mace-mp-0-medium",
                    "structure": {
                        "source": "builtin",
                        "name": "HKUST-1"
                    },
                    "parameters": {
                        "fmax": 0.01,
                        "steps": 500
                    },
                    "options": {
                        "priority": "NORMAL",
                        "timeout": 3600
                    }
                }
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert data["code"] == 202
        assert data["message"] == "任务已提交"
        assert "task_id" in data["data"]
    
    def test_submit_task_invalid_model(self, test_client, mock_db_session):
        """测试提交无效模型"""
        response = test_client.post(
            "/api/v1/tasks/optimization",
            json={
                "model": "invalid-model",
                "structure": {
                    "source": "builtin",
                    "name": "HKUST-1"
                }
            }
        )
        
        # 应该返回 404 (模型不存在)
        assert response.status_code in (404, 422, 500)
    
    def test_submit_stability_task(self, test_client, mock_db_session):
        """测试提交稳定性任务"""
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.task_type.value = "stability"
        mock_task.status.value = "QUEUED"
        mock_task.model_name = "mace-mp-0-medium"
        mock_task.priority.value = "NORMAL"
        mock_task.created_at = datetime.now()
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.gpu_id = None
        mock_task.error_message = None
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.create.return_value = mock_task
            mock_crud.update_status.return_value = mock_task
            
            response = test_client.post(
                "/api/v1/tasks/stability",
                json={
                    "model": "mace-mp-0-medium",
                    "structure": {
                        "source": "builtin",
                        "name": "MOF-5"
                    },
                    "parameters": {
                        "temperature": 300,
                        "nvt_steps": 10000,
                        "npt_steps": 10000
                    }
                }
            )
        
        assert response.status_code == 202


class TestGetTask:
    """获取任务测试"""
    
    def test_get_task_success(self, test_client, mock_db_session):
        """测试成功获取任务"""
        task_id = uuid4()
        
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.task_type.value = "optimization"
        mock_task.status.value = "COMPLETED"
        mock_task.model_name = "mace-mp-0-medium"
        mock_task.priority.value = "NORMAL"
        mock_task.created_at = datetime.now()
        mock_task.started_at = datetime.now()
        mock_task.completed_at = datetime.now()
        mock_task.gpu_id = 0
        mock_task.error_message = None
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_by_id.return_value = mock_task
            
            response = test_client.get(f"/api/v1/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == str(task_id)
    
    def test_get_task_not_found(self, test_client, mock_db_session):
        """测试获取不存在的任务"""
        task_id = uuid4()
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_by_id.return_value = None
            
            response = test_client.get(f"/api/v1/tasks/{task_id}")
        
        assert response.status_code in (404, 500)


class TestListTasks:
    """任务列表测试"""
    
    def test_list_tasks_success(self, test_client, mock_db_session):
        """测试获取任务列表"""
        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task.task_type.value = "optimization"
        mock_task.status.value = "COMPLETED"
        mock_task.model_name = "mace-mp-0-medium"
        mock_task.priority.value = "NORMAL"
        mock_task.created_at = datetime.now()
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.gpu_id = None
        mock_task.error_message = None
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_list.return_value = ([mock_task], 1)
            
            response = test_client.get("/api/v1/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["pagination"]["total_items"] == 1
    
    def test_list_tasks_with_filters(self, test_client, mock_db_session):
        """测试带过滤条件的任务列表"""
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_list.return_value = ([], 0)
            
            response = test_client.get(
                "/api/v1/tasks",
                params={
                    "status": "COMPLETED",
                    "task_type": "optimization",
                    "model": "mace-mp-0-medium",
                    "page": 1,
                    "page_size": 10
                }
            )
        
        assert response.status_code == 200


class TestCancelTask:
    """取消任务测试"""
    
    def test_cancel_task_success(self, test_client, mock_db_session):
        """测试成功取消任务"""
        from db.models import TaskStatus
        
        task_id = uuid4()
        
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.status = TaskStatus.QUEUED
        mock_task.celery_task_id = None
        
        mock_cancelled = MagicMock()
        mock_cancelled.id = task_id
        mock_cancelled.status = TaskStatus.CANCELLED
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_by_id.return_value = mock_task
            mock_crud.cancel.return_value = mock_cancelled
            
            response = test_client.post(f"/api/v1/tasks/{task_id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestGetTaskResult:
    """获取任务结果测试"""
    
    def test_get_result_completed(self, test_client, mock_db_session):
        """测试获取已完成任务结果"""
        from db.models import TaskStatus as DBTaskStatus, TaskType as DBTaskType
        
        task_id = uuid4()
        
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.task_type = DBTaskType.OPTIMIZATION
        mock_task.status = DBTaskStatus.COMPLETED
        mock_task.model_name = "mace-mp-0-medium"
        mock_task.structure_name = "HKUST-1"
        mock_task.created_at = datetime.now()
        mock_task.started_at = datetime.now()
        mock_task.completed_at = datetime.now()
        mock_task.result = {
            "converged": True,
            "final_energy_eV": -100.5
        }
        mock_task.output_files = {
            "optimized_structure": "/path/to/output.cif"
        }
        mock_task.duration_seconds = 120.5
        mock_task.peak_memory_mb = 2048
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_by_id.return_value = mock_task
            
            response = test_client.get(f"/api/v1/tasks/{task_id}/result")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["result"]["converged"] is True
    
    def test_get_result_not_finished(self, test_client, mock_db_session):
        """测试获取未完成任务结果应该报错"""
        from db.models import TaskStatus as DBTaskStatus, TaskType as DBTaskType
        
        task_id = uuid4()
        
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.task_type = DBTaskType.OPTIMIZATION
        mock_task.status = DBTaskStatus.RUNNING
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.get_by_id.return_value = mock_task
            
            response = test_client.get(f"/api/v1/tasks/{task_id}/result")
        
        # 应该返回 400 (任务未完成)
        assert response.status_code == 400


class TestBatchSubmit:
    """批量提交测试"""
    
    def test_batch_submit_success(self, test_client, mock_db_session):
        """测试批量提交任务"""
        mock_task1 = MagicMock()
        mock_task1.id = uuid4()
        mock_task1.task_type.value = "optimization"
        mock_task1.status.value = "QUEUED"
        mock_task1.model_name = "mace-mp-0-medium"
        mock_task1.priority.value = "NORMAL"
        mock_task1.created_at = datetime.now()
        mock_task1.started_at = None
        mock_task1.completed_at = None
        
        mock_task2 = MagicMock()
        mock_task2.id = uuid4()
        mock_task2.task_type.value = "optimization"
        mock_task2.status.value = "QUEUED"
        mock_task2.model_name = "mace-mp-0-medium"
        mock_task2.priority.value = "NORMAL"
        mock_task2.created_at = datetime.now()
        mock_task2.started_at = None
        mock_task2.completed_at = None
        
        with patch("core.services.task_service.TaskCRUD") as mock_crud:
            mock_crud.create.side_effect = [mock_task1, mock_task2]
            mock_crud.update_status.side_effect = [mock_task1, mock_task2]
            
            response = test_client.post(
                "/api/v1/tasks/batch",
                params={"task_type": "optimization"},
                json={
                    "tasks": [
                        {
                            "model": "mace-mp-0-medium",
                            "structure": {"source": "builtin", "name": "HKUST-1"}
                        },
                        {
                            "model": "mace-mp-0-medium",
                            "structure": {"source": "builtin", "name": "MOF-5"}
                        }
                    ]
                }
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert data["data"]["submitted"] == 2
        assert data["data"]["failed"] == 0
