"""
热容任务

集成 core/tasks/heat_capacity.py 执行器
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.heat_capacity import HeatCapacityExecutor


class HeatCapacityTask(BaseModelTask):
    """热容计算任务"""
    name = "workers.tasks.heat_capacity.run"
    executor_class = HeatCapacityExecutor
    
    def run(
        self,
        task_id: str,
        model_name: str,
        structure_path: str,
        parameters: Dict[str, Any],
        gpu_id: int = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        计算热容
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 热容参数
                - temperature: 目标温度 (K)
                - supercell: 超胞大小
                - displacement: 位移大小 (Å)
                - run_optimization: 是否先优化
        
        Returns:
            热容结果，包含:
            - Cv_kB_per_atom: 每原子热容 (kB)
            - Cv_J_mol_K: 摩尔热容 (J/mol/K)
            - thermal_properties: 热力学性质
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=HeatCapacityTask)
def run_heat_capacity(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """热容任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
