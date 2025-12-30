"""
稳定性任务
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask


class StabilityTask(BaseModelTask):
    """NPT MD 稳定性任务"""
    name = "workers.tasks.stability.run"
    
    def run(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 NPT MD 稳定性测试
        
        Args:
            parameters:
                - temperature: 温度 (K)
                - pressure: 压力 (bar)
                - steps: MD 步数
                - timestep: 时间步 (fs)
        """
        # TODO: Phase 2 实现
        raise NotImplementedError("Phase 2 实现")


@celery_app.task(bind=True, base=StabilityTask)
def run_stability(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """稳定性任务入口"""
    return self.run(task_id, model_name, structure_path, parameters)
