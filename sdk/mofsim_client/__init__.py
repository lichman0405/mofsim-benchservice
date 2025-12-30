"""
MOFSimBench Python SDK

一个用于与 MOFSimBench 服务进行交互的 Python 客户端库。

基本用法:
    ```python
    from mofsim_client import MOFSimClient
    
    # 创建同步客户端
    client = MOFSimClient("http://localhost:8000")
    
    # 提交优化任务
    task = client.submit_optimization(
        model="mace_mof_large",
        structure_file="structure.cif",
        fmax=0.05
    )
    
    # 等待结果
    result = task.wait()
    print(result.final_energy)
    ```

异步用法:
    ```python
    from mofsim_client import AsyncMOFSimClient
    
    async with AsyncMOFSimClient("http://localhost:8000") as client:
        task = await client.submit_optimization(
            model="mace_mof_large",
            structure_file="structure.cif"
        )
        result = await task.wait()
    ```
"""

from .client import MOFSimClient
from .async_client import AsyncMOFSimClient
from .task import Task, TaskResult, TaskStatus
from .exceptions import (
    MOFSimError,
    APIError,
    AuthenticationError,
    TaskNotFoundError,
    TaskFailedError,
    TaskTimeoutError,
    ValidationError,
    ConnectionError,
    RateLimitError,
)
from .models import (
    TaskInfo,
    StructureInfo,
    ModelInfo,
    GPUInfo,
    QueueInfo,
)

__version__ = "1.0.0"

__all__ = [
    # Clients
    "MOFSimClient",
    "AsyncMOFSimClient",
    # Task
    "Task",
    "TaskResult",
    "TaskStatus",
    # Exceptions
    "MOFSimError",
    "APIError",
    "AuthenticationError",
    "TaskNotFoundError",
    "TaskFailedError",
    "TaskTimeoutError",
    "ValidationError",
    "ConnectionError",
    "RateLimitError",
    # Models
    "TaskInfo",
    "StructureInfo",
    "ModelInfo",
    "GPUInfo",
    "QueueInfo",
    # Version
    "__version__",
]
