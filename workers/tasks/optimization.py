"""
优化任务

集成 core/tasks/optimization.py 执行器
参考文档: docs/architecture/async_task_design.md 3.1 节
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.optimization import OptimizationExecutor


class OptimizationTask(BaseModelTask):
    """结构优化任务"""
    name = "workers.tasks.optimization.run"
    executor_class = OptimizationExecutor
    
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
        执行结构优化
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 优化参数
                - fmax: 收敛力阈值 (eV/Å)
                - steps: 最大步数
                - optimizer: 优化器类型 (BFGS, LBFGS, FIRE)
                - filter: 晶胞过滤器 (FrechetCellFilter, ExpCellFilter, UnitCellFilter)
            gpu_id: GPU ID (可选)
            timeout: 超时时间 (可选)
        
        Returns:
            优化结果字典，包含:
            - converged: 是否收敛
            - final_energy_eV: 最终能量
            - final_fmax: 最终最大力
            - steps: 优化步数
            - volume_change_percent: 体积变化百分比
            - cell_parameters: 晶胞参数
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=OptimizationTask)
def run_optimization(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """优化任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
