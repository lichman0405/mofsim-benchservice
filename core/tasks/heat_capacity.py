"""
热容任务执行器

通过声子计算获取恒容热容 (Cv)
"""
from typing import Any, Dict, List, Optional
from pathlib import Path
import os

import ase
import ase.io
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext

logger = structlog.get_logger(__name__)


class HeatCapacityExecutor(TaskExecutor):
    """
    热容执行器
    
    计算流程：
    1. 结构优化（可选）
    2. 声子计算（有限位移法）
    3. 计算热力学性质
    
    输出：
    - Cv: 恒容热容 (J/mol/K 或 kB/atom)
    - 自由能、熵等热力学量
    - 声子态密度 (可选)
    """
    
    task_type = "heat_capacity"
    
    default_parameters = {
        # 优化参数
        "run_optimization": True,
        "opt_fmax": 0.001,  # 热容计算需要更严格的收敛
        "opt_steps": 1000,
        
        # 声子计算参数
        "supercell": [2, 2, 2],  # 超胞大小
        "displacement": 0.01,    # 位移大小 (Å)
        "symmetrize": True,      # 使用对称性
        
        # 温度参数
        "temperature": 300.0,    # 目标温度 (K)
        "temperature_range": None,  # 温度范围 [T_min, T_max, n_points]
        
        # 输出控制
        "save_phonopy_yaml": True,
        "calculate_dos": True,
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行热容计算"""
        params = context.parameters
        
        logger.info(
            "heat_capacity_start",
            n_atoms=len(atoms),
            supercell=params.get("supercell", [2, 2, 2]),
            **context.log_context()
        )
        
        output_files = {}
        
        # 阶段1：结构优化
        if params.get("run_optimization", True):
            atoms = self._optimize_structure(atoms, params, context)
        
        # 检查是否有 phonopy
        try:
            from phonopy import Phonopy
            from phonopy.structure.atoms import PhonopyAtoms
        except ImportError:
            return {
                "result": {
                    "error": "phonopy not installed. Please install: pip install phonopy",
                    "Cv_kB_per_atom": None,
                },
                "output_files": {},
            }
        
        # 转换为 phonopy atoms
        phonopy_atoms = PhonopyAtoms(
            symbols=atoms.get_chemical_symbols(),
            scaled_positions=atoms.get_scaled_positions(),
            cell=atoms.get_cell()
        )
        
        # 创建 phonopy 对象
        supercell = params.get("supercell", [2, 2, 2])
        
        phonon = Phonopy(
            phonopy_atoms,
            supercell_matrix=np.diag(supercell),
            primitive_matrix="auto",
        )
        
        # 生成位移
        displacement = params.get("displacement", 0.01)
        phonon.generate_displacements(distance=displacement)
        
        supercells = phonon.supercells_with_displacements
        
        logger.info(
            "phonon_displacements",
            n_displacements=len(supercells),
            supercell_size=supercell,
            **context.log_context()
        )
        
        # 计算力
        forces = []
        for i, scell in enumerate(supercells):
            # 转换为 ASE atoms
            sc_atoms = ase.Atoms(
                symbols=scell.symbols,
                positions=scell.positions,
                cell=scell.cell,
                pbc=True
            )
            sc_atoms.set_calculator(atoms.calc)
            
            try:
                f = sc_atoms.get_forces()
                forces.append(f)
                
                if (i + 1) % 10 == 0:
                    logger.debug(
                        "force_calculation_progress",
                        completed=i+1,
                        total=len(supercells),
                        **context.log_context()
                    )
            except Exception as e:
                logger.error(f"Force calculation failed for displacement {i}: {e}")
                forces.append(np.zeros_like(sc_atoms.positions))
        
        # 设置力
        phonon.forces = forces
        
        # 产生力常数
        phonon.produce_force_constants()
        
        # 计算热力学性质
        temperature = params.get("temperature", 300.0)
        temp_range = params.get("temperature_range")
        
        if temp_range:
            T_min, T_max, n_points = temp_range
            temperatures = np.linspace(T_min, T_max, n_points)
        else:
            temperatures = np.array([temperature])
        
        # 网格采样
        phonon.run_mesh([20, 20, 20])
        phonon.run_thermal_properties(temperatures=temperatures)
        
        # 获取热力学性质
        tp = phonon.get_thermal_properties_dict()
        
        # 提取目标温度的值
        if len(temperatures) == 1:
            Cv = float(tp["heat_capacity"][0])
            entropy = float(tp["entropy"][0])
            free_energy = float(tp["free_energy"][0])
            thermal_results = {
                "temperature_K": temperature,
                "Cv_J_mol_K": Cv,
                "entropy_J_mol_K": entropy,
                "free_energy_kJ_mol": free_energy,
            }
        else:
            thermal_results = {
                "temperatures_K": temperatures.tolist(),
                "Cv_J_mol_K": tp["heat_capacity"].tolist(),
                "entropy_J_mol_K": tp["entropy"].tolist(),
                "free_energy_kJ_mol": tp["free_energy"].tolist(),
            }
            # 目标温度
            idx = np.argmin(np.abs(temperatures - temperature))
            Cv = float(tp["heat_capacity"][idx])
        
        # 转换为 kB/atom
        from ase import units
        n_atoms = len(atoms)
        Cv_kB_per_atom = Cv / (units.kB * units.mol / units.J) / n_atoms
        
        logger.info(
            "heat_capacity_completed",
            temperature=temperature,
            Cv_kB_per_atom=round(Cv_kB_per_atom, 4),
            **context.log_context()
        )
        
        # 保存输出
        if context.work_dir:
            if params.get("save_phonopy_yaml", True):
                yaml_file = str(context.work_dir / "phonopy.yaml")
                phonon.save(yaml_file)
                output_files["phonopy_yaml"] = yaml_file
            
            # 保存力常数
            fc_file = str(context.work_dir / "FORCE_CONSTANTS")
            phonon.save_force_constants(fc_file)
            output_files["force_constants"] = fc_file
            
            # 计算和保存 DOS
            if params.get("calculate_dos", True):
                try:
                    phonon.run_total_dos()
                    dos_file = str(context.work_dir / "total_dos.dat")
                    phonon.write_total_dos(filename=dos_file)
                    output_files["dos"] = dos_file
                except Exception as e:
                    logger.warning(f"Failed to calculate DOS: {e}")
        
        result = {
            "Cv_kB_per_atom": float(Cv_kB_per_atom),
            "Cv_J_mol_K": float(Cv),
            "n_atoms": n_atoms,
            "supercell": supercell,
            "n_displacements": len(supercells),
            "thermal_properties": thermal_results,
        }
        
        return {
            "result": result,
            "output_files": output_files,
        }
    
    def _optimize_structure(self, atoms: ase.Atoms, params: dict, context: TaskContext) -> ase.Atoms:
        """优化结构"""
        from ase.optimize import BFGS
        from ase.filters import FrechetCellFilter
        
        logger.info("heat_capacity_optimization", **context.log_context())
        
        filtered = FrechetCellFilter(atoms)
        opt = BFGS(filtered, logfile=None)
        
        fmax = params.get("opt_fmax", 0.001)
        steps = params.get("opt_steps", 1000)
        
        opt.run(fmax=fmax, steps=steps)
        
        return atoms
