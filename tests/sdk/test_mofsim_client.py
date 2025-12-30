"""
SDK 测试模块
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx

from sdk.mofsim_client import (
    MOFSimClient,
    AsyncMOFSimClient,
    Task,
    TaskResult,
    TaskStatus,
    MOFSimError,
    APIError,
    TaskNotFoundError,
    TaskFailedError,
    TaskTimeoutError,
    ValidationError,
    ConnectionError,
)
from sdk.mofsim_client.models import (
    TaskInfo,
    StructureInfo,
    ModelInfo,
    GPUInfo,
    QueueInfo,
    PaginatedResult,
)


# ===== 模型测试 =====

class TestTaskStatus:
    """TaskStatus 枚举测试"""
    
    def test_terminal_states(self):
        """终态判断"""
        assert TaskStatus.COMPLETED.is_terminal()
        assert TaskStatus.FAILED.is_terminal()
        assert TaskStatus.CANCELLED.is_terminal()
        assert TaskStatus.TIMEOUT.is_terminal()
        
        assert not TaskStatus.PENDING.is_terminal()
        assert not TaskStatus.RUNNING.is_terminal()
    
    def test_success_state(self):
        """成功状态"""
        assert TaskStatus.COMPLETED.is_success()
        assert not TaskStatus.FAILED.is_success()


class TestTaskInfo:
    """TaskInfo 模型测试"""
    
    def test_from_dict(self):
        """从字典创建"""
        data = {
            "task_id": "task-123",
            "task_type": "optimization",
            "status": "COMPLETED",
            "model": "mace_mof_large",
            "priority": "HIGH",
            "progress": 100.0,
        }
        
        info = TaskInfo.from_dict(data)
        
        assert info.task_id == "task-123"
        assert info.task_type == "optimization"
        assert info.status == "COMPLETED"
        assert info.model == "mace_mof_large"
        assert info.priority == "HIGH"
        assert info.progress == 100.0
    
    def test_is_terminal(self):
        """终态检查"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="COMPLETED",
            model="mace",
        )
        assert info.is_terminal
        
        info.status = "RUNNING"
        assert not info.is_terminal


class TestTaskResult:
    """TaskResult 模型测试"""
    
    def test_optimization_properties(self):
        """优化结果属性"""
        result = TaskResult(
            task_id="task-123",
            task_type="optimization",
            status="COMPLETED",
            result_data={
                "initial_energy": -100.0,
                "final_energy": -105.0,
                "n_steps": 50,
                "converged": True,
                "fmax": 0.01,
            },
        )
        
        assert result.initial_energy == -100.0
        assert result.final_energy == -105.0
        assert result.energy_change == -5.0
        assert result.optimization_steps == 50
        assert result.converged is True
        assert result.final_fmax == 0.01
    
    def test_bulk_modulus_properties(self):
        """体积模量结果属性"""
        result = TaskResult(
            task_id="task-123",
            task_type="bulk-modulus",
            status="COMPLETED",
            result_data={
                "K0": 15.5,
                "K0_prime": 4.2,
                "V0": 1000.0,
                "E0": -500.0,
                "r_squared": 0.999,
            },
        )
        
        assert result.bulk_modulus == 15.5
        assert result.bulk_modulus_derivative == 4.2
        assert result.equilibrium_volume == 1000.0
        assert result.equilibrium_energy == -500.0
        assert result.fitting_r_squared == 0.999


class TestStructureInfo:
    """StructureInfo 模型测试"""
    
    def test_from_dict(self):
        """从字典创建"""
        data = {
            "structure_id": "struct-123",
            "filename": "test.cif",
            "format": "cif",
            "n_atoms": 100,
            "formula": "Cu2O3",
        }
        
        info = StructureInfo.from_dict(data)
        
        assert info.structure_id == "struct-123"
        assert info.filename == "test.cif"
        assert info.format == "cif"
        assert info.n_atoms == 100
        assert info.formula == "Cu2O3"


class TestGPUInfo:
    """GPUInfo 模型测试"""
    
    def test_memory_usage_percent(self):
        """显存使用百分比"""
        gpu = GPUInfo(
            gpu_id=0,
            name="RTX 3090",
            memory_total=24.0,
            memory_used=12.0,
            memory_free=12.0,
        )
        
        assert gpu.memory_usage_percent == 50.0


class TestPaginatedResult:
    """PaginatedResult 模型测试"""
    
    def test_pagination_properties(self):
        """分页属性"""
        result = PaginatedResult(
            items=list(range(10)),
            total=35,
            page=2,
            page_size=10,
        )
        
        assert result.total_pages == 4
        assert result.has_next is True
        assert result.has_prev is True
    
    def test_first_page(self):
        """首页"""
        result = PaginatedResult(
            items=list(range(10)),
            total=35,
            page=1,
            page_size=10,
        )
        
        assert result.has_prev is False
        assert result.has_next is True
    
    def test_last_page(self):
        """末页"""
        result = PaginatedResult(
            items=list(range(5)),
            total=35,
            page=4,
            page_size=10,
        )
        
        assert result.has_prev is True
        assert result.has_next is False


# ===== 异常测试 =====

class TestExceptions:
    """异常类测试"""
    
    def test_mofsim_error(self):
        """基础异常"""
        error = MOFSimError("Test error", code="TEST_ERROR")
        assert str(error) == "[TEST_ERROR] Test error"
    
    def test_api_error(self):
        """API 错误"""
        error = APIError(
            "Not found",
            status_code=404,
            code="NOT_FOUND",
            request_id="req-123",
        )
        assert "HTTP 404" in str(error)
        assert "NOT_FOUND" in str(error)
        assert "req-123" in str(error)
    
    def test_task_not_found_error(self):
        """任务未找到错误"""
        error = TaskNotFoundError("task-123")
        assert error.task_id == "task-123"
        assert error.status_code == 404
    
    def test_task_failed_error(self):
        """任务失败错误"""
        error = TaskFailedError("task-123", "Calculation diverged")
        assert error.task_id == "task-123"
        assert "Calculation diverged" in str(error)
    
    def test_task_timeout_error(self):
        """任务超时错误"""
        error = TaskTimeoutError("task-123", 3600.0)
        assert error.task_id == "task-123"
        assert error.timeout == 3600.0
    
    def test_validation_error(self):
        """验证错误"""
        error = ValidationError(
            "Invalid parameters",
            field_errors={"fmax": "must be positive"},
        )
        assert error.field_errors["fmax"] == "must be positive"


# ===== 同步客户端测试 =====

class TestMOFSimClient:
    """同步客户端测试"""
    
    def test_init_defaults(self):
        """默认初始化"""
        client = MOFSimClient()
        assert client.base_url == "http://localhost:8000"
        assert client.api_prefix == "/api/v1"
        assert client.timeout == 30.0
        client.close()
    
    def test_init_custom(self):
        """自定义初始化"""
        client = MOFSimClient(
            base_url="https://api.example.com",
            api_key="test-key",
            timeout=60.0,
        )
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.timeout == 60.0
        client.close()
    
    def test_url_building(self):
        """URL 构建"""
        client = MOFSimClient(base_url="http://localhost:8000")
        assert client._url("/tasks") == "http://localhost:8000/api/v1/tasks"
        assert client._url("/api/v1/health") == "http://localhost:8000/api/v1/health"
        client.close()
    
    def test_context_manager(self):
        """上下文管理器"""
        with MOFSimClient() as client:
            assert isinstance(client, MOFSimClient)
    
    @patch.object(httpx.Client, 'request')
    def test_health_check(self, mock_request):
        """健康检查"""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            result = client.health_check()
        
        assert result["status"] == "healthy"
    
    @patch.object(httpx.Client, 'request')
    def test_is_healthy_true(self, mock_request):
        """健康状态 True"""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {"status": "healthy"}
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            assert client.is_healthy() is True
    
    @patch.object(httpx.Client, 'request')
    def test_is_healthy_false(self, mock_request):
        """健康状态 False"""
        mock_request.side_effect = httpx.ConnectError("Connection refused")
        
        with MOFSimClient() as client:
            assert client.is_healthy() is False
    
    @patch.object(httpx.Client, 'request')
    def test_list_models(self, mock_request):
        """列出模型"""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": {
                "models": [
                    {"name": "mace_mof_large", "family": "mace"},
                    {"name": "orb_v2", "family": "orb"},
                ]
            }
        }
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            models = client.list_models()
        
        assert len(models) == 2
        assert models[0].name == "mace_mof_large"
        assert models[1].family == "orb"
    
    @patch.object(httpx.Client, 'request')
    def test_get_gpu_status(self, mock_request):
        """获取 GPU 状态"""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": {
                "gpus": [
                    {
                        "gpu_id": 0,
                        "name": "RTX 3090",
                        "memory_total": 24.0,
                        "memory_used": 8.0,
                        "memory_free": 16.0,
                    }
                ]
            }
        }
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            gpus = client.get_gpu_status()
        
        assert len(gpus) == 1
        assert gpus[0].name == "RTX 3090"
        assert gpus[0].memory_usage_percent == pytest.approx(33.33, rel=0.01)
    
    @patch.object(httpx.Client, 'request')
    def test_list_tasks(self, mock_request):
        """列出任务"""
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "data": {
                "items": [
                    {"task_id": "task-1", "task_type": "optimization", "status": "COMPLETED", "model": "mace"},
                    {"task_id": "task-2", "task_type": "stability", "status": "RUNNING", "model": "orb"},
                ],
                "pagination": {"total": 2, "page": 1, "page_size": 20},
            }
        }
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            result = client.list_tasks()
        
        assert result.total == 2
        assert len(result.items) == 2
    
    @patch.object(httpx.Client, 'request')
    def test_error_handling_404(self, mock_request):
        """404 错误处理"""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Task not found", "code": "TASK_NOT_FOUND"}
        mock_response.text = "Task not found"
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            with pytest.raises(TaskNotFoundError):
                client.get_task_info("nonexistent")
    
    @patch.object(httpx.Client, 'request')
    def test_error_handling_422(self, mock_request):
        """422 验证错误处理"""
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 422
        mock_response.json.return_value = {"message": "Validation error"}
        mock_response.text = "Validation error"
        mock_request.return_value = mock_response
        
        with MOFSimClient() as client:
            with pytest.raises(ValidationError):
                client.get_task_info("task-123")
    
    @patch.object(httpx.Client, 'request')
    def test_connection_error(self, mock_request):
        """连接错误"""
        mock_request.side_effect = httpx.ConnectError("Connection refused")
        
        with MOFSimClient() as client:
            with pytest.raises(ConnectionError):
                client.health_check()


# ===== Task 对象测试 =====

class TestTask:
    """Task 对象测试"""
    
    def test_properties(self):
        """属性访问"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="RUNNING",
            model="mace",
            priority="HIGH",
            progress=50.0,
        )
        client = Mock()
        
        task = Task(info, client)
        
        assert task.task_id == "task-123"
        assert task.task_type == "optimization"
        assert task.status == "RUNNING"
        assert task.model == "mace"
        assert task.priority == "HIGH"
        assert task.progress == 50.0
        assert not task.is_terminal
    
    def test_refresh(self):
        """刷新状态"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="RUNNING",
            model="mace",
        )
        client = Mock()
        client.get_task_info.return_value = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="COMPLETED",
            model="mace",
        )
        
        task = Task(info, client)
        task.refresh()
        
        assert task.status == "COMPLETED"
        client.get_task_info.assert_called_once_with("task-123")
    
    def test_cancel(self):
        """取消任务"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="RUNNING",
            model="mace",
        )
        client = Mock()
        client.cancel_task.return_value = True
        client.get_task_info.return_value = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="CANCELLED",
            model="mace",
        )
        
        task = Task(info, client)
        result = task.cancel()
        
        assert result is True
        client.cancel_task.assert_called_once_with("task-123")
    
    def test_wait_completed(self):
        """等待完成"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="RUNNING",
            model="mace",
        )
        client = Mock()
        
        # 模拟状态变化
        call_count = [0]
        def get_task_info_side_effect(task_id):
            call_count[0] += 1
            if call_count[0] < 2:
                return TaskInfo(
                    task_id="task-123",
                    task_type="optimization",
                    status="RUNNING",
                    model="mace",
                )
            return TaskInfo(
                task_id="task-123",
                task_type="optimization",
                status="COMPLETED",
                model="mace",
            )
        
        client.get_task_info.side_effect = get_task_info_side_effect
        client.get_task_result.return_value = TaskResult(
            task_id="task-123",
            task_type="optimization",
            status="COMPLETED",
            result_data={"final_energy": -100.0},
        )
        
        task = Task(info, client)
        result = task.wait(poll_interval=0.01)
        
        assert result.final_energy == -100.0
    
    def test_wait_failed(self):
        """等待失败任务"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="RUNNING",
            model="mace",
        )
        client = Mock()
        client.get_task_info.return_value = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="FAILED",
            model="mace",
            error_message="Calculation diverged",
        )
        
        task = Task(info, client)
        
        with pytest.raises(TaskFailedError) as exc_info:
            task.wait(poll_interval=0.01)
        
        assert exc_info.value.task_id == "task-123"
    
    def test_repr(self):
        """字符串表示"""
        info = TaskInfo(
            task_id="task-123",
            task_type="optimization",
            status="COMPLETED",
            model="mace",
        )
        client = Mock()
        
        task = Task(info, client)
        
        assert "task-123" in repr(task)
        assert "optimization" in repr(task)
        assert "COMPLETED" in repr(task)


# ===== 导入测试 =====

class TestImports:
    """导入测试"""
    
    def test_main_imports(self):
        """主模块导入"""
        from sdk.mofsim_client import (
            MOFSimClient,
            AsyncMOFSimClient,
            Task,
            TaskResult,
            TaskStatus,
            MOFSimError,
            APIError,
            TaskNotFoundError,
            TaskFailedError,
            TaskTimeoutError,
            ValidationError,
            TaskInfo,
            StructureInfo,
            ModelInfo,
            GPUInfo,
            QueueInfo,
            __version__,
        )
        
        assert __version__ == "1.0.0"
    
    def test_exception_hierarchy(self):
        """异常继承关系"""
        from sdk.mofsim_client.exceptions import (
            MOFSimError,
            APIError,
            AuthenticationError,
            TaskNotFoundError,
            ValidationError,
        )
        
        assert issubclass(APIError, MOFSimError)
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(TaskNotFoundError, APIError)
        assert issubclass(ValidationError, APIError)
