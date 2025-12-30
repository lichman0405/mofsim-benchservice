# 用户使用指南

## 一、概述

**MOFSimBench** 是一个用于评估**通用机器学习原子间势（Universal Machine Learning Interatomic Potentials, uMLIPs）**在**金属有机框架（Metal-Organic Frameworks, MOFs）**分子建模中性能的基准测试套件。

该项目的核心目标是：
1. **系统性评估多种主流 uMLIP 模型**：对比不同模型在 MOF 材料模拟中的准确性和可靠性
2. **提供标准化的测试任务**：包括结构优化、模拟稳定性、体积模量、热容等物理性质的计算
3. **促进 MOF 模拟领域的发展**：为研究人员选择合适的势函数提供参考依据

**论文引用**：
> MOFSimBench: evaluating universal machine learning interatomic potentials in metal-organic framework molecular modeling  
> npj Computational Materials, 2025  
> DOI: [10.1038/s41524-025-01872-3](https://doi.org/10.1038/s41524-025-01872-3)

---

## 二、核心功能

### 2.1 结构优化任务 (Optimization)

- **目的**：评估模型对 MOF 结构的几何优化能力
- **方法**：使用 BFGS 优化器配合 FrechetCellFilter 进行全松弛
- **评估指标**：
  - RMSD（与实验结构/DFT 结构对比）
  - 晶胞参数变化
  - 体积变化
  - 能量收敛

### 2.2 模拟稳定性任务 (Stability)

- **目的**：测试模型在长时间分子动力学（MD）模拟中的稳定性
- **方法**：
  1. 先进行结构优化
  2. NVT 系综平衡
  3. NPT 系综生产运行（支持 Langevin、Berendsen、MTK-NPT 等热浴）
- **评估指标**：
  - 金属配位数变化
  - 结构 RMSD 演化
  - 体积稳定性
  - 温度/压力控制能力

### 2.3 体积模量计算 (Bulk Modulus)

- **目的**：计算 MOF 材料的力学性质
- **方法**：通过体积-能量曲线拟合（Birch-Murnaghan 状态方程）
- **评估指标**：
  - 体积模量 $B_0$（与 DFT 参考值对比）
  - 平衡体积 $V_0$
  - 能量-体积关系曲线

### 2.4 热容计算 (Heat Capacity)

- **目的**：评估模型预测热力学性质的能力
- **方法**：基于声子计算（phonopy）获取热容
- **评估指标**：
  - 300K 下的等容热容 $C_v$
  - 与 DFT 计算结果对比
  - 熵和自由能

### 2.5 QMOF 能量对比任务

- **目的**：验证模型能量预测的准确性
- **方法**：计算 QMOF 数据库中结构的能量，与 DFT 参考值对比
- **要求**：需下载 QMOF 数据库

### 2.6 相互作用能任务 (Interaction Energy)

- **目的**：评估模型对主客体相互作用的描述能力
- **方法**：计算 MOF 与气体分子（CO₂、H₂O）的相互作用能
- **数据来源**：GoldDAC 数据集
- **评估指标**：
  - 相互作用能 MAE
  - 力场 MAE

---

## 三、使用方式

### 3.1 快速开始

```bash
# 1. 创建 Conda 环境
conda create -n mb_mace python=3.11
conda activate mb_mace

# 2. 安装项目
pip install .

# 3. 安装模型依赖（以 MACE 为例）
pip install mace-torch torch-dftd

# 4. 安装 ASE 开发版（支持 MTKNPT 驱动）
pip install git+https://gitlab.com/ase/ase.git

# 5. 测试模型
python mof_benchmark/setup/test_calculator.py mace_prod
```

### 3.2 运行基准测试

#### 运行所有任务（SLURM 环境）
```bash
./mof_benchmark/experiments/scripts/run_all.sh mace_prod
```

#### 运行单个任务
```bash
# 结构优化
cd mof_benchmark/experiments/scripts/optimization
python run_optimization.py --model mace_prod --structure ./mof.cif

# 稳定性测试
cd mof_benchmark/experiments/scripts/stability
python run_stability.py --model mace_prod --structure ./mof.cif

# 体积模量
cd mof_benchmark/experiments/scripts/bulk_modulus
python run_bulk_modulus.py --model mace_prod --structure ./mof.cif
```

### 3.3 结果分析（Streamlit 界面）

```bash
# 运行分析脚本
cd mof_benchmark/analysis
./run_analysis.sh

# 启动 Streamlit 可视化界面
streamlit run Overview.py
```

访问 `http://localhost:8501` 查看：
- 各任务的汇总结果
- 模型性能对比图表
- 详细的结构分析

---

## 四、模型选择指南

详细的模型列表请参考 [模型目录](model_catalog.md)。

| 模型系列 | 配置键示例 | 优势 | 适用场景 |
|---------|-----------|------|--------|
| **MACE** | `mace_prod` | 精度极高，支持多种元素 | 最终性质计算、高精度优化 |
| **ORB** | `orb_prod` | 速度快，泛化能力强 | 大规模筛选、初步优化 |
| **OMAT24** | `omat24_prod` | 针对无机材料优化 | 氧化物、金属骨架 |
| **SevenNet** | `sevennet_prod` | 稳定性好 | 长时间 MD 模拟 |
| **GRACE** | `grace_prod` | 良好外推性能 | 新型材料探索 |
| **MatterSim** | `mattersim_prod` | 微软开发，通用性强 | 多场景应用 |

---

## 五、数据来源

项目使用的 MOF 结构来自多个知名数据库：

| 数据库 | 说明 | 用途 |
|--------|------|------|
| **CoRE-MOF** | 计算就绪实验 MOF 数据库 | 主要测试集 |
| **QMOF** | 量子力学优化的 MOF 数据库 | 能量对比验证 |
| **IZA** | 国际沸石协会结构数据库 | 沸石结构测试 |
| **Curated-COF** | 精选共价有机框架数据库 | COF 结构测试 |
| **GoldDAC** | 用于相互作用能测试的基准数据 | 吸附能验证 |

---

## 六、最佳实践

### 6.1 结构准备

- 确保 CIF 文件包含完整的对称性信息。
- 检查是否有重叠原子或缺失的氢原子。
- 对于大孔 MOF，建议使用超胞进行稳定性分析。

### 6.2 计算流程

1. **初步优化**：使用 `orb_prod` 进行快速几何优化。
2. **高精度优化**：使用 `mace_prod` 进行最终优化。
3. **性质计算**：基于优化后的结构计算体积模量或热容。

### 6.3 环境配置建议

- 为每个模型系列创建独立的 Conda 环境，避免依赖冲突。
- 推荐使用 Python 3.11。
- 安装 ASE 开发版以支持 MTKNPT 驱动。

---

## 七、常见问题

### 7.1 优化不收敛怎么办？

- 增加 `max_steps`。
- 尝试不同的 `optimizer`（如从 LBFGS 切换到 FIRE）。
- 检查初始结构是否合理。

### 7.2 模型加载失败？

- 确认已安装对应的模型包（如 `mace-torch`、`orb-models`）。
- 检查模型权重文件路径是否正确。
- 运行 `python mof_benchmark/setup/test_calculator.py <model_key>` 进行诊断。

### 7.3 GPU 显存溢出 (OOM)？

- 减小超胞尺寸。
- 尝试使用显存效率更高的模型（如 `orb_prod`）。
- 检查 `nvidia-smi` 确认无其他进程占用显存。

---

## 八、获取支持

- **论文**：[npj Computational Materials](https://doi.org/10.1038/s41524-025-01872-3)
- **代码仓库**：[GitHub - AI4ChemS/mofsim-bench](https://github.com/AI4ChemS/mofsim-bench)
- **问题反馈**：[GitHub Issues](https://github.com/AI4ChemS/mofsim-bench/issues)

---

*文档版本：v1.1*  
*更新日期：2025年12月30日*
