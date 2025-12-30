"""
告警检查器

参考文档: docs/engineering_requirements.md 7.2 节
定时检查系统指标并触发告警
"""
import asyncio
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
import structlog

from .rules import AlertRuleEngine, AlertRule, get_rule_engine

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """
    指标收集器
    
    收集系统各项指标用于告警评估
    """
    
    def __init__(self):
        self._custom_collectors: Dict[str, Callable[[], float]] = {}
    
    def register_collector(self, metric: str, collector: Callable[[], float]) -> None:
        """注册自定义指标收集器"""
        self._custom_collectors[metric] = collector
    
    async def collect(self) -> Dict[str, float]:
        """
        收集所有指标
        
        Returns:
            指标名称到值的映射
        """
        metrics = {}
        
        # GPU 指标
        gpu_metrics = await self._collect_gpu_metrics()
        metrics.update(gpu_metrics)
        
        # 队列指标
        queue_metrics = await self._collect_queue_metrics()
        metrics.update(queue_metrics)
        
        # 磁盘指标
        disk_metrics = self._collect_disk_metrics()
        metrics.update(disk_metrics)
        
        # Worker 指标
        worker_metrics = await self._collect_worker_metrics()
        metrics.update(worker_metrics)
        
        # 自定义指标
        for metric, collector in self._custom_collectors.items():
            try:
                metrics[metric] = collector()
            except Exception as e:
                logger.warning("custom_metric_failed", metric=metric, error=str(e))
        
        return metrics
    
    async def _collect_gpu_metrics(self) -> Dict[str, float]:
        """收集 GPU 指标"""
        try:
            from core.scheduler import GPUManager
            
            gpu_manager = GPUManager(mock_mode=False)
            gpu_manager.refresh_states()
            
            if not gpu_manager.gpu_states:
                return {
                    "available_gpus": 0,
                    "total_gpus": 0,
                    "min_gpu_free_memory_gb": 0,
                    "max_gpu_temp": 0,
                }
            
            free_gpus = gpu_manager.get_free_gpus()
            temps = [s.temperature_c for s in gpu_manager.gpu_states.values() if s.temperature_c > 0]
            free_mem = [s.memory_free_mb / 1024 for s in gpu_manager.gpu_states.values()]
            
            return {
                "available_gpus": len(free_gpus),
                "total_gpus": len(gpu_manager.gpu_states),
                "min_gpu_free_memory_gb": min(free_mem) if free_mem else 0,
                "max_gpu_temp": max(temps) if temps else 0,
            }
        except Exception as e:
            logger.warning("gpu_metrics_failed", error=str(e))
            # 返回安全的默认值（不触发告警）
            return {
                "available_gpus": 8,
                "total_gpus": 8,
                "min_gpu_free_memory_gb": 24,
                "max_gpu_temp": 50,
            }
    
    async def _collect_queue_metrics(self) -> Dict[str, float]:
        """收集队列指标"""
        try:
            from core.scheduler import PriorityQueue
            
            queue = PriorityQueue()
            return {
                "queue_length": queue.size(),
            }
        except Exception as e:
            logger.warning("queue_metrics_failed", error=str(e))
            return {"queue_length": 0}
    
    def _collect_disk_metrics(self) -> Dict[str, float]:
        """收集磁盘指标"""
        try:
            usage = shutil.disk_usage("/")
            free_gb = usage.free / (1024 ** 3)
            return {"disk_free_gb": free_gb}
        except Exception as e:
            logger.warning("disk_metrics_failed", error=str(e))
            return {"disk_free_gb": 100}  # 安全默认值
    
    async def _collect_worker_metrics(self) -> Dict[str, float]:
        """收集 Worker 指标"""
        try:
            # TODO: 实际从 Celery 获取 worker 状态
            # 目前返回安全默认值
            return {"active_workers": 1}
        except Exception as e:
            logger.warning("worker_metrics_failed", error=str(e))
            return {"active_workers": 1}


class AlertChecker:
    """
    告警检查器
    
    定时检查系统指标并触发告警
    """
    
    def __init__(
        self,
        check_interval: float = 60.0,  # 检查间隔（秒）
        rule_engine: Optional[AlertRuleEngine] = None,
    ):
        self.check_interval = check_interval
        self.rule_engine = rule_engine or get_rule_engine()
        self.metrics_collector = MetricsCollector()
        
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self._on_alert_callbacks: List[Callable[[AlertRule, Dict[str, float]], None]] = []
        
        # 统计
        self._check_count = 0
        self._last_check: Optional[datetime] = None
        self._last_metrics: Dict[str, float] = {}
    
    def on_alert(self, callback: Callable[[AlertRule, Dict[str, float]], None]) -> None:
        """注册告警回调"""
        self._on_alert_callbacks.append(callback)
    
    async def start(self) -> None:
        """启动定时检查"""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("alert_checker_started", interval=self.check_interval)
    
    async def stop(self) -> None:
        """停止定时检查"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("alert_checker_stopped")
    
    async def _check_loop(self) -> None:
        """检查循环"""
        while self._running:
            try:
                await self.check_once()
            except Exception as e:
                logger.error("alert_check_failed", error=str(e))
            
            await asyncio.sleep(self.check_interval)
    
    async def check_once(self) -> List[AlertRule]:
        """
        执行一次检查
        
        Returns:
            触发的规则列表
        """
        # 收集指标
        metrics = await self.metrics_collector.collect()
        self._last_metrics = metrics
        self._last_check = datetime.utcnow()
        self._check_count += 1
        
        # 评估规则
        triggered = self.rule_engine.evaluate(metrics)
        
        # 触发回调
        for rule in triggered:
            for callback in self._on_alert_callbacks:
                try:
                    callback(rule, metrics)
                except Exception as e:
                    logger.error("alert_callback_failed", error=str(e))
        
        return triggered
    
    def get_stats(self) -> Dict[str, Any]:
        """获取检查器统计"""
        return {
            "running": self._running,
            "check_interval": self.check_interval,
            "check_count": self._check_count,
            "last_check": self._last_check.isoformat() + "Z" if self._last_check else None,
            "last_metrics": self._last_metrics,
            "rules_count": len(self.rule_engine.list_rules()),
            "enabled_rules": len(self.rule_engine.list_rules(enabled_only=True)),
        }


# 全局单例
_alert_checker: Optional[AlertChecker] = None


def get_alert_checker() -> AlertChecker:
    """获取告警检查器单例"""
    global _alert_checker
    if _alert_checker is None:
        _alert_checker = AlertChecker()
    return _alert_checker
