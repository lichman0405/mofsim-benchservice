"""
系统相关数据模型

参考文档: docs/engineering_requirements.md 3.5 节
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    uptime_seconds: float = Field(..., description="运行时长 (秒)")


class GPUInfo(BaseModel):
    """单个 GPU 信息"""
    gpu_id: int = Field(..., description="GPU ID")
    name: str = Field(..., description="GPU 名称")
    
    memory_total_MB: int = Field(..., description="总显存 (MB)")
    memory_used_MB: int = Field(..., description="已用显存 (MB)")
    memory_free_MB: int = Field(..., description="可用显存 (MB)")
    
    temperature_C: Optional[int] = Field(None, description="温度 (°C)")
    utilization_percent: Optional[int] = Field(None, description="利用率 (%)")
    
    current_task_id: Optional[str] = Field(None, description="当前运行的任务 ID")
    loaded_models: List[str] = Field(default=[], description="已加载的模型")


class GPUStatusResponse(BaseModel):
    """GPU 状态响应"""
    gpus: List[GPUInfo] = Field(..., description="GPU 列表")
    total_gpus: int = Field(..., description="GPU 总数")
    available_gpus: int = Field(..., description="可用 GPU 数")


class QueueInfo(BaseModel):
    """队列信息"""
    priority: str = Field(..., description="优先级")
    count: int = Field(..., description="任务数量")


class QueueStatusResponse(BaseModel):
    """队列状态响应"""
    queues: List[QueueInfo] = Field(..., description="各优先级队列")
    total_pending: int = Field(..., description="总待处理任务数")
    total_running: int = Field(..., description="总运行中任务数")
    total_completed_today: int = Field(..., description="今日完成任务数")


class SystemConfigResponse(BaseModel):
    """系统配置响应（脱敏）"""
    gpu_count: int = Field(..., description="GPU 数量")
    max_concurrent_tasks: int = Field(..., description="最大并发任务数")
    default_timeout: int = Field(..., description="默认超时时间 (秒)")
    supported_models: List[str] = Field(..., description="支持的模型列表")
    version: str = Field(..., description="系统版本")
