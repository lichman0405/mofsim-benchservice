"""
稳定性测试任务执行器

通过分子动力学模拟测试结构在有限温度下的稳定性
包括: 优化 → NVT → NPT 阶段
"""
from typing import Any, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
import os
import warnings

import ase
import ase.io
from ase.md.langevin import Langevin
from ase.md.npt import NPT
from ase.md.nptberendsen import NPTBerendsen
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext
from .optimization import OptimizationExecutor

logger = structlog.get_logger(__name__)


@dataclass
class StageResult:
    """MD 阶段结果"""
    name: str
    completed: bool = False
    steps_run: int = 0
    initial_volume: float = 0.0
    final_volume: float = 0.0
    volume_change_percent: float = 0.0
    avg_temperature: float = 0.0
    avg_pressure: Optional[float] = None
    collapsed: bool = False
    error: Optional[str] = None
    trajectory_file: Optional[str] = None


class StabilityExecutor(TaskExecutor):
    """
    稳定性测试执行器
    
    执行 MD 模拟来测试结构稳定性：
    1. 结构优化（可选）
    2. NVT 平衡（恒温）
    3. NPT 模拟（恒温恒压）
    
    输出：
    - 结构是否稳定（未坍塌）
    - 体积变化
    - 温度/压力历史
    - 最终结构
    """
    
    task_type = "stability"
    
    default_parameters = {
        # 是否先优化
        "run_optimization": True,
        "opt_fmax": 0.01,
        "opt_steps": 500,
        
        # NVT 参数
        "nvt_steps": 1000,
        "nvt_timestep_fs": 1.0,
        "nvt_friction": 0.02,  # Langevin friction
        
        # NPT 参数
        "npt_steps": 5000,
        "npt_timestep_fs": 1.0,
        "npt_thermostat": "Langevin",  # Langevin, Berendsen
        "npt_friction": 0.02,
        "npt_ttime_fs": 100.0,  # thermostat time
        "npt_ptime_fs": 1000.0,  # barostat time
        "npt_pressure_bar": 1.0,
        "npt_compressibility_GPa": 0.1,
        
        # 通用参数
        "temperature_K": 300.0,
        "log_interval": 10,  # 记录间隔
        
        # 稳定性判据
        "volume_collapse_threshold": 0.5,  # 体积缩小超过50%认为坍塌
        "max_volume_change": 0.3,  # 体积变化超过30%认为不稳定
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行稳定性测试"""
        params = context.parameters
        temperature = params.get("temperature_K", 300.0)
        
        logger.info(
            "stability_start",
            n_atoms=len(atoms),
            temperature=temperature,
            **context.log_context()
        )
        
        stages_results: List[Dict[str, Any]] = []
        current_atoms = atoms.copy()
        output_files = {}
        
        # 阶段1：结构优化
        if params.get("run_optimization", True):
            opt_result = self._run_optimization(current_atoms, context, params)
            stages_results.append(opt_result.to_dict())
            
            if opt_result.error:
                return self._build_error_result(
                    f"Optimization failed: {opt_result.error}",
                    stages_results
                )
            
            if opt_result.trajectory_file:
                output_files["opt_trajectory"] = opt_result.trajectory_file
        
        initial_volume = current_atoms.get_volume()
        
        # 初始化速度
        MaxwellBoltzmannDistribution(current_atoms, temperature_K=temperature)
        
        # 阶段2：NVT 平衡
        nvt_result = self._run_nvt(current_atoms, context, params)
        stages_results.append(nvt_result.to_dict())
        
        if nvt_result.error:
            return self._build_error_result(
                f"NVT failed: {nvt_result.error}",
                stages_results
            )
        
        if nvt_result.trajectory_file:
            output_files["nvt_trajectory"] = nvt_result.trajectory_file
        
        # 阶段3：NPT 模拟
        npt_result = self._run_npt(current_atoms, context, params)
        stages_results.append(npt_result.to_dict())
        
        if npt_result.error:
            return self._build_error_result(
                f"NPT failed: {npt_result.error}",
                stages_results
            )
        
        if npt_result.trajectory_file:
            output_files["npt_trajectory"] = npt_result.trajectory_file
        
        # 保存最终结构
        if context.work_dir:
            final_structure_file = context.work_dir / f"{context.structure_name or 'structure'}_final.cif"
            ase.io.write(str(final_structure_file), current_atoms)
            output_files["final_structure"] = str(final_structure_file)
        
        # 判断稳定性
        final_volume = current_atoms.get_volume()
        total_volume_change = (final_volume - initial_volume) / initial_volume
        
        volume_collapse_threshold = params.get("volume_collapse_threshold", 0.5)
        max_volume_change = params.get("max_volume_change", 0.3)
        
        is_collapsed = total_volume_change < -volume_collapse_threshold
        is_stable = not is_collapsed and abs(total_volume_change) < max_volume_change
        
        logger.info(
            "stability_completed",
            is_stable=is_stable,
            is_collapsed=is_collapsed,
            total_volume_change=round(total_volume_change * 100, 2),
            **context.log_context()
        )
        
        result = {
            "is_stable": is_stable,
            "is_collapsed": is_collapsed,
            "initial_volume_A3": float(initial_volume),
            "final_volume_A3": float(final_volume),
            "volume_change_percent": float(total_volume_change * 100),
            "temperature_K": temperature,
            "stages": stages_results,
        }
        
        return {
            "result": result,
            "output_files": output_files,
        }
    
    def _run_optimization(self, atoms: ase.Atoms, context: TaskContext, params: dict) -> StageResult:
        """运行优化阶段"""
        result = StageResult(name="optimization")
        
        try:
            from ase.optimize import BFGS
            from ase.filters import FrechetCellFilter
            
            initial_volume = atoms.get_volume()
            result.initial_volume = initial_volume
            
            filtered = FrechetCellFilter(atoms)
            opt = BFGS(filtered, logfile=None)
            
            fmax = params.get("opt_fmax", 0.01)
            steps = params.get("opt_steps", 500)
            
            converged = opt.run(fmax=fmax, steps=steps)
            
            result.completed = True
            result.steps_run = opt.nsteps
            result.final_volume = atoms.get_volume()
            result.volume_change_percent = (result.final_volume - initial_volume) / initial_volume * 100
            
            logger.info(
                "optimization_stage_completed",
                converged=converged,
                steps=opt.nsteps,
                **context.log_context()
            )
            
        except Exception as e:
            result.error = str(e)
            logger.error("optimization_stage_failed", error=str(e), **context.log_context())
        
        return result
    
    def _run_nvt(self, atoms: ase.Atoms, context: TaskContext, params: dict) -> StageResult:
        """运行 NVT 阶段 (Langevin)"""
        result = StageResult(name="nvt")
        
        try:
            temperature = params.get("temperature_K", 300.0)
            timestep = params.get("nvt_timestep_fs", 1.0) * units.fs
            friction = params.get("nvt_friction", 0.02)
            steps = params.get("npt_steps", 1000)
            log_interval = params.get("log_interval", 10)
            
            result.initial_volume = atoms.get_volume()
            
            # 设置轨迹文件
            traj_file = None
            if context.work_dir:
                traj_file = str(context.work_dir / f"{context.structure_name or 'structure'}_nvt.traj")
                result.trajectory_file = traj_file
            
            # 创建 Langevin 动力学
            dyn = Langevin(
                atoms,
                timestep=timestep,
                temperature_K=temperature,
                friction=friction,
                logfile=None,
                trajectory=traj_file,
            )
            
            # 记录温度历史
            temperatures = []
            
            def record_step():
                T = atoms.get_kinetic_energy() / (1.5 * units.kB * len(atoms))
                temperatures.append(float(T))
            
            dyn.attach(record_step, interval=log_interval)
            
            # 运行
            dyn.run(steps)
            
            result.completed = True
            result.steps_run = steps
            result.final_volume = atoms.get_volume()
            result.volume_change_percent = (result.final_volume - result.initial_volume) / result.initial_volume * 100
            result.avg_temperature = float(np.mean(temperatures)) if temperatures else temperature
            
            logger.info(
                "nvt_stage_completed",
                steps=steps,
                avg_temperature=round(result.avg_temperature, 1),
                **context.log_context()
            )
            
        except Exception as e:
            result.error = str(e)
            logger.error("nvt_stage_failed", error=str(e), **context.log_context())
        
        return result
    
    def _run_npt(self, atoms: ase.Atoms, context: TaskContext, params: dict) -> StageResult:
        """运行 NPT 阶段"""
        result = StageResult(name="npt")
        
        try:
            temperature = params.get("temperature_K", 300.0)
            timestep = params.get("npt_timestep_fs", 1.0) * units.fs
            steps = params.get("npt_steps", 5000)
            log_interval = params.get("log_interval", 10)
            thermostat = params.get("npt_thermostat", "Langevin")
            pressure = params.get("npt_pressure_bar", 1.0) * units.bar
            
            result.initial_volume = atoms.get_volume()
            
            # 设置轨迹文件
            traj_file = None
            if context.work_dir:
                traj_file = str(context.work_dir / f"{context.structure_name or 'structure'}_npt.traj")
                result.trajectory_file = traj_file
            
            # 选择 NPT 方法
            if thermostat == "Berendsen":
                ttime = params.get("npt_ttime_fs", 100.0) * units.fs
                ptime = params.get("npt_ptime_fs", 1000.0) * units.fs
                compressibility = params.get("npt_compressibility_GPa", 0.1) / units.GPa
                
                dyn = NPTBerendsen(
                    atoms,
                    timestep=timestep,
                    temperature_K=temperature,
                    taut=ttime,
                    pressure_au=pressure,
                    taup=ptime,
                    compressibility_au=compressibility,
                    logfile=None,
                    trajectory=traj_file,
                )
            else:
                # 使用 ASE 的 NPT
                friction = params.get("npt_friction", 0.02)
                ttime = params.get("npt_ttime_fs", 100.0) * units.fs
                ptime = params.get("npt_ptime_fs", 1000.0) * units.fs
                
                dyn = NPT(
                    atoms,
                    timestep=timestep,
                    temperature_K=temperature,
                    externalstress=pressure,
                    ttime=ttime,
                    pfactor=ptime * ptime * atoms.get_volume(),
                    logfile=None,
                    trajectory=traj_file,
                )
            
            # 记录历史
            temperatures = []
            volumes = []
            
            def record_step():
                T = atoms.get_kinetic_energy() / (1.5 * units.kB * len(atoms))
                V = atoms.get_volume()
                temperatures.append(float(T))
                volumes.append(float(V))
                
                # 检查是否坍塌
                if V < result.initial_volume * 0.5:
                    result.collapsed = True
            
            dyn.attach(record_step, interval=log_interval)
            
            # 运行
            dyn.run(steps)
            
            result.completed = True
            result.steps_run = steps
            result.final_volume = atoms.get_volume()
            result.volume_change_percent = (result.final_volume - result.initial_volume) / result.initial_volume * 100
            result.avg_temperature = float(np.mean(temperatures)) if temperatures else temperature
            
            logger.info(
                "npt_stage_completed",
                steps=steps,
                avg_temperature=round(result.avg_temperature, 1),
                volume_change=round(result.volume_change_percent, 2),
                collapsed=result.collapsed,
                **context.log_context()
            )
            
        except Exception as e:
            result.error = str(e)
            logger.error("npt_stage_failed", error=str(e), **context.log_context())
        
        return result
    
    def _build_error_result(self, error: str, stages: List[Dict]) -> Dict[str, Any]:
        """构建错误结果"""
        return {
            "result": {
                "is_stable": False,
                "is_collapsed": False,
                "error": error,
                "stages": stages,
            },
            "output_files": {},
        }


# Helper for StageResult
def _to_dict(stage_result: StageResult) -> Dict[str, Any]:
    return {
        "name": stage_result.name,
        "completed": stage_result.completed,
        "steps_run": stage_result.steps_run,
        "initial_volume_A3": stage_result.initial_volume,
        "final_volume_A3": stage_result.final_volume,
        "volume_change_percent": stage_result.volume_change_percent,
        "avg_temperature_K": stage_result.avg_temperature,
        "collapsed": stage_result.collapsed,
        "error": stage_result.error,
    }

StageResult.to_dict = lambda self: _to_dict(self)
