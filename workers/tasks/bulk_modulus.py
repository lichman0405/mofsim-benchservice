"""
体积模量任务

集成 core/tasks/bulk_modulus.py 执行器
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.bulk_modulus import BulkModulusExecutor


class BulkModulusTask(BaseModelTask):
    """体积模量计算任务"""
    name = "workers.tasks.bulk_modulus.run"
    executor_class = BulkModulusExecutor
    
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
        计算体积模量
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 体积模量参数
                - strain_range: 应变范围 (默认 0.06)
                - n_points: 采样点数 (默认 7)
                - eos_type: 状态方程类型 (默认 birchmurnaghan)
                - optimize_atoms: 是否优化原子位置
        
        Returns:
            体积模量结果，包含:
            - B0_GPa: 体积模量 (GPa)
            - V0_A3: 平衡体积 (Å³)
            - E0_eV: 平衡能量 (eV)
            - Bp: 体积模量的压力导数
            - strain_results: 各应变点数据
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=BulkModulusTask)
def run_bulk_modulus(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """体积模量任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
