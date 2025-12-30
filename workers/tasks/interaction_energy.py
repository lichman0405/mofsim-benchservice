"""
相互作用能任务

集成 core/tasks/interaction_energy.py 执行器
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.interaction_energy import InteractionEnergyExecutor


class InteractionEnergyTask(BaseModelTask):
    """相互作用能计算任务"""
    name = "workers.tasks.interaction_energy.run"
    executor_class = InteractionEnergyExecutor
    
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
        计算分子-框架相互作用能
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 相互作用能参数
                - gas_molecule: 气体分子类型 (CO2, H2, CH4, N2, H2O, CO, NH3)
                - positions: 位置生成方法 (grid, random, specified)
                - n_grid_points: 网格点数
                - optimize_gas: 是否优化气体位置
        
        Returns:
            相互作用能结果，包含:
            - E_interaction_eV: 相互作用能 (eV)
            - E_mof_eV: MOF 能量
            - E_gas_eV: 气体能量
            - best_position: 最佳插入位置
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=InteractionEnergyTask)
def run_interaction_energy(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """相互作用能任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
