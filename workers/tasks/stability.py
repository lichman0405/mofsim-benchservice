"""
稳定性任务

集成 core/tasks/stability.py 执行器
"""
from typing import Dict, Any

from workers.celery_app import celery_app
from workers.tasks.base import BaseModelTask
from core.tasks.stability import StabilityExecutor


class StabilityTask(BaseModelTask):
    """NPT MD 稳定性任务"""
    name = "workers.tasks.stability.run"
    executor_class = StabilityExecutor
    
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
        执行 NPT MD 稳定性测试
        
        Args:
            task_id: 任务 ID
            model_name: 模型名称
            structure_path: 结构文件路径
            parameters: 稳定性测试参数
                - temperature_K: 温度 (K)
                - run_optimization: 是否先优化
                - nvt_steps: NVT 步数
                - npt_steps: NPT 步数
                - npt_thermostat: NPT 恒温器类型
        
        Returns:
            稳定性结果，包含:
            - is_stable: 是否稳定
            - is_collapsed: 是否坍塌
            - volume_change_percent: 体积变化
            - stages: 各阶段详情
        """
        return self.run_with_executor(
            task_id=task_id,
            model_name=model_name,
            structure_path=structure_path,
            parameters=parameters,
            gpu_id=gpu_id,
            timeout=timeout,
        )


@celery_app.task(bind=True, base=StabilityTask)
def run_stability(
    self,
    task_id: str,
    model_name: str,
    structure_path: str,
    parameters: Dict[str, Any],
    gpu_id: int = None,
    timeout: int = None,
) -> Dict[str, Any]:
    """稳定性任务入口"""
    return self.run(task_id, model_name, structure_path, parameters, gpu_id, timeout)
