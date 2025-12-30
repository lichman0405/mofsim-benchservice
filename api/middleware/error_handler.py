"""
全局错误处理中间件

参考文档: docs/engineering_requirements.md 5.4 节
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from api.schemas.response import error_response

logger = structlog.get_logger(__name__)


class ErrorCode:
    """错误码定义"""
    # 通用错误 (40xxx)
    BAD_REQUEST = 40000
    STRUCTURE_FORMAT_INVALID = 40001
    PARAMETER_INVALID = 40002
    MODEL_NOT_FOUND = 40401
    TASK_NOT_FOUND = 40402
    STRUCTURE_NOT_FOUND = 40403
    
    # 服务器错误 (50xxx)
    INTERNAL_ERROR = 50000
    GPU_UNAVAILABLE = 50001
    MODEL_LOAD_FAILED = 50002
    TASK_EXECUTION_FAILED = 50003
    
    # 队列错误 (51xxx)
    QUEUE_FULL = 51000
    QUEUE_TIMEOUT = 51001


class TaskNotFoundError(Exception):
    """任务未找到"""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"任务 {task_id} 未找到")


class ModelNotFoundError(Exception):
    """模型未找到"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"模型 {model_name} 未找到")


class StructureFormatError(Exception):
    """结构格式错误"""
    def __init__(self, message: str):
        super().__init__(message)


class GPUUnavailableError(Exception):
    """GPU 不可用"""
    pass


async def error_handler_middleware(request: Request, call_next):
    """
    全局错误处理中间件
    
    捕获异常并转换为统一响应格式
    """
    try:
        return await call_next(request)
    except TaskNotFoundError as e:
        logger.warning("task_not_found", task_id=e.task_id)
        return JSONResponse(
            status_code=404,
            content=error_response(
                message="任务未找到",
                code=ErrorCode.TASK_NOT_FOUND,
                error_type="TaskNotFoundError",
                detail=str(e),
            )
        )
    except ModelNotFoundError as e:
        logger.warning("model_not_found", model_name=e.model_name)
        return JSONResponse(
            status_code=404,
            content=error_response(
                message="模型未找到",
                code=ErrorCode.MODEL_NOT_FOUND,
                error_type="ModelNotFoundError",
                detail=str(e),
            )
        )
    except StructureFormatError as e:
        logger.warning("structure_format_error", message=str(e))
        return JSONResponse(
            status_code=400,
            content=error_response(
                message="结构格式错误",
                code=ErrorCode.STRUCTURE_FORMAT_INVALID,
                error_type="StructureFormatError",
                detail=str(e),
            )
        )
    except GPUUnavailableError as e:
        logger.error("gpu_unavailable", message=str(e))
        return JSONResponse(
            status_code=503,
            content=error_response(
                message="GPU 不可用",
                code=ErrorCode.GPU_UNAVAILABLE,
                error_type="GPUUnavailableError",
                detail=str(e),
            )
        )
    except Exception as e:
        logger.error("unhandled_exception", error=str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content=error_response(
                message="内部服务器错误",
                code=ErrorCode.INTERNAL_ERROR,
                error_type="InternalError",
                detail="发生未预期的错误，请联系管理员",
            )
        )
