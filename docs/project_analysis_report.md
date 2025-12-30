# MOFSimBench 项目分析报告

## 一、项目概述

### 1.1 项目目的

**MOFSimBench** 是一个用于评估**通用机器学习原子间势（Universal Machine Learning Interatomic Potentials, uMLIPs）**在**金属有机框架（Metal-Organic Frameworks, MOFs）**分子建模中性能的基准测试套件。

该项目的核心目标是：

1. **系统性评估多种主流 uMLIP 模型**：对比不同模型在 MOF 材料模拟中的准确性和可靠性
2. **提供标准化的测试任务**：包括结构优化、模拟稳定性、体积模量、热容等物理性质的计算
3. **促进 MOF 模拟领域的发展**：为研究人员选择合适的势函数提供参考依据
4. **可扩展性设计**：支持轻松添加新的模型和任务

该项目的论文已发表于 npj Computational Materials 期刊：[MOFSimBench: evaluating universal machine learning interatomic potentials in metal-organic framework molecular modeling](https://doi.org/10.1038/s41524-025-01872-3)

---

## 二、项目当前存在的问题

### 2.1 代码层面问题

1. **Python 版本兼容性过宽**：`pyproject.toml` 中指定 `requires-python = ">=3.7"`，但实际代码使用了 Python 3.10+ 的语法特性（如 `str | None` 类型注解），可能导致低版本 Python 运行时报错

2. **依赖管理不完善**：
   - 核心依赖中未包含所有必需的模型库（如 `orb-models`, `fairchem`, `sevenn` 等）
   - 需要手动安装 ASE 的开发版本以获取 `MTKNPT` 驱动

3. **硬编码路径问题**：部分代码中存在硬编码的模型路径，如：
   ```python
   model_file = settings.get(
       "model_file",
       "../../../mace4mof/mace4mof/model_management/2024-07-12-mace-128-L1_epoch-199.model",
   )
   ```

4. **错误处理不够健壮**：某些模型初始化时的错误处理不完整，缺少统一的异常处理机制

### 2.2 文档和配置问题

1. **文档目录为空**：`docs/` 目录当前没有任何文档内容
2. **部分外部数据需手动下载**：
   - QMOF 数据库需要手动下载并放置到指定目录
   - GoldDAC 测试文件需要手动配置

### 2.3 结构设计问题

1. **计算器配置冗余**：`calculators.yaml` 中存在大量相似配置，可考虑使用继承或模板机制
2. **日志系统简单**：仅使用基础的 `logging` 模块，缺少结构化日志和日志轮转

---

## 三、涉及的模型及下载方式

项目支持 **8 大类、20+ 个预训练模型**，以下是详细列表：

### 3.1 MACE 系列

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| MACE-MP-0b3-medium | `mace_prod_b3` | [官方 GitHub](https://github.com/ACEsuit/mace) 或 `mace_mp()` 自动下载 |
| MACE-128-L1 (2023) | `mace_prod_0a` | 需手动下载模型文件 |
| MACE-MOF-v1 | `mace_prod_mof` | 专为 MOF 训练的模型，需手动获取 |
| MACE-MPA-0-medium | `mace_prod` | [Hugging Face](https://huggingface.co/mace-ml) |
| MACE-OMAT-0-medium | `mace_prod_omat` | [Hugging Face](https://huggingface.co/mace-ml) |
| MACE-MatPES-r2scan | `mace_prod_matpes` | [Hugging Face](https://huggingface.co/mace-ml) |

**安装方式**：
```bash
pip install mace-torch
pip install torch-dftd  # D3 色散校正
```

### 3.2 ORB 系列

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| orb-mptraj-only-v2 | `orb_prod_mp` | 通过 `orb-models` 包自动下载 |
| orb-d3-v2 | `orb_prod` | 自动下载 |
| orb-v3-direct-20-omat | `orb3` | 自动下载 |
| orb-v3-conservative-inf-omat | `orb_prod_v3` | 自动下载 |
| orb-v3-conservative-inf-mpa | `orb_prod_v3_mp` | 自动下载 |

**安装方式**：
```bash
pip install orb-models
```
**官方仓库**：https://github.com/orbital-materials/orb-models

### 3.3 OMAT24 (FAIRChem/EquiformerV2)

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| eqV2_dens_86M_mp | `omat24_prod_mp` | 通过 `fairchem` 包加载 |
| eqV2_86M_omat_mp_salex | `omat24_prod` | 自动下载 |
| esen_30m_oam | `omat24_prod_esen` | 自动下载 |
| esen_30m_mptrj | `omat24_prod_esen_mp` | 自动下载 |

**安装方式**：
```bash
pip install fairchem-core
```
**官方仓库**：https://github.com/FAIR-Chem/fairchem

### 3.4 GRACE 系列

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| GRACE-2L-MP-r6 | `grace_prod` | 通过 `tensorpotential` 包加载 |
| GRACE-2L-OAM | `grace_prod_oam` | 自动下载 |
| GRACE-2L-OMAT | `grace_prod_omat` | 自动下载 |

**安装方式**：
```bash
pip install tensorpotential
```
**官方仓库**：https://github.com/ACEsuit/mace （GRACE 与 ACE 相关）

### 3.5 MatterSim

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| MatterSim-v1.0.0-5M | `mattersim_prod` | 通过 `mattersim` 包加载 |

**安装方式**：
```bash
pip install mattersim
```
**官方仓库**：https://github.com/microsoft/mattersim

### 3.6 SevenNet (7net)

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| 7net-0 | `sevennet_prod` | 通过 `sevenn` 包加载 |
| 7net-l3i5 | `sevennet_prod_l3i5` | 自动下载 |
| 7net-mf-ompa | `sevennet_prod_ompa` | 自动下载 |

**安装方式**：
```bash
pip install sevenn
```
**官方仓库**：https://github.com/MDIL-SNU/SevenNet

### 3.7 其他模型

| 模型类型 | 安装/下载方式 |
|---------|--------------|
| PosEGNN | 需要 `posegnn` 包，模型文件需手动配置 |
| MatGL | `pip install matgl`，通过 `matgl.load_model()` 加载 |

### 3.8 D3 色散校正

大多数模型需要配合 D3 色散校正使用：
```bash
pip install torch-dftd
```

---

## 四、项目能完成的任务

### 4.1 结构优化任务 (Optimization)

- **目的**：评估模型对 MOF 结构的几何优化能力
- **方法**：使用 BFGS 优化器配合 FrechetCellFilter 进行全松弛
- **评估指标**：
  - RMSD（与实验结构/DFT 结构对比）
  - 晶胞参数变化
  - 体积变化
  - 能量收敛

### 4.2 模拟稳定性任务 (Stability)

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

### 4.3 体积模量计算 (Bulk Modulus)

- **目的**：计算 MOF 材料的力学性质
- **方法**：通过体积-能量曲线拟合（Birch-Murnaghan 状态方程）
- **评估指标**：
  - 体积模量 B₀（与 DFT 参考值对比）
  - 平衡体积 V₀
  - 能量-体积关系曲线

### 4.4 热容计算 (Heat Capacity)

- **目的**：评估模型预测热力学性质的能力
- **方法**：基于声子计算（phonopy）获取热容
- **评估指标**：
  - 300K 下的等容热容 Cv
  - 与 DFT 计算结果对比
  - 熵和自由能

### 4.5 QMOF 能量对比任务

- **目的**：验证模型能量预测的准确性
- **方法**：计算 QMOF 数据库中结构的能量，与 DFT 参考值对比
- **要求**：需下载 QMOF 数据库

### 4.6 相互作用能任务 (Interaction Energy)

- **目的**：评估模型对主客体相互作用的描述能力
- **方法**：计算 MOF 与气体分子（CO₂、H₂O）的相互作用能
- **数据来源**：GoldDAC 数据集
- **评估指标**：
  - 相互作用能 MAE
  - 力场 MAE

---

## 五、项目架构

```
mofsim-bench/
├── mof_benchmark/
│   ├── setup/               # 计算器配置
│   │   ├── calculator.py    # 模型加载逻辑
│   │   ├── calculators.yaml # 模型配置文件
│   │   └── test_calculator.py
│   ├── experiments/         # 实验脚本
│   │   ├── scripts/         # 各任务的运行脚本
│   │   │   ├── optimization/
│   │   │   ├── stability/
│   │   │   ├── bulk_modulus/
│   │   │   ├── heat_capacity/
│   │   │   ├── interaction_energy/
│   │   │   └── qmof_energies/
│   │   └── structures/      # 测试结构
│   └── analysis/            # 结果分析
│       ├── optimization/
│       ├── stability/
│       ├── bulk_modulus/
│       ├── heat_capacity/
│       ├── interaction_energy/
│       ├── plot/            # 可视化
│       └── pages/           # Streamlit 页面
├── docs/                    # 文档
└── media/                   # 媒体资源
```

---

## 六、使用流程

### 6.1 快速开始

```bash
# 1. 创建环境
conda create -n mb_mace python=3.11
conda activate mb_mace

# 2. 安装项目
pip install .
pip install mace-torch torch-dftd

# 3. 安装 ASE 开发版（支持 MTKNPT）
pip install git+https://gitlab.com/ase/ase.git

# 4. 测试模型
python mof_benchmark/setup/test_calculator.py mace_prod

# 5. 运行所有任务（SLURM 环境）
./mof_benchmark/experiments/scripts/run_all.sh mace_prod
```

### 6.2 分析结果

```bash
# 运行分析脚本
cd mof_benchmark/analysis
./run_analysis.sh

# 启动 Streamlit 可视化
streamlit run Overview.py
```

---

## 七、数据来源

项目使用的 MOF 结构来自多个知名数据库：

- **CoRE-MOF**：计算就绪实验 MOF 数据库
- **QMOF**：量子力学优化的 MOF 数据库
- **IZA**：国际沸石协会结构数据库
- **Curated-COF**：精选共价有机框架数据库
- **GoldDAC**：用于相互作用能测试的基准数据

---

## 八、总结

MOFSimBench 是一个专业的 MOF 机器学习势函数评估平台，具有以下特点：

**优势**：
- 全面的任务覆盖（结构、动力学、热力学、力学性质）
- 支持多种主流 uMLIP 模型
- 模块化设计，易于扩展
- 提供 Streamlit 可视化界面
- 论文已发表，具有学术权威性

**待改进**：
- 完善文档
- 优化依赖管理
- 添加更多错误处理
- 支持更多模型类型

---

*报告生成日期：2025年12月30日*
