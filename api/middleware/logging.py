"""
请求日志中间件

参考文档: docs/engineering_requirements.md 6.2 节
使用 structlog 结构化日志
"""
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    
    记录每个请求的:
    - 请求 ID
    - 请求方法、路径
    - 客户端 IP
    - 响应状态码
    - 处理时长
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成或获取请求 ID
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
        
        # 绑定请求 ID 到日志上下文
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # 记录请求开始
        start_time = time.perf_counter()
        
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            
            # 计算处理时长
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # 记录请求完成
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise
