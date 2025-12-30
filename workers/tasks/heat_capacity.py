"""
热容任务
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask


class HeatCapacityTask(BaseModelTask):
    """热容计算任务"""
    name = "workers.tasks.heat_capacity.run"
    
    def run(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算热容
        
        Args:
            parameters:
                - temperatures: 温度列表 (K)
                - equilibration_steps: 平衡步数
                - production_steps: 采样步数
        """
        # TODO: Phase 2 实现
        raise NotImplementedError("Phase 2 实现")


@celery_app.task(bind=True, base=HeatCapacityTask)
def run_heat_capacity(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """热容任务入口"""
    return self.run(task_id, model_name, structure_path, parameters)
