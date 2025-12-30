"""
相互作用能任务执行器

计算 MOF 与气体分子之间的相互作用能
"""
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import os

import ase
import ase.io
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext

logger = structlog.get_logger(__name__)


# 常见气体分子
GAS_MOLECULES = {
    "H2": {
        "symbols": ["H", "H"],
        "positions": [[0, 0, 0], [0, 0, 0.74]],
    },
    "CO2": {
        "symbols": ["C", "O", "O"],
        "positions": [[0, 0, 0], [0, 0, 1.16], [0, 0, -1.16]],
    },
    "CH4": {
        "symbols": ["C", "H", "H", "H", "H"],
        "positions": [
            [0, 0, 0],
            [0.629, 0.629, 0.629],
            [-0.629, -0.629, 0.629],
            [-0.629, 0.629, -0.629],
            [0.629, -0.629, -0.629],
        ],
    },
    "N2": {
        "symbols": ["N", "N"],
        "positions": [[0, 0, 0], [0, 0, 1.10]],
    },
    "H2O": {
        "symbols": ["O", "H", "H"],
        "positions": [[0, 0, 0], [0.757, 0.587, 0], [-0.757, 0.587, 0]],
    },
    "CO": {
        "symbols": ["C", "O"],
        "positions": [[0, 0, 0], [0, 0, 1.13]],
    },
    "NH3": {
        "symbols": ["N", "H", "H", "H"],
        "positions": [
            [0, 0, 0],
            [0, 0.94, 0.38],
            [0.81, -0.47, 0.38],
            [-0.81, -0.47, 0.38],
        ],
    },
}


class InteractionEnergyExecutor(TaskExecutor):
    """
    相互作用能执行器
    
    计算 MOF 框架与气体分子之间的相互作用能：
    E_interaction = E_total - E_MOF - E_gas
    
    可以扫描多个位置取最低能量
    """
    
    task_type = "interaction_energy"
    
    default_parameters = {
        # 气体分子
        "gas_molecule": "CO2",       # 气体类型
        "custom_gas_atoms": None,    # 自定义气体结构（ASE atoms 格式）
        
        # 插入位置
        "positions": "grid",         # grid, random, specified
        "n_grid_points": [3, 3, 3],  # 网格点数
        "n_random_points": 20,       # 随机点数
        "specified_positions": None,  # 指定位置列表
        
        # 优化
        "optimize_gas": True,        # 优化气体位置
        "opt_fmax": 0.05,
        "opt_steps": 100,
        
        # 其他
        "min_distance": 2.0,         # 与框架最小距离 (Å)
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行相互作用能计算"""
        params = context.parameters
        
        mof_atoms = atoms.copy()
        
        logger.info(
            "interaction_energy_start",
            n_mof_atoms=len(mof_atoms),
            gas_molecule=params.get("gas_molecule", "CO2"),
            **context.log_context()
        )
        
        # 计算 MOF 能量
        E_mof = mof_atoms.get_potential_energy()
        
        # 获取气体分子
        gas_atoms = self._get_gas_molecule(params)
        
        # 计算气体分子能量（真空中）
        gas_isolated = gas_atoms.copy()
        gas_isolated.set_cell([20, 20, 20])
        gas_isolated.center()
        gas_isolated.set_pbc(True)
        gas_isolated.set_calculator(atoms.calc)
        E_gas = gas_isolated.get_potential_energy()
        
        # 生成插入位置
        positions = self._generate_positions(mof_atoms, params)
        
        logger.info(
            "scanning_positions",
            n_positions=len(positions),
            **context.log_context()
        )
        
        # 扫描每个位置
        results = []
        
        for i, pos in enumerate(positions):
            try:
                result = self._compute_at_position(
                    mof_atoms, gas_atoms, pos, E_mof, E_gas, params
                )
                results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.debug(
                        "position_scan_progress",
                        completed=i+1,
                        total=len(positions),
                        **context.log_context()
                    )
            except Exception as e:
                logger.warning(f"Position {i} failed: {e}")
                continue
        
        if not results:
            return {
                "result": {
                    "error": "All positions failed",
                    "E_interaction_eV": None,
                },
                "output_files": {},
            }
        
        # 找到最低能量
        best_result = min(results, key=lambda x: x["E_interaction_eV"])
        
        logger.info(
            "interaction_energy_completed",
            E_interaction_eV=round(best_result["E_interaction_eV"], 4),
            best_position=best_result["position"],
            **context.log_context()
        )
        
        # 保存最佳结构
        output_files = {}
        if context.work_dir and best_result.get("combined_atoms"):
            combined_file = context.work_dir / f"{context.structure_name or 'mof'}_with_gas.cif"
            ase.io.write(str(combined_file), best_result["combined_atoms"])
            output_files["combined_structure"] = str(combined_file)
            del best_result["combined_atoms"]  # 不包含在 JSON 中
        
        result = {
            "E_mof_eV": float(E_mof),
            "E_gas_eV": float(E_gas),
            "E_interaction_eV": float(best_result["E_interaction_eV"]),
            "best_position": best_result["position"],
            "gas_molecule": params.get("gas_molecule", "CO2"),
            "n_positions_scanned": len(results),
            "all_results": [
                {
                    "position": r["position"],
                    "E_interaction_eV": r["E_interaction_eV"],
                }
                for r in sorted(results, key=lambda x: x["E_interaction_eV"])[:10]
            ],
        }
        
        return {
            "result": result,
            "output_files": output_files,
        }
    
    def _get_gas_molecule(self, params: dict) -> ase.Atoms:
        """获取气体分子"""
        if params.get("custom_gas_atoms"):
            # 使用自定义结构
            custom = params["custom_gas_atoms"]
            return ase.Atoms(
                symbols=custom["symbols"],
                positions=custom["positions"]
            )
        
        gas_name = params.get("gas_molecule", "CO2")
        
        if gas_name not in GAS_MOLECULES:
            raise ValueError(f"Unknown gas molecule: {gas_name}. Available: {list(GAS_MOLECULES.keys())}")
        
        gas_data = GAS_MOLECULES[gas_name]
        return ase.Atoms(
            symbols=gas_data["symbols"],
            positions=gas_data["positions"]
        )
    
    def _generate_positions(self, mof_atoms: ase.Atoms, params: dict) -> List[np.ndarray]:
        """生成气体分子插入位置"""
        method = params.get("positions", "grid")
        cell = mof_atoms.get_cell()
        
        if method == "grid":
            n_grid = params.get("n_grid_points", [3, 3, 3])
            positions = []
            
            for i in range(n_grid[0]):
                for j in range(n_grid[1]):
                    for k in range(n_grid[2]):
                        frac = np.array([
                            (i + 0.5) / n_grid[0],
                            (j + 0.5) / n_grid[1],
                            (k + 0.5) / n_grid[2]
                        ])
                        cart = frac @ cell
                        positions.append(cart)
            
            return positions
        
        elif method == "random":
            n_random = params.get("n_random_points", 20)
            positions = []
            
            for _ in range(n_random):
                frac = np.random.random(3)
                cart = frac @ cell
                positions.append(cart)
            
            return positions
        
        elif method == "specified":
            return params.get("specified_positions", [])
        
        else:
            raise ValueError(f"Unknown position method: {method}")
    
    def _compute_at_position(
        self,
        mof_atoms: ase.Atoms,
        gas_atoms: ase.Atoms,
        position: np.ndarray,
        E_mof: float,
        E_gas: float,
        params: dict
    ) -> Dict[str, Any]:
        """在指定位置计算相互作用能"""
        # 复制并移动气体分子
        gas = gas_atoms.copy()
        gas_center = gas.get_center_of_mass()
        gas.translate(position - gas_center)
        
        # 检查最小距离
        min_dist = params.get("min_distance", 2.0)
        mof_positions = mof_atoms.get_positions()
        gas_positions = gas.get_positions()
        
        for gp in gas_positions:
            distances = np.linalg.norm(mof_positions - gp, axis=1)
            if distances.min() < min_dist:
                # 太近了，跳过
                return {
                    "position": position.tolist(),
                    "E_interaction_eV": float('inf'),
                    "skipped": True,
                }
        
        # 合并结构
        combined = mof_atoms.copy()
        combined.extend(gas)
        combined.set_calculator(mof_atoms.calc)
        
        # 可选优化
        if params.get("optimize_gas", True):
            from ase.optimize import BFGS
            from ase.constraints import FixAtoms
            
            # 固定 MOF 原子
            constraint = FixAtoms(indices=list(range(len(mof_atoms))))
            combined.set_constraint(constraint)
            
            opt = BFGS(combined, logfile=None)
            opt.run(
                fmax=params.get("opt_fmax", 0.05),
                steps=params.get("opt_steps", 100)
            )
        
        # 计算总能量
        E_total = combined.get_potential_energy()
        E_interaction = E_total - E_mof - E_gas
        
        # 获取优化后的气体位置
        final_gas_positions = combined.positions[len(mof_atoms):]
        final_position = final_gas_positions.mean(axis=0)
        
        return {
            "position": final_position.tolist(),
            "E_interaction_eV": float(E_interaction),
            "E_total_eV": float(E_total),
            "combined_atoms": combined,
        }
