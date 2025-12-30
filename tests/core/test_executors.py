"""
执行器测试

测试各类任务执行器的基本功能。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from core.tasks.base import TaskExecutor, TaskContext, TaskResult


# ===== TaskContext 测试 =====

class TestTaskContext:
    """TaskContext 数据类测试"""
    
    def test_create_context(self):
        """创建上下文"""
        context = TaskContext(
            task_id="task-123",
            task_type="optimization",
            model_name="mace_mof_large",
            structure_path="/path/to/structure.cif",
            parameters={"fmax": 0.05},
            output_dir="/path/to/output",
        )
        
        assert context.task_id == "task-123"
        assert context.task_type == "optimization"
        assert context.model_name == "mace_mof_large"
        assert context.parameters["fmax"] == 0.05
    
    def test_context_with_gpu(self):
        """带 GPU 的上下文"""
        context = TaskContext(
            task_id="task-123",
            task_type="optimization",
            model_name="mace",
            structure_path="/path/to/structure.cif",
            parameters={},
            output_dir="/output",
            gpu_id=0,
        )
        
        assert context.gpu_id == 0


# ===== TaskResult 测试 =====

class TestTaskResult:
    """TaskResult 数据类测试"""
    
    def test_success_result(self):
        """成功结果"""
        result = TaskResult(
            success=True,
            task_id="task-123",
            task_type="optimization",
            result_data={
                "initial_energy": -100.0,
                "final_energy": -105.0,
                "converged": True,
            },
            execution_time=10.5,
        )
        
        assert result.success is True
        assert result.result_data["final_energy"] == -105.0
        assert result.execution_time == 10.5
        assert result.error_message is None
    
    def test_failed_result(self):
        """失败结果"""
        result = TaskResult(
            success=False,
            task_id="task-123",
            task_type="optimization",
            result_data={},
            error_message="Calculation diverged",
        )
        
        assert result.success is False
        assert result.error_message == "Calculation diverged"


# ===== TaskExecutor 基类测试 =====

class TestTaskExecutorBase:
    """TaskExecutor 基类测试"""
    
    def test_executor_is_abstract(self):
        """执行器是抽象类"""
        # TaskExecutor 应该不能直接实例化
        with pytest.raises(TypeError):
            TaskExecutor()
    
    def test_concrete_executor(self):
        """具体执行器实现"""
        class ConcreteExecutor(TaskExecutor):
            def execute(self, context: TaskContext) -> TaskResult:
                return TaskResult(
                    success=True,
                    task_id=context.task_id,
                    task_type=context.task_type,
                    result_data={"test": "value"},
                )
            
            def validate_parameters(self, parameters: dict) -> dict:
                return parameters
        
        executor = ConcreteExecutor()
        context = TaskContext(
            task_id="test-123",
            task_type="test",
            model_name="test_model",
            structure_path="/path/to/test.cif",
            parameters={},
            output_dir="/output",
        )
        
        result = executor.execute(context)
        assert result.success is True
        assert result.result_data["test"] == "value"


# ===== 优化执行器测试 =====

class TestOptimizationExecutor:
    """优化执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.optimization import OptimizationExecutor
        assert OptimizationExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.optimization import OptimizationExecutor
        
        executor = OptimizationExecutor()
        params = executor.validate_parameters({})
        
        assert "fmax" in params
        assert "max_steps" in params
        assert "optimizer" in params
    
    def test_custom_parameters(self):
        """自定义参数"""
        from core.tasks.optimization import OptimizationExecutor
        
        executor = OptimizationExecutor()
        params = executor.validate_parameters({
            "fmax": 0.01,
            "max_steps": 1000,
            "optimizer": "LBFGS",
        })
        
        assert params["fmax"] == 0.01
        assert params["max_steps"] == 1000
        assert params["optimizer"] == "LBFGS"


# ===== 稳定性执行器测试 =====

class TestStabilityExecutor:
    """稳定性执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.stability import StabilityExecutor
        assert StabilityExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.stability import StabilityExecutor
        
        executor = StabilityExecutor()
        params = executor.validate_parameters({})
        
        assert "temperature" in params
        assert "pressure" in params
        assert "steps" in params


# ===== 体积模量执行器测试 =====

class TestBulkModulusExecutor:
    """体积模量执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.bulk_modulus import BulkModulusExecutor
        assert BulkModulusExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.bulk_modulus import BulkModulusExecutor
        
        executor = BulkModulusExecutor()
        params = executor.validate_parameters({})
        
        assert "strain_range" in params
        assert "n_points" in params


# ===== 热容执行器测试 =====

class TestHeatCapacityExecutor:
    """热容执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.heat_capacity import HeatCapacityExecutor
        assert HeatCapacityExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.heat_capacity import HeatCapacityExecutor
        
        executor = HeatCapacityExecutor()
        params = executor.validate_parameters({})
        
        assert "temperature" in params
        assert "supercell" in params


# ===== 相互作用能执行器测试 =====

class TestInteractionEnergyExecutor:
    """相互作用能执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.interaction_energy import InteractionEnergyExecutor
        assert InteractionEnergyExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.interaction_energy import InteractionEnergyExecutor
        
        executor = InteractionEnergyExecutor()
        params = executor.validate_parameters({})
        
        assert "gas_molecule" in params


# ===== 单点能执行器测试 =====

class TestSinglePointExecutor:
    """单点能执行器测试"""
    
    def test_import(self):
        """导入成功"""
        from core.tasks.single_point import SinglePointExecutor
        assert SinglePointExecutor is not None
    
    def test_default_parameters(self):
        """默认参数"""
        from core.tasks.single_point import SinglePointExecutor
        
        executor = SinglePointExecutor()
        params = executor.validate_parameters({})
        
        assert "calculate_forces" in params
        assert "calculate_stress" in params
