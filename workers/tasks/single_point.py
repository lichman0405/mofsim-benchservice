"""
单点能量任务
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask


class SinglePointTask(BaseModelTask):
    """单点能量计算任务"""
    name = "workers.tasks.single_point.run"
    
    def run(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算单点能量、力和应力
        
        Args:
            parameters:
                - compute_forces: 是否计算力
                - compute_stress: 是否计算应力
        """
        # TODO: Phase 2 实现
        raise NotImplementedError("Phase 2 实现")


@celery_app.task(bind=True, base=SinglePointTask)
def run_single_point(self, task_id: str, model_name: str, structure_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """单点能量任务入口"""
    return self.run(task_id, model_name, structure_path, parameters)
