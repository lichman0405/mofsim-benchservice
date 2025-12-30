"""
维护任务

定时执行的系统维护任务
"""
from celery import shared_task
import structlog
import time

logger = structlog.get_logger(__name__)


@shared_task(name="workers.tasks.maintenance.cleanup_expired")
def cleanup_expired():
    """
    清理过期任务和结果
    
    定时执行：每小时
    """
    logger.info("cleanup_expired_started")
    
    try:
        # TODO: 实现清理逻辑
        # 1. 清理超过 7 天的已完成任务
        # 2. 清理孤立的结果文件
        # 3. 清理临时文件
        
        cleaned_count = 0
        
        logger.info(
            "cleanup_expired_completed",
            cleaned_count=cleaned_count
        )
        
        return {"cleaned_count": cleaned_count}
        
    except Exception as e:
        logger.error("cleanup_expired_failed", error=str(e))
        raise


@shared_task(name="workers.tasks.maintenance.refresh_gpu_status")
def refresh_gpu_status():
    """
    刷新 GPU 状态
    
    定时执行：每 30 秒
    """
    try:
        # 这个任务在每个 Worker 上运行
        # 每个 Worker 只报告自己绑定的 GPU 状态
        import os
        
        gpu_id = os.environ.get("MOFSIM_WORKER_GPU_ID")
        worker_id = os.environ.get("MOFSIM_WORKER_ID", "unknown")
        
        if gpu_id is None:
            return {"status": "no_gpu"}
        
        # 获取 GPU 状态
        gpu_info = _get_gpu_info(int(gpu_id))
        
        logger.debug(
            "gpu_status_refreshed",
            worker_id=worker_id,
            gpu_id=gpu_id,
            gpu_info=gpu_info
        )
        
        return {
            "worker_id": worker_id,
            "gpu_id": gpu_id,
            "gpu_info": gpu_info,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.warning("refresh_gpu_status_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def _get_gpu_info(gpu_id: int) -> dict:
    """获取单个 GPU 信息"""
    try:
        import pynvml
        pynvml.nvmlInit()
        
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode()
        
        pynvml.nvmlShutdown()
        
        return {
            "name": name,
            "memory_total_mb": memory.total // 1024 // 1024,
            "memory_used_mb": memory.used // 1024 // 1024,
            "memory_free_mb": memory.free // 1024 // 1024,
            "utilization_percent": util.gpu,
            "temperature_c": temp,
        }
    except Exception:
        # 无 GPU 或 pynvml 不可用
        return {
            "name": f"Mock GPU {gpu_id}",
            "memory_total_mb": 24000,
            "memory_used_mb": 2000,
            "memory_free_mb": 22000,
            "utilization_percent": 0,
            "temperature_c": 40,
            "mock": True,
        }


@shared_task(name="workers.tasks.maintenance.health_check")
def health_check():
    """
    Worker 健康检查
    """
    import os
    import socket
    
    return {
        "status": "healthy",
        "worker_id": os.environ.get("MOFSIM_WORKER_ID", "unknown"),
        "gpu_id": os.environ.get("MOFSIM_WORKER_GPU_ID"),
        "hostname": socket.gethostname(),
        "timestamp": time.time(),
    }
