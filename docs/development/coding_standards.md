# 代码规范

## 一、概述

本文档定义 MOFSimBench 项目的代码规范和最佳实践。

---

## 二、Python 代码风格

### 2.1 基本规范

遵循 [PEP 8](https://peps.python.org/pep-0008/) 规范，使用 Black 格式化。

```python
# 使用 Black 格式化
black --line-length 88 .

# 使用 isort 排序导入
isort --profile black .
```

### 2.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `task_service.py` |
| 类 | PascalCase | `TaskService` |
| 函数/方法 | snake_case | `get_task_status()` |
| 变量 | snake_case | `task_id` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| 私有属性 | _前缀 | `_internal_cache` |

### 2.3 类型注解

所有公开函数必须有完整的类型注解：

```python
from typing import Optional, List, Dict

def get_task(
    task_id: str,
    include_logs: bool = False
) -> Optional[Task]:
    """获取任务详情。
    
    Args:
        task_id: 任务 ID
        include_logs: 是否包含日志
    
    Returns:
        任务对象，不存在时返回 None
    """
    ...
```

### 2.4 文档字符串

使用 Google 风格的 docstring：

```python
def schedule_task(
    task: Task,
    priority: str = "NORMAL"
) -> ScheduleResult:
    """调度任务到可用 GPU。
    
    根据优先级和资源可用性将任务分配到合适的 GPU。
    
    Args:
        task: 待调度的任务对象
        priority: 优先级，可选值: CRITICAL, HIGH, NORMAL, LOW
    
    Returns:
        ScheduleResult: 调度结果，包含分配的 GPU ID
    
    Raises:
        NoGPUAvailableError: 没有可用的 GPU
        InvalidTaskError: 任务配置无效
    
    Example:
        >>> result = schedule_task(task, priority="HIGH")
        >>> print(result.gpu_id)
        0
    """
    ...
```

---

## 三、项目结构规范

### 3.1 模块组织

```python
# 导入顺序
# 1. 标准库
import os
import json
from typing import Optional

# 2. 第三方库
import numpy as np
from fastapi import FastAPI
from sqlalchemy import Column

# 3. 本地模块
from core.config import settings
from db.models import Task
```

### 3.2 文件结构

每个模块文件应包含：

```python
"""模块说明。

详细描述该模块的功能和用途。
"""

# 导入
...

# 常量
...

# 类型定义
...

# 类
...

# 函数
...

# 模块级代码（仅用于脚本）
if __name__ == "__main__":
    ...
```

---

## 四、API 开发规范

### 4.1 路由定义

```python
from fastapi import APIRouter, Depends, HTTPException, status
from api.schemas.task import TaskCreate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交任务",
    description="提交一个新的计算任务到队列"
)
async def create_task(
    task_data: TaskCreate,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """提交新任务。"""
    task = await task_service.create(task_data)
    return TaskResponse.from_orm(task)
```

### 4.2 Schema 定义

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class TaskCreate(BaseModel):
    """任务创建请求"""
    
    model: str = Field(..., description="模型名称")
    structure_id: str = Field(..., description="结构文件 ID")
    parameters: dict = Field(default_factory=dict, description="任务参数")
    priority: str = Field(default="NORMAL", description="优先级")
    
    @validator("priority")
    def validate_priority(cls, v):
        valid = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
        if v not in valid:
            raise ValueError(f"优先级必须是 {valid} 之一")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "model": "mace_prod",
                "structure_id": "struct_xxx",
                "parameters": {"fmax": 0.001},
                "priority": "NORMAL"
            }
        }
```

### 4.3 错误处理

```python
from fastapi import HTTPException

class TaskNotFoundError(Exception):
    """任务不存在"""
    pass

# 在路由中
@router.get("/{task_id}")
async def get_task(task_id: str):
    task = await task_service.get(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "code": 40401,
                "message": f"任务 {task_id} 不存在"
            }
        )
    return task
```

---

## 五、数据库操作规范

### 5.1 ORM 模型

```python
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base
import uuid

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    parameters = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Task(id={self.id}, type={self.task_type}, status={self.status})>"
```

### 5.2 CRUD 操作

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class TaskCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get(self, task_id: str) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, task_data: TaskCreate) -> Task:
        task = Task(**task_data.dict())
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task
```

---

## 六、日志规范

### 6.1 使用 structlog

```python
import structlog

logger = structlog.get_logger(__name__)

async def process_task(task_id: str):
    log = logger.bind(task_id=task_id)
    
    log.info("开始处理任务")
    
    try:
        result = await execute_task(task_id)
        log.info("任务完成", result=result)
    except Exception as e:
        log.error("任务失败", error=str(e), exc_info=True)
        raise
```

### 6.2 日志级别使用

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 详细的变量值、流程跟踪 |
| INFO | 正常操作 | 任务开始、完成、状态变更 |
| WARNING | 潜在问题 | 重试、降级、非致命错误 |
| ERROR | 错误 | 任务失败、异常 |
| CRITICAL | 严重错误 | 系统不可用 |

---

## 七、测试规范

### 7.1 测试文件命名

```
tests/
├── test_api/
│   ├── test_tasks.py
│   └── test_models.py
├── test_core/
│   ├── test_scheduler.py
│   └── test_task_executor.py
└── conftest.py
```

### 7.2 测试函数命名

```python
# 格式：test_<功能>_<场景>_<预期结果>

def test_create_task_with_valid_data_returns_task_id():
    ...

def test_create_task_with_invalid_model_raises_error():
    ...

async def test_schedule_task_when_no_gpu_available_queues_task():
    ...
```

### 7.3 使用 Fixtures

```python
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_task_data():
    return {
        "model": "mace_prod",
        "structure_id": "test_struct",
        "parameters": {"fmax": 0.001}
    }

async def test_create_task(client, sample_task_data):
    response = await client.post("/api/v1/tasks", json=sample_task_data)
    assert response.status_code == 202
```

---

## 八、Git 提交规范

### 8.1 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 8.2 Type 类型

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 bug |
| docs | 文档更新 |
| style | 代码格式（不影响功能） |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具相关 |

### 8.3 示例

```
feat(scheduler): 添加模型亲和性调度策略

- 优先将任务调度到已加载相同模型的 GPU
- 减少模型加载时间，提高吞吐量

Closes #123
```

---

## 九、代码审查清单

- [ ] 代码符合 PEP 8 规范
- [ ] 所有公开函数有类型注解
- [ ] 所有公开函数有文档字符串
- [ ] 错误处理完整
- [ ] 日志记录适当
- [ ] 有相应的测试用例
- [ ] 没有硬编码的配置值
- [ ] 没有敏感信息泄露

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
