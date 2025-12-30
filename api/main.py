"""
FastAPI 应用主入口

参考文档:
- docs/architecture/api_design.md 第二节
- docs/engineering_requirements.md 第五节
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import tasks, models, structures, system, alerts
from api.middleware.logging import LoggingMiddleware
from api.middleware.error_handler import (
    TaskNotFoundError,
    ModelNotFoundError,
    StructureFormatError,
    GPUUnavailableError,
    ErrorCode,
)
from api.schemas.response import success_response
from core.config import get_settings
from logging_config import setup_logging, get_logger

# 获取配置
settings = get_settings()

# 配置日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时:
    - 初始化数据库连接
    - 检查 Redis 连接
    - 加载内置模型列表
    
    关闭时:
    - 关闭数据库连接
    - 清理资源
    """
    # 启动
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    
    app.state.start_time = datetime.utcnow()
    
    # TODO: Phase 2 - 初始化数据库连接池
    # TODO: Phase 2 - 检查 Redis 连接
    # TODO: Phase 3 - 加载模型列表
    
    logger.info("application_started")
    
    yield
    
    # 关闭
    logger.info("application_shutting_down")
    
    # TODO: 清理资源
    
    logger.info("application_stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="MOFSimBench - Universal Machine Learning Interatomic Potential Benchmark for MOF Simulations",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# ===== 中间件 =====

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志
app.add_middleware(LoggingMiddleware)


# ===== 路由 =====

# API 版本前缀
API_PREFIX = settings.api_prefix


# 健康检查 (无前缀)
@app.get("/health")
async def health_check_root():
    """根路径健康检查"""
    return success_response(
        data={
            "status": "healthy",
            "version": settings.app_version,
        }
    )


# 带前缀的健康检查
@app.get(f"{API_PREFIX}/health")
async def health_check():
    """API 健康检查"""
    uptime = (datetime.utcnow() - app.state.start_time).total_seconds() if hasattr(app.state, 'start_time') else 0
    
    return success_response(
        data={
            "status": "healthy",
            "version": settings.app_version,
            "uptime_seconds": round(uptime, 2),
            "environment": settings.environment,
        }
    )


# 注册路由
app.include_router(tasks.router, prefix=f"{API_PREFIX}/tasks", tags=["Tasks"])
app.include_router(models.router, prefix=f"{API_PREFIX}/models", tags=["Models"])
app.include_router(structures.router, prefix=f"{API_PREFIX}/structures", tags=["Structures"])
app.include_router(system.router, prefix=f"{API_PREFIX}/system", tags=["System"])
app.include_router(alerts.router, prefix=f"{API_PREFIX}/alerts", tags=["Alerts"])


# ===== 全局异常处理 =====

@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: TaskNotFoundError):
    """任务未找到异常处理"""
    logger.warning("task_not_found", task_id=exc.task_id, path=request.url.path)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "code": ErrorCode.TASK_NOT_FOUND,
            "message": "任务未找到",
            "error": {
                "type": "TaskNotFoundError",
                "detail": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(request: Request, exc: ModelNotFoundError):
    """模型未找到异常处理"""
    logger.warning("model_not_found", model_name=exc.model_name, path=request.url.path)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "code": ErrorCode.MODEL_NOT_FOUND,
            "message": "模型未找到",
            "error": {
                "type": "ModelNotFoundError",
                "detail": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.exception_handler(StructureFormatError)
async def structure_format_error_handler(request: Request, exc: StructureFormatError):
    """结构格式错误异常处理"""
    logger.warning("structure_format_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "code": ErrorCode.STRUCTURE_FORMAT_INVALID,
            "message": "结构格式错误",
            "error": {
                "type": "StructureFormatError",
                "detail": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.exception_handler(GPUUnavailableError)
async def gpu_unavailable_handler(request: Request, exc: GPUUnavailableError):
    """GPU 不可用异常处理"""
    logger.error("gpu_unavailable", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "code": ErrorCode.GPU_UNAVAILABLE,
            "message": "GPU 不可用",
            "error": {
                "type": "GPUUnavailableError",
                "detail": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 50000,
            "message": "内部服务器错误",
            "error": {
                "type": "InternalError",
                "detail": "发生未预期的错误，请联系管理员" if not settings.debug else str(exc),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


# ===== 开发模式入口 =====

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
