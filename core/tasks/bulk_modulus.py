"""
体积模量任务执行器

通过 E-V 曲线拟合 Birch-Murnaghan 状态方程
"""
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import os

import ase
import ase.io
from ase.eos import EquationOfState
import numpy as np
import structlog

from .base import TaskExecutor, TaskContext

logger = structlog.get_logger(__name__)


class BulkModulusExecutor(TaskExecutor):
    """
    体积模量执行器
    
    计算流程：
    1. 等比例缩放晶胞体积
    2. 对每个体积进行结构优化
    3. 记录 E-V 数据点
    4. 拟合 Birch-Murnaghan 状态方程
    
    输出：
    - B0: 体积模量 (GPa)
    - V0: 平衡体积 (Å³)
    - E0: 平衡能量 (eV)
    - B': 体积模量对压力的导数
    """
    
    task_type = "bulk_modulus"
    
    default_parameters = {
        # 体积缩放参数
        "volume_strains": None,  # 自定义应变列表，如 [-0.06, -0.04, ...]
        "strain_range": 0.06,    # 应变范围 (±6%)
        "n_points": 7,           # 数据点数
        
        # 优化参数
        "optimize_atoms": True,  # 是否优化原子位置
        "opt_fmax": 0.01,
        "opt_steps": 200,
        
        # EOS 拟合参数
        "eos_type": "birchmurnaghan",  # birchmurnaghan, murnaghan, birch, vinet, etc.
    }
    
    def execute(self, atoms: ase.Atoms, context: TaskContext) -> Dict[str, Any]:
        """执行体积模量计算"""
        params = context.parameters
        
        original_cell = atoms.get_cell().copy()
        original_positions = atoms.get_positions().copy()
        original_volume = atoms.get_volume()
        
        logger.info(
            "bulk_modulus_start",
            n_atoms=len(atoms),
            original_volume=round(original_volume, 2),
            **context.log_context()
        )
        
        # 生成体积应变列表
        strains = self._get_volume_strains(params)
        
        # 计算 E-V 数据
        volumes = []
        energies = []
        strain_results = []
        
        for i, strain in enumerate(strains):
            # 缩放晶胞
            scale = (1 + strain) ** (1/3)  # 体积应变转为线性缩放
            
            test_atoms = atoms.copy()
            test_atoms.set_cell(original_cell * scale, scale_atoms=True)
            test_atoms.set_calculator(atoms.calc)
            
            volume = test_atoms.get_volume()
            
            # 可选：优化原子位置（固定晶胞）
            if params.get("optimize_atoms", True):
                energy, fmax = self._optimize_positions(test_atoms, params)
            else:
                energy = test_atoms.get_potential_energy()
                fmax = 0.0
            
            volumes.append(volume)
            energies.append(energy)
            
            strain_results.append({
                "strain": float(strain),
                "volume_A3": float(volume),
                "energy_eV": float(energy),
                "fmax": float(fmax),
            })
            
            logger.debug(
                "bulk_modulus_point",
                point=i+1,
                strain=round(strain, 3),
                volume=round(volume, 2),
                energy=round(energy, 4),
                **context.log_context()
            )
        
        # 拟合 EOS
        eos_type = params.get("eos_type", "birchmurnaghan")
        
        try:
            eos = EquationOfState(volumes, energies, eos=eos_type)
            v0, e0, B = eos.fit()
            
            # B0 单位转换：eV/Å³ → GPa
            B0_GPa = B / ase.units.kJ * 1e24
            
            # 计算 B' (体积模量对压力的导数)
            # 从 Birch-Murnaghan EOS: B' ≈ 4 (典型值)
            # 实际可以从拟合参数获取
            Bp = self._estimate_Bp(volumes, energies, v0, e0, B)
            
            fit_success = True
            fit_error = None
            
            logger.info(
                "bulk_modulus_fit_success",
                B0_GPa=round(B0_GPa, 2),
                V0=round(v0, 2),
                E0=round(e0, 4),
                **context.log_context()
            )
            
        except Exception as e:
            fit_success = False
            fit_error = str(e)
            v0 = None
            e0 = None
            B0_GPa = None
            Bp = None
            
            logger.error(
                "bulk_modulus_fit_failed",
                error=str(e),
                **context.log_context()
            )
        
        # 保存 EOS 图
        output_files = {}
        if context.work_dir and fit_success:
            try:
                eos_plot_file = str(context.work_dir / f"{context.structure_name or 'structure'}_eos.png")
                eos.plot(eos_plot_file)
                output_files["eos_plot"] = eos_plot_file
            except Exception as e:
                logger.warning(f"Failed to save EOS plot: {e}")
        
        # 保存数据
        if context.work_dir:
            data_file = context.work_dir / f"{context.structure_name or 'structure'}_ev_data.csv"
            self._save_ev_data(data_file, strain_results)
            output_files["ev_data"] = str(data_file)
        
        result = {
            "fit_success": fit_success,
            "B0_GPa": float(B0_GPa) if B0_GPa else None,
            "V0_A3": float(v0) if v0 else None,
            "E0_eV": float(e0) if e0 else None,
            "Bp": float(Bp) if Bp else None,
            "eos_type": eos_type,
            "n_points": len(volumes),
            "strain_results": strain_results,
            "fit_error": fit_error,
        }
        
        return {
            "result": result,
            "output_files": output_files,
        }
    
    def _get_volume_strains(self, params: dict) -> List[float]:
        """获取体积应变列表"""
        if params.get("volume_strains"):
            return params["volume_strains"]
        
        strain_range = params.get("strain_range", 0.06)
        n_points = params.get("n_points", 7)
        
        return np.linspace(-strain_range, strain_range, n_points).tolist()
    
    def _optimize_positions(self, atoms: ase.Atoms, params: dict) -> Tuple[float, float]:
        """优化原子位置（固定晶胞）"""
        from ase.optimize import BFGS
        from ase.constraints import FixedPlane
        
        fmax = params.get("opt_fmax", 0.01)
        steps = params.get("opt_steps", 200)
        
        # 不使用晶胞过滤器，直接优化原子位置
        opt = BFGS(atoms, logfile=None)
        opt.run(fmax=fmax, steps=steps)
        
        energy = atoms.get_potential_energy()
        forces = atoms.get_forces()
        final_fmax = float(np.sqrt((forces**2).sum(axis=1).max()))
        
        return energy, final_fmax
    
    def _estimate_Bp(
        self,
        volumes: List[float],
        energies: List[float],
        v0: float,
        e0: float,
        B: float
    ) -> Optional[float]:
        """估算 B' (体积模量的压力导数)"""
        try:
            # 使用 scipy 拟合 Birch-Murnaghan EOS 获取 B'
            from scipy.optimize import curve_fit
            
            def birch_murnaghan(V, E0, V0, B0, Bp):
                eta = (V0 / V) ** (2/3)
                E = E0 + 9 * V0 * B0 / 16 * (
                    (eta - 1) ** 3 * Bp + 
                    (eta - 1) ** 2 * (6 - 4 * eta)
                )
                return E
            
            # 初始猜测
            p0 = [e0, v0, B, 4.0]
            
            popt, _ = curve_fit(
                birch_murnaghan,
                volumes,
                energies,
                p0=p0,
                maxfev=10000
            )
            
            return float(popt[3])
            
        except Exception:
            return 4.0  # 返回典型值
    
    def _save_ev_data(self, filepath: Path, strain_results: List[Dict]) -> None:
        """保存 E-V 数据"""
        with open(filepath, 'w') as f:
            f.write("strain,volume_A3,energy_eV,fmax\n")
            for r in strain_results:
                f.write(f"{r['strain']},{r['volume_A3']},{r['energy_eV']},{r['fmax']}\n")
