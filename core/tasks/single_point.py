"""
单点能计算任务执行器

计算给定结构的能量、力和应力
"""
from typing import Any, Dict, List, Optional
from pathlib import Path

import ase
import ase.io
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext

logger = structlog.get_logger(__name__)


class SinglePointExecutor(TaskExecutor):
    """
    单点能执行器
    
    计算给定结构的：
    - 总能量 (eV)
    - 原子力 (eV/Å)
    - 应力张量 (GPa)
    """
    
    task_type = "single_point"
    
    default_parameters = {
        "compute_forces": True,
        "compute_stress": True,
        "per_atom_energies": False,  # 如果模型支持
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行单点能计算"""
        params = context.parameters
        
        logger.info(
            "single_point_start",
            n_atoms=len(atoms),
            formula=atoms.get_chemical_formula(),
            **context.log_context()
        )
        
        # 计算能量
        energy = atoms.get_potential_energy()
        
        result = {
            "energy_eV": float(energy),
            "energy_per_atom_eV": float(energy / len(atoms)),
            "n_atoms": len(atoms),
            "formula": atoms.get_chemical_formula(),
            "volume_A3": float(atoms.get_volume()),
        }
        
        # 计算力
        if params.get("compute_forces", True):
            forces = atoms.get_forces()
            fmax = float(np.sqrt((forces**2).sum(axis=1).max()))
            frms = float(np.sqrt((forces**2).mean()))
            
            result["forces"] = {
                "fmax_eV_A": fmax,
                "frms_eV_A": frms,
                "forces_array": forces.tolist(),
            }
            
            logger.info(
                "forces_computed",
                fmax=round(fmax, 6),
                frms=round(frms, 6),
                **context.log_context()
            )
        
        # 计算应力
        if params.get("compute_stress", True):
            try:
                stress = atoms.get_stress()  # Voigt notation: xx, yy, zz, yz, xz, xy
                
                # 转换为 GPa
                stress_GPa = stress / ase.units.GPa
                
                # 压力 (负迹/3)
                pressure_GPa = -stress_GPa[:3].mean()
                
                result["stress"] = {
                    "stress_voigt_GPa": stress_GPa.tolist(),
                    "pressure_GPa": float(pressure_GPa),
                    "stress_tensor_GPa": self._voigt_to_tensor(stress_GPa).tolist(),
                }
                
                logger.info(
                    "stress_computed",
                    pressure_GPa=round(pressure_GPa, 4),
                    **context.log_context()
                )
                
            except Exception as e:
                logger.warning(f"Stress calculation failed: {e}")
                result["stress"] = {"error": str(e)}
        
        # 每原子能量（如果支持）
        if params.get("per_atom_energies", False):
            try:
                # 某些模型支持 get_potential_energies()
                per_atom = atoms.get_potential_energies()
                result["per_atom_energies_eV"] = per_atom.tolist()
            except Exception:
                # 大多数模型不支持
                pass
        
        # 晶胞信息
        cell = atoms.get_cell()
        result["cell"] = {
            "a": float(cell.lengths()[0]),
            "b": float(cell.lengths()[1]),
            "c": float(cell.lengths()[2]),
            "alpha": float(cell.angles()[0]),
            "beta": float(cell.angles()[1]),
            "gamma": float(cell.angles()[2]),
            "vectors": cell.tolist(),
        }
        
        logger.info(
            "single_point_completed",
            energy_eV=round(energy, 4),
            **context.log_context()
        )
        
        return {
            "result": result,
            "output_files": {},
        }
    
    def _voigt_to_tensor(self, voigt: np.ndarray) -> np.ndarray:
        """将 Voigt 应力转换为 3x3 张量"""
        # voigt: [xx, yy, zz, yz, xz, xy]
        tensor = np.array([
            [voigt[0], voigt[5], voigt[4]],
            [voigt[5], voigt[1], voigt[3]],
            [voigt[4], voigt[3], voigt[2]],
        ])
        return tensor
