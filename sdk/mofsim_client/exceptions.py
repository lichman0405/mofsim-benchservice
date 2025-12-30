"""
SDK 异常类型定义

提供详细的错误信息和类型，方便用户处理各种错误情况。
"""

from typing import Optional, Dict, Any


class MOFSimError(Exception):
    """
    MOFSimBench SDK 基础异常类
    
    所有 SDK 异常都继承自此类，可用于捕获所有 SDK 相关错误。
    
    Example:
        ```python
        try:
            result = client.get_task("task-123")
        except MOFSimError as e:
            print(f"SDK error: {e}")
        ```
    """
    
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, code={self.code!r})"


class APIError(MOFSimError):
    """
    API 请求错误
    
    当 API 返回非成功状态码时抛出。
    
    Attributes:
        status_code: HTTP 状态码
        request_id: 请求 ID（如果有）
    """
    
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code=code, details=details)
        self.status_code = status_code
        self.request_id = request_id
    
    def __str__(self) -> str:
        base = f"[HTTP {self.status_code}]"
        if self.code:
            base += f" [{self.code}]"
        base += f" {self.message}"
        if self.request_id:
            base += f" (request_id: {self.request_id})"
        return base


class AuthenticationError(APIError):
    """
    认证错误
    
    API 密钥无效或已过期时抛出。
    """
    pass


class TaskNotFoundError(APIError):
    """
    任务未找到错误
    
    请求的任务 ID 不存在时抛出。
    
    Attributes:
        task_id: 未找到的任务 ID
    """
    
    def __init__(
        self,
        task_id: str,
        *,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message or f"Task not found: {task_id}",
            status_code=404,
            code="TASK_NOT_FOUND",
            request_id=request_id,
        )
        self.task_id = task_id


class ModelNotFoundError(APIError):
    """
    模型未找到错误
    
    请求的模型名称不存在时抛出。
    
    Attributes:
        model_name: 未找到的模型名称
    """
    
    def __init__(
        self,
        model_name: str,
        *,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message or f"Model not found: {model_name}",
            status_code=404,
            code="MODEL_NOT_FOUND",
            request_id=request_id,
        )
        self.model_name = model_name


class StructureNotFoundError(APIError):
    """
    结构未找到错误
    
    请求的结构 ID 不存在时抛出。
    
    Attributes:
        structure_id: 未找到的结构 ID
    """
    
    def __init__(
        self,
        structure_id: str,
        *,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message or f"Structure not found: {structure_id}",
            status_code=404,
            code="STRUCTURE_NOT_FOUND",
            request_id=request_id,
        )
        self.structure_id = structure_id


class TaskFailedError(MOFSimError):
    """
    任务失败错误
    
    任务执行失败时抛出。
    
    Attributes:
        task_id: 失败的任务 ID
        error_message: 原始错误信息
    """
    
    def __init__(
        self,
        task_id: str,
        error_message: Optional[str] = None,
    ):
        super().__init__(
            f"Task failed: {task_id}" + (f" - {error_message}" if error_message else ""),
            code="TASK_FAILED",
        )
        self.task_id = task_id
        self.error_message = error_message


class TaskTimeoutError(MOFSimError):
    """
    任务超时错误
    
    等待任务完成超时时抛出。
    
    Attributes:
        task_id: 超时的任务 ID
        timeout: 超时时间（秒）
    """
    
    def __init__(
        self,
        task_id: str,
        timeout: float,
    ):
        super().__init__(
            f"Task timed out after {timeout}s: {task_id}",
            code="TASK_TIMEOUT",
        )
        self.task_id = task_id
        self.timeout = timeout


class TaskCancelledError(MOFSimError):
    """
    任务取消错误
    
    任务被取消时抛出。
    
    Attributes:
        task_id: 被取消的任务 ID
    """
    
    def __init__(self, task_id: str):
        super().__init__(
            f"Task was cancelled: {task_id}",
            code="TASK_CANCELLED",
        )
        self.task_id = task_id


class ValidationError(APIError):
    """
    请求验证错误
    
    请求参数不符合要求时抛出。
    
    Attributes:
        field_errors: 字段错误详情
    """
    
    def __init__(
        self,
        message: str,
        *,
        field_errors: Optional[Dict[str, str]] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message,
            status_code=422,
            code="VALIDATION_ERROR",
            request_id=request_id,
            details={"field_errors": field_errors or {}},
        )
        self.field_errors = field_errors or {}


class ConnectionError(MOFSimError):
    """
    连接错误
    
    无法连接到 API 服务器时抛出。
    """
    
    def __init__(self, message: str = "Failed to connect to server"):
        super().__init__(message, code="CONNECTION_ERROR")


class RateLimitError(APIError):
    """
    请求限流错误
    
    请求频率过高时抛出。
    
    Attributes:
        retry_after: 重试等待时间（秒）
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: Optional[float] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message,
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            request_id=request_id,
        )
        self.retry_after = retry_after


class ServerError(APIError):
    """
    服务器内部错误
    
    服务器发生内部错误时抛出。
    """
    
    def __init__(
        self,
        message: str = "Internal server error",
        *,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            message,
            status_code=500,
            code="INTERNAL_ERROR",
            request_id=request_id,
        )
