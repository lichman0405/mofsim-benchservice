"""
Prometheus 指标模块

参考文档: docs/engineering_requirements.md 第八节
提供系统监控指标，支持 Prometheus 抓取
"""
from datetime import datetime
from typing import Optional
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from core.config import get_settings

router = APIRouter()
settings = get_settings()

# 内存中的指标计数器
_metrics_state = {
    "requests_total": 0,
    "requests_by_status": {},
    "requests_by_endpoint": {},
    "request_duration_sum": 0.0,
    "request_count": 0,
    "start_time": time.time(),
    
    # 任务指标
    "tasks_submitted_total": 0,
    "tasks_completed_total": 0,
    "tasks_failed_total": 0,
    "tasks_cancelled_total": 0,
    "tasks_by_type": {},
    
    # 告警指标
    "alerts_triggered_total": 0,
    "alerts_resolved_total": 0,
}


def increment_request(status_code: int, endpoint: str, duration: float):
    """记录请求指标"""
    _metrics_state["requests_total"] += 1
    
    # 按状态码分组
    status_key = str(status_code)
    _metrics_state["requests_by_status"][status_key] = \
        _metrics_state["requests_by_status"].get(status_key, 0) + 1
    
    # 按端点分组
    _metrics_state["requests_by_endpoint"][endpoint] = \
        _metrics_state["requests_by_endpoint"].get(endpoint, 0) + 1
    
    # 延迟统计
    _metrics_state["request_duration_sum"] += duration
    _metrics_state["request_count"] += 1


def increment_task(task_type: str, status: str):
    """记录任务指标"""
    if status == "submitted":
        _metrics_state["tasks_submitted_total"] += 1
    elif status == "completed":
        _metrics_state["tasks_completed_total"] += 1
    elif status == "failed":
        _metrics_state["tasks_failed_total"] += 1
    elif status == "cancelled":
        _metrics_state["tasks_cancelled_total"] += 1
    
    # 按类型分组
    _metrics_state["tasks_by_type"][task_type] = \
        _metrics_state["tasks_by_type"].get(task_type, 0) + 1


def increment_alert(resolved: bool = False):
    """记录告警指标"""
    if resolved:
        _metrics_state["alerts_resolved_total"] += 1
    else:
        _metrics_state["alerts_triggered_total"] += 1


def _format_prometheus_metric(name: str, value, help_text: str, metric_type: str = "gauge", labels: Optional[dict] = None) -> str:
    """格式化 Prometheus 指标"""
    lines = []
    
    # HELP 和 TYPE
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} {metric_type}")
    
    # 值
    if labels:
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
        lines.append(f"{name}{{{label_str}}} {value}")
    else:
        lines.append(f"{name} {value}")
    
    return "\n".join(lines)


def _collect_gpu_metrics() -> str:
    """收集 GPU 指标"""
    lines = []
    
    try:
        from core.scheduler import get_gpu_manager
        gpu_manager = get_gpu_manager()
        gpu_manager.refresh_states()
        
        # GPU 总数
        lines.append(_format_prometheus_metric(
            "mofsimbench_gpu_total",
            len(gpu_manager.gpu_ids),
            "Total number of GPUs",
        ))
        
        # 可用 GPU 数
        available = sum(1 for s in gpu_manager.gpu_states.values() if s.is_available)
        lines.append(_format_prometheus_metric(
            "mofsimbench_gpu_available",
            available,
            "Number of available GPUs",
        ))
        
        # 每个 GPU 的详细指标
        for gpu_id, state in gpu_manager.gpu_states.items():
            labels = {"gpu_id": str(gpu_id), "gpu_name": state.name}
            
            # 显存使用
            lines.append(_format_prometheus_metric(
                "mofsimbench_gpu_memory_used_bytes",
                state.memory_used_mb * 1024 * 1024,
                "GPU memory used in bytes",
                labels=labels,
            ))
            
            lines.append(_format_prometheus_metric(
                "mofsimbench_gpu_memory_total_bytes",
                state.memory_total_mb * 1024 * 1024,
                "GPU memory total in bytes",
                labels=labels,
            ))
            
            # 温度
            if state.temperature_c > 0:
                lines.append(_format_prometheus_metric(
                    "mofsimbench_gpu_temperature_celsius",
                    state.temperature_c,
                    "GPU temperature in Celsius",
                    labels=labels,
                ))
            
            # 利用率
            if state.utilization_percent >= 0:
                lines.append(_format_prometheus_metric(
                    "mofsimbench_gpu_utilization_percent",
                    state.utilization_percent,
                    "GPU utilization percentage",
                    labels=labels,
                ))
            
            # 是否繁忙
            busy = 1 if state.current_task_id else 0
            lines.append(_format_prometheus_metric(
                "mofsimbench_gpu_busy",
                busy,
                "Whether GPU is running a task (1=busy, 0=idle)",
                labels=labels,
            ))
    except Exception:
        pass
    
    return "\n".join(lines)


def _collect_queue_metrics() -> str:
    """收集队列指标"""
    lines = []
    
    try:
        from core.scheduler import get_priority_queue
        queue = get_priority_queue()
        
        # 队列总大小
        lines.append(_format_prometheus_metric(
            "mofsimbench_queue_size",
            queue.size(),
            "Total number of tasks in queue",
        ))
        
        # 按优先级分组
        size_by_priority = queue.size_by_priority()
        for priority, count in size_by_priority.items():
            lines.append(_format_prometheus_metric(
                "mofsimbench_queue_size_by_priority",
                count,
                "Number of tasks in queue by priority",
                labels={"priority": str(priority)},
            ))
    except Exception:
        pass
    
    return "\n".join(lines)


def _collect_alert_metrics() -> str:
    """收集告警指标"""
    lines = []
    
    try:
        from alerts import get_alert_notifier
        notifier = get_alert_notifier()
        stats = notifier.get_stats()
        
        lines.append(_format_prometheus_metric(
            "mofsimbench_alerts_total",
            stats.get("total_alerts", 0),
            "Total number of alerts",
            metric_type="counter",
        ))
        
        lines.append(_format_prometheus_metric(
            "mofsimbench_alerts_active",
            stats.get("active_alerts", 0),
            "Number of active (unresolved) alerts",
        ))
        
        # 按级别
        by_level = stats.get("by_level", {})
        for level, count in by_level.items():
            lines.append(_format_prometheus_metric(
                "mofsimbench_alerts_by_level",
                count,
                "Number of alerts by level",
                labels={"level": level},
            ))
    except Exception:
        pass
    
    return "\n".join(lines)


@router.get("", response_class=PlainTextResponse)
async def get_metrics():
    """
    Prometheus 指标端点
    
    返回 Prometheus 格式的监控指标，包括：
    - 应用信息
    - 请求统计
    - GPU 状态
    - 队列状态
    - 任务统计
    - 告警统计
    """
    lines = []
    
    # ===== 应用信息 =====
    lines.append(_format_prometheus_metric(
        "mofsimbench_info",
        1,
        "Application information",
        labels={
            "version": settings.app_version,
            "environment": settings.environment,
        },
    ))
    
    # 运行时间
    uptime = time.time() - _metrics_state["start_time"]
    lines.append(_format_prometheus_metric(
        "mofsimbench_uptime_seconds",
        round(uptime, 2),
        "Application uptime in seconds",
        metric_type="counter",
    ))
    
    # ===== 请求指标 =====
    lines.append(_format_prometheus_metric(
        "mofsimbench_http_requests_total",
        _metrics_state["requests_total"],
        "Total number of HTTP requests",
        metric_type="counter",
    ))
    
    # 按状态码
    for status, count in _metrics_state["requests_by_status"].items():
        lines.append(_format_prometheus_metric(
            "mofsimbench_http_requests_by_status",
            count,
            "HTTP requests by status code",
            metric_type="counter",
            labels={"status": status},
        ))
    
    # 平均延迟
    if _metrics_state["request_count"] > 0:
        avg_duration = _metrics_state["request_duration_sum"] / _metrics_state["request_count"]
        lines.append(_format_prometheus_metric(
            "mofsimbench_http_request_duration_seconds_avg",
            round(avg_duration, 6),
            "Average HTTP request duration in seconds",
        ))
    
    # ===== 任务指标 =====
    lines.append(_format_prometheus_metric(
        "mofsimbench_tasks_submitted_total",
        _metrics_state["tasks_submitted_total"],
        "Total number of submitted tasks",
        metric_type="counter",
    ))
    
    lines.append(_format_prometheus_metric(
        "mofsimbench_tasks_completed_total",
        _metrics_state["tasks_completed_total"],
        "Total number of completed tasks",
        metric_type="counter",
    ))
    
    lines.append(_format_prometheus_metric(
        "mofsimbench_tasks_failed_total",
        _metrics_state["tasks_failed_total"],
        "Total number of failed tasks",
        metric_type="counter",
    ))
    
    # ===== GPU 指标 =====
    gpu_metrics = _collect_gpu_metrics()
    if gpu_metrics:
        lines.append(gpu_metrics)
    
    # ===== 队列指标 =====
    queue_metrics = _collect_queue_metrics()
    if queue_metrics:
        lines.append(queue_metrics)
    
    # ===== 告警指标 =====
    alert_metrics = _collect_alert_metrics()
    if alert_metrics:
        lines.append(alert_metrics)
    
    return "\n\n".join(lines) + "\n"
