# 测试指南

## 一、概述

本文档描述 MOFSimBench 项目的测试策略和编写规范。

---

## 二、测试类型

| 类型 | 说明 | 位置 |
|------|------|------|
| 单元测试 | 测试单个函数/类 | `tests/unit/` |
| 集成测试 | 测试组件交互 | `tests/integration/` |
| API 测试 | 测试 HTTP 接口 | `tests/api/` |
| 端到端测试 | 完整流程测试 | `tests/e2e/` |

---

## 三、测试框架

### 3.1 依赖

```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
```

### 3.2 配置

`pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: 标记为慢速测试
    gpu: 需要 GPU 的测试
```

`conftest.py`:

```python
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from api.main import app
from db.base import Base

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session
    
    await engine.dispose()

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

---

## 四、单元测试

### 4.1 测试服务类

```python
# tests/unit/test_task_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from core.services.task_service import TaskService
from api.schemas.task import TaskCreate

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_queue():
    return AsyncMock()

@pytest.fixture
def task_service(mock_db, mock_queue):
    return TaskService(db=mock_db, queue=mock_queue)

class TestTaskService:
    async def test_create_task_success(self, task_service, mock_db, mock_queue):
        # Arrange
        task_data = TaskCreate(
            model="mace_prod",
            structure_id="struct_xxx",
            parameters={"fmax": 0.001}
        )
        mock_db.create.return_value = MagicMock(id="task_123")
        
        # Act
        result = await task_service.create(task_data)
        
        # Assert
        assert result.id == "task_123"
        mock_db.create.assert_called_once()
        mock_queue.enqueue.assert_called_once()
    
    async def test_create_task_invalid_model_raises_error(self, task_service):
        # Arrange
        task_data = TaskCreate(
            model="invalid_model",
            structure_id="struct_xxx"
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="模型不存在"):
            await task_service.create(task_data)
```

### 4.2 测试调度器

```python
# tests/unit/test_scheduler.py

import pytest
from core.scheduler.scheduler import Scheduler
from core.scheduler.gpu_manager import GPUManager, GPUState

@pytest.fixture
def gpu_states():
    return {
        0: GPUState(id=0, status="free", memory_free_mb=20000, loaded_models=["mace_prod"]),
        1: GPUState(id=1, status="busy", memory_free_mb=10000, loaded_models=[]),
        2: GPUState(id=2, status="free", memory_free_mb=15000, loaded_models=[]),
    }

class TestScheduler:
    def test_select_gpu_prefers_model_affinity(self, gpu_states):
        # GPU 0 已加载 mace_prod，应该优先选择
        scheduler = Scheduler(gpu_states)
        task = MagicMock(model_name="mace_prod", estimated_memory=5000)
        
        gpu_id = scheduler.select_best_gpu(task)
        
        assert gpu_id == 0
    
    def test_select_gpu_skips_busy_gpu(self, gpu_states):
        scheduler = Scheduler(gpu_states)
        task = MagicMock(model_name="orb_prod", estimated_memory=5000)
        
        gpu_id = scheduler.select_best_gpu(task)
        
        assert gpu_id in [0, 2]  # 不应该选择 GPU 1
```

---

## 五、API 测试

### 5.1 测试端点

```python
# tests/api/test_tasks.py

import pytest
from httpx import AsyncClient

class TestTasksAPI:
    async def test_create_task_returns_202(self, client: AsyncClient):
        # Arrange
        task_data = {
            "model": "mace_prod",
            "structure": {"source": "builtin", "name": "MOF-5_primitive"},
            "parameters": {"fmax": 0.001}
        }
        
        # Act
        response = await client.post("/api/v1/tasks/optimization", json=task_data)
        
        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data["data"]
    
    async def test_create_task_invalid_model_returns_400(self, client: AsyncClient):
        task_data = {
            "model": "nonexistent_model",
            "structure": {"source": "builtin", "name": "MOF-5_primitive"}
        }
        
        response = await client.post("/api/v1/tasks/optimization", json=task_data)
        
        assert response.status_code == 400
        assert response.json()["success"] is False
    
    async def test_get_task_not_found_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/tasks/nonexistent_id")
        
        assert response.status_code == 404
```

### 5.2 测试认证

```python
# tests/api/test_auth.py

class TestAuthentication:
    async def test_request_without_api_key_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/tasks")
        
        assert response.status_code == 401
    
    async def test_request_with_invalid_api_key_returns_403(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer invalid_key"}
        )
        
        assert response.status_code == 403
    
    async def test_request_with_valid_api_key_succeeds(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer valid_test_key"}
        )
        
        assert response.status_code == 200
```

---

## 六、集成测试

### 6.1 数据库集成测试

```python
# tests/integration/test_db_integration.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from db.crud import TaskCRUD
from db.models import Task

class TestDatabaseIntegration:
    async def test_create_and_retrieve_task(self, db_session: AsyncSession):
        # Arrange
        crud = TaskCRUD(db_session)
        task_data = TaskCreate(model="mace_prod", structure_id="xxx")
        
        # Act
        created = await crud.create(task_data)
        retrieved = await crud.get(created.id)
        
        # Assert
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.model_name == "mace_prod"
    
    async def test_update_task_status(self, db_session: AsyncSession):
        crud = TaskCRUD(db_session)
        task = await crud.create(TaskCreate(model="mace_prod", structure_id="xxx"))
        
        await crud.update_status(task.id, "RUNNING")
        
        updated = await crud.get(task.id)
        assert updated.status == "RUNNING"
```

### 6.2 Redis 集成测试

```python
# tests/integration/test_redis_integration.py

import pytest
import redis.asyncio as redis

@pytest.fixture
async def redis_client():
    client = redis.from_url("redis://localhost:6379/15")  # 测试数据库
    yield client
    await client.flushdb()
    await client.close()

class TestRedisIntegration:
    async def test_enqueue_and_dequeue_task(self, redis_client):
        from core.scheduler.priority_queue import PriorityQueue
        
        queue = PriorityQueue(redis_client)
        
        await queue.enqueue("task_1", "NORMAL")
        await queue.enqueue("task_2", "HIGH")
        
        # HIGH 优先级应该先出队
        first = await queue.dequeue()
        assert first == "task_2"
        
        second = await queue.dequeue()
        assert second == "task_1"
```

---

## 七、端到端测试

### 7.1 完整任务流程

```python
# tests/e2e/test_task_flow.py

import pytest
import asyncio

@pytest.mark.slow
class TestTaskFlow:
    async def test_submit_and_complete_optimization_task(self, client: AsyncClient):
        # 1. 提交任务
        task_data = {
            "model": "mace_prod",
            "structure": {"source": "builtin", "name": "MOF-5_primitive"},
            "parameters": {"fmax": 0.01, "max_steps": 10}
        }
        
        response = await client.post("/api/v1/tasks/optimization", json=task_data)
        assert response.status_code == 202
        task_id = response.json()["data"]["task_id"]
        
        # 2. 等待任务完成（轮询）
        for _ in range(60):
            response = await client.get(f"/api/v1/tasks/{task_id}")
            status = response.json()["data"]["status"]
            
            if status in ["COMPLETED", "FAILED"]:
                break
            
            await asyncio.sleep(1)
        
        # 3. 验证结果
        assert status == "COMPLETED"
        
        response = await client.get(f"/api/v1/tasks/{task_id}/result")
        result = response.json()["data"]["result"]
        
        assert "converged" in result
        assert "final_energy_eV" in result
```

---

## 八、Mock 和 Fixture

### 8.1 Mock GPU

```python
@pytest.fixture
def mock_gpu_manager():
    manager = MagicMock()
    manager.get_free_gpus.return_value = [0, 1]
    manager.allocate.return_value = True
    manager.gpu_states = {
        0: GPUState(id=0, status="free", memory_free_mb=20000),
        1: GPUState(id=1, status="free", memory_free_mb=20000),
    }
    return manager
```

### 8.2 Mock 模型计算

```python
@pytest.fixture
def mock_calculator():
    calc = MagicMock()
    calc.get_potential_energy.return_value = -1234.567
    calc.get_forces.return_value = np.zeros((100, 3))
    return calc
```

---

## 九、运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/api/test_tasks.py

# 运行特定测试类
pytest tests/api/test_tasks.py::TestTasksAPI

# 运行特定测试函数
pytest tests/api/test_tasks.py::TestTasksAPI::test_create_task_returns_202

# 带覆盖率
pytest --cov=api --cov=core --cov-report=html

# 跳过慢速测试
pytest -m "not slow"

# 跳过需要 GPU 的测试
pytest -m "not gpu"

# 并行运行
pytest -n auto
```

---

## 十、覆盖率要求

| 模块 | 最低覆盖率 |
|------|-----------|
| api/ | 80% |
| core/ | 85% |
| db/ | 75% |
| 整体 | 80% |

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
