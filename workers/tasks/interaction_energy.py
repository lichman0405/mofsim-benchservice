"""
相互作用能任务
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask


class InteractionEnergyTask(BaseModelTask):
    """相互作用能计算任务"""
    name = "workers.tasks.interaction_energy.run"
    
    def run(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算分子-框架相互作用能
        
        Args:
            parameters:
                - adsorbate: 吸附质分子
                - grid_spacing: 采样网格间距
        """
        # TODO: Phase 2 实现
        raise NotImplementedError("Phase 2 实现")


@celery_app.task(bind=True, base=InteractionEnergyTask)
def run_interaction_energy(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """相互作用能任务入口"""
    return self.run(task_id, model_name, structure_path, parameters)
