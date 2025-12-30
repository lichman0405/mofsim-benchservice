"""
单点能量任务

集成 core/tasks/single_point.py 执行器
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.single_point import SinglePointExecutor


class SinglePointTask(BaseModelTask):
    """单点能量计算任务"""
    name = "workers.tasks.single_point.run"
    executor_class = SinglePointExecutor
    
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
        计算单点能量、力和应力
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 单点能参数
                - compute_forces: 是否计算力
                - compute_stress: 是否计算应力
                - per_atom_energies: 是否计算每原子能量
        
        Returns:
            单点能结果，包含:
            - energy_eV: 总能量 (eV)
            - energy_per_atom_eV: 每原子能量
            - forces: 力信息
            - stress: 应力信息
            - cell: 晶胞参数
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=SinglePointTask)
def run_single_point(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """单点能量任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
