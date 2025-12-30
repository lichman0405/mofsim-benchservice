# 任务类型参考

## 一、概述

本文档详细说明 MOFSimBench 支持的所有任务类型及其参数。

---

## 二、几何优化 (Optimization)

### 2.1 说明
通过调整原子位置和晶胞参数，寻找势能面上的局部极小值。

### 2.2 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `fmax` | float | 0.001 | 力收敛阈值 (eV/Å) |
| `max_steps` | int | 500 | 最大优化步数 |
| `optimizer` | string | "LBFGS" | 优化器：LBFGS, BFGS, FIRE, MDMin |
| `relax_cell` | bool | true | 是否允许晶胞形变 |
| `mask` | list | null | 固定特定原子的掩码 |
| `trajectory_interval` | int | 10 | 轨迹保存频率 |

### 2.3 结果
- `final_energy_eV`: 优化后的总能量
- `final_structure`: 优化后的结构文件
- `converged`: 是否达到收敛标准
- `steps`: 实际执行步数
- `energy_history`: 能量随步数的变化

---

## 三、稳定性分析 (Stability)

### 3.1 说明
通过分子动力学（MD）模拟，观察结构在特定温度下的波动情况。

### 3.2 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `temperature_k` | float | 300 | 模拟温度 (K) |
| `timestep_fs` | float | 1.0 | 时间步长 (fs) |
| `total_steps` | int | 1000 | 总模拟步数 |
| `equilibration_steps` | int | 100 | 平衡步数 |
| `ensemble` | string | "NVT" | 系综：NVT, NPT |
| `supercell` | list | [1, 1, 1] | 超胞尺寸 |

### 3.3 结果
- `stable`: 是否保持结构稳定
- `max_displacement_A`: 原子最大位移
- `rdf`: 径向分布函数数据
- `energy_drift_eV`: 能量漂移率
- `trajectory`: MD 轨迹文件

---

## 四、体积模量 (Bulk Modulus)

### 4.1 说明
计算材料抵抗均匀压缩的能力。通过拟合状态方程（EOS）获得。

### 4.2 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strain_range` | float | 0.05 | 应变范围 (±5%) |
| `num_points` | int | 7 | 采样点数 |
| `fitting_method` | string | "birch_murnaghan" | 拟合方程：birch_murnaghan, murnaghan, vinet |

### 4.3 结果
- `bulk_modulus_GPa`: 体积模量 (GPa)
- `equilibrium_volume_A3`: 平衡体积 (Å³)
- `pressure_derivative`: 模量对压力的导数 B'
- `eos_plot`: 能量-体积拟合曲线

---

## 五、热容 (Heat Capacity)

### 5.1 说明
计算定容热容 $C_v$ 随温度的变化。基于声子谱或 MD 能量波动。

### 5.2 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `temperature_range` | list | [100, 500] | 温度范围 [起始, 结束] |
| `temperature_step` | float | 50 | 温度步长 |
| `method` | string | "phonon" | 计算方法：phonon, md_fluctuation |
| `supercell` | list | [2, 2, 2] | 超胞尺寸 |

### 5.3 结果
- `temperatures`: 温度列表
- `heat_capacities`: 对应热容值 (J/mol·K)
- `cv_plot`: 热容-温度曲线

---

## 六、相互作用能 (Interaction Energy)

### 6.1 说明
评估模型对主客体相互作用的描述能力。计算 MOF 与气体分子的相互作用能。

### 6.2 数据来源
- **GoldDAC 数据集**：包含 CO₂、H₂O 等分子在 MOF 中的吸附构型和参考能量。

### 6.3 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `adsorbate` | string | "CO2" | 吸附质：CO2, H2O |
| `reference_data` | string | - | GoldDAC 参考数据路径 |

### 6.4 结果
- `interaction_energy_eV`: 相互作用能 (eV)
- `mae_vs_reference`: 与参考值的 MAE
- `force_mae`: 力场 MAE

---

## 七、QMOF 能量对比 (QMOF Energy)

### 7.1 说明
验证模型能量预测的准确性。计算 QMOF 数据库中结构的能量，与 DFT 参考值对比。

### 7.2 数据来源
- **QMOF 数据库**：量子力学优化的 MOF 结构数据库，需手动下载。

### 7.3 参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `qmof_path` | string | - | QMOF 数据库路径 |
| `subset` | string | "all" | 测试子集：all, small, medium |

### 7.4 结果
- `predicted_energies`: 模型预测能量列表
- `reference_energies`: DFT 参考能量列表
- `mae_eV_per_atom`: 每原子能量 MAE (eV/atom)
- `correlation_plot`: 相关性图

---

## 八、脚本位置参考

各任务的运行脚本位于 `mof_benchmark/experiments/scripts/` 目录下：

```
scripts/
├── optimization/      # 结构优化
├── stability/         # 稳定性分析
├── bulk_modulus/      # 体积模量
├── heat_capacity/     # 热容计算
├── interaction_energy/ # 相互作用能
├── qmof_energies/     # QMOF 能量对比
└── run_all.sh         # 批量运行所有任务
```

---

*文档版本：v1.1*  
*更新日期：2025年12月30日*
