"""
结构优化任务执行器

使用 BFGS 优化器配合 FrechetCellFilter 进行全松弛
"""
from typing import Any, Dict
from pathlib import Path
import os

import ase
import ase.io
from ase.optimize import BFGS, LBFGS, FIRE
from ase.filters import FrechetCellFilter, ExpCellFilter, UnitCellFilter
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext

logger = structlog.get_logger(__name__)


# 支持的优化器
OPTIMIZERS = {
    "BFGS": BFGS,
    "LBFGS": LBFGS,
    "FIRE": FIRE,
}

# 支持的过滤器
FILTERS = {
    "FrechetCellFilter": FrechetCellFilter,
    "ExpCellFilter": ExpCellFilter,
    "UnitCellFilter": UnitCellFilter,
    None: None,
}


class OptimizationExecutor(TaskExecutor):
    """
    结构优化执行器
    
    执行结构优化并返回：
    - 是否收敛
    - 最终能量和最大力
    - 体积变化
    - 优化后的结构文件
    """
    
    task_type = "optimization"
    
    default_parameters = {
        "fmax": 0.01,           # 收敛判据：最大力 (eV/Å)
        "steps": 500,           # 最大优化步数
        "optimizer": "BFGS",    # 优化器
        "filter": "FrechetCellFilter",  # 晶胞过滤器
        "filter_kwargs": {},    # 过滤器参数
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行结构优化"""
        params = context.parameters
        
        # 记录初始状态
        initial_atoms = atoms.copy()
        initial_energy = atoms.get_potential_energy()
        initial_volume = atoms.get_volume()
        initial_cell = atoms.get_cell()
        
        logger.info(
            "optimization_start",
            initial_energy=round(initial_energy, 4),
            initial_volume=round(initial_volume, 2),
            n_atoms=len(atoms),
            **context.log_context()
        )
        
        # 获取优化器和过滤器
        optimizer_name = params.get("optimizer", "BFGS")
        filter_name = params.get("filter", "FrechetCellFilter")
        
        if optimizer_name not in OPTIMIZERS:
            raise ValueError(f"Unsupported optimizer: {optimizer_name}")
        
        OptimizerClass = OPTIMIZERS[optimizer_name]
        FilterClass = FILTERS.get(filter_name)
        
        # 应用过滤器
        if FilterClass:
            filter_kwargs = params.get("filter_kwargs", {})
            filtered_atoms = FilterClass(atoms, **filter_kwargs)
            logger.info(f"Using filter: {filter_name}")
        else:
            filtered_atoms = atoms
        
        # 设置轨迹文件
        trajectory_file = None
        if context.work_dir:
            trajectory_file = str(context.work_dir / f"{context.structure_name or 'structure'}.traj")
        
        # 创建优化器
        optimizer_kwargs = {"logfile": "-"}  # 输出到 stdout
        if trajectory_file:
            optimizer_kwargs["trajectory"] = trajectory_file
        
        opt = OptimizerClass(filtered_atoms, **optimizer_kwargs)
        
        # 添加步骤回调
        steps_info = []
        
        def log_step():
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces()
            fmax = np.sqrt((forces**2).sum(axis=1).max())
            steps_info.append({
                "step": len(steps_info),
                "energy": float(energy),
                "fmax": float(fmax),
            })
            if len(steps_info) % 10 == 0:
                logger.info(
                    "optimization_step",
                    step=len(steps_info),
                    energy=round(energy, 4),
                    fmax=round(fmax, 6),
                    **context.log_context()
                )
        
        opt.attach(log_step, interval=1)
        
        # 执行优化
        fmax = params.get("fmax", 0.01)
        steps = params.get("steps", 500)
        
        converged = opt.run(fmax=fmax, steps=steps)
        
        # 获取最终状态
        final_energy = atoms.get_potential_energy()
        final_forces = atoms.get_forces()
        final_fmax = float(np.sqrt((final_forces**2).sum(axis=1).max()))
        final_volume = atoms.get_volume()
        final_cell = atoms.get_cell()
        
        # 计算变化
        volume_change_percent = (final_volume - initial_volume) / initial_volume * 100
        
        # 计算 RMSD
        if len(atoms) == len(initial_atoms):
            try:
                displacements = atoms.get_positions() - initial_atoms.get_positions()
                rmsd = float(np.sqrt((displacements**2).mean()))
            except:
                rmsd = None
        else:
            rmsd = None
        
        logger.info(
            "optimization_completed",
            converged=converged,
            final_energy=round(final_energy, 4),
            final_fmax=round(final_fmax, 6),
            steps=len(steps_info),
            volume_change_percent=round(volume_change_percent, 2),
            **context.log_context()
        )
        
        # 保存优化后的结构
        output_files = {}
        if context.work_dir:
            output_structure = context.work_dir / f"{context.structure_name or 'optimized'}.cif"
            ase.io.write(str(output_structure), atoms)
            output_files["optimized_structure"] = str(output_structure)
            
            if trajectory_file and os.path.exists(trajectory_file):
                output_files["trajectory"] = trajectory_file
        
        # 构建结果
        result = {
            "converged": converged,
            "final_energy_eV": float(final_energy),
            "final_fmax": final_fmax,
            "steps": len(steps_info),
            "initial_volume_A3": float(initial_volume),
            "final_volume_A3": float(final_volume),
            "volume_change_percent": float(volume_change_percent),
            "cell_parameters": {
                "a": float(final_cell.lengths()[0]),
                "b": float(final_cell.lengths()[1]),
                "c": float(final_cell.lengths()[2]),
                "alpha": float(final_cell.angles()[0]),
                "beta": float(final_cell.angles()[1]),
                "gamma": float(final_cell.angles()[2]),
            },
            "rmsd_from_initial": rmsd,
        }
        
        return {
            "result": result,
            "output_files": output_files,
        }
