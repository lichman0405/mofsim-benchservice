# 模型目录

## 一、概述

本文档列出 MOFSimBench 集成的所有通用机器学习原子间势（uMLIP）模型及其详细信息。项目支持 **8 大类、20+ 个预训练模型**。

---

## 二、模型列表

### 2.1 MACE 系列

MACE（Multi-ACE）是基于等变消息传递神经网络的高精度势能模型。

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| MACE-MP-0b3-medium | `mace_prod_b3` | [官方 GitHub](https://github.com/ACEsuit/mace) 或 `mace_mp()` 自动下载 |
| MACE-128-L1 (2023) | `mace_prod_0a` | 需手动下载模型文件 |
| MACE-MOF-v1 | `mace_prod_mof` | 专为 MOF 训练的模型，需手动获取 |
| MACE-MPA-0-medium | `mace_prod` | [Hugging Face](https://huggingface.co/mace-ml) 自动下载 |
| MACE-OMAT-0-medium | `mace_prod_omat` | [Hugging Face](https://huggingface.co/mace-ml) 自动下载 |
| MACE-MatPES-r2scan | `mace_prod_matpes` | [Hugging Face](https://huggingface.co/mace-ml) 自动下载 |

**安装方式**：
```bash
pip install mace-torch
pip install torch-dftd  # D3 色散校正
```

**官方仓库**：https://github.com/ACEsuit/mace

---

### 2.2 ORB 系列

ORB 是 Orbital Materials 开发的高速图神经网络势能模型，特别适合大规模筛选。

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

---

### 2.3 OMAT24 (FAIRChem/EquiformerV2)

OMAT24 是 Meta FAIR 团队开发的基于 EquiformerV2 架构的通用材料模型。

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

---

### 2.4 GRACE 系列

GRACE（Graph-based Atomic Cluster Expansion）是具有良好外推性能的张量势模型。

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

---

### 2.5 MatterSim

MatterSim 是微软开发的深度学习通用势能模型。

| 模型名称 | 配置键 | 下载/加载方式 |
|---------|--------|--------------|
| MatterSim-v1.0.0-5M | `mattersim_prod` | 通过 `mattersim` 包加载 |

**安装方式**：
```bash
pip install mattersim
```

**官方仓库**：https://github.com/microsoft/mattersim

---

### 2.6 SevenNet (7net)

SevenNet 是首尔大学开发的稳定性优化模型，特别适合长时间 MD 模拟。

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

---

### 2.7 其他模型

| 模型类型 | 配置键 | 安装/下载方式 |
|---------|--------|--------------|
| PosEGNN | - | 需要 `posegnn` 包，模型文件需手动配置 |
| MatGL (M3GNet) | `matgl_prod` | `pip install matgl`，通过 `matgl.load_model()` 加载 |

---

### 2.8 D3 色散校正

大多数模型需要配合 D3 色散校正使用以获得更准确的非共价相互作用描述：

```bash
pip install torch-dftd
```

在配置文件中，带有 `_d3` 后缀的模型配置表示已启用 D3 校正。

---

## 三、模型性能对比

| 指标 | MACE | ORB | OMAT24 | GRACE | SevenNet | MatterSim |
|------|------|-----|--------|-------|----------|-----------|
| **能量精度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **力精度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **推理速度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **显存效率** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **MD 稳定性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **元素覆盖** | 广泛 | 广泛 | 广泛 | 广泛 | 广泛 | 广泛 |

---

## 四、模型选择建议

### 4.1 按任务类型

| 任务 | 推荐模型 | 说明 |
|------|---------|------|
| **几何优化** | `mace_prod`, `orb_prod` | MACE 精度高，ORB 速度快 |
| **MD 模拟** | `sevennet_prod`, `mace_prod` | SevenNet 稳定性极佳 |
| **体积模量** | `mace_prod`, `omat24_prod` | 需要准确的应力张量 |
| **热容计算** | `mace_prod` | 需要高精度声子计算 |
| **相互作用能** | `mace_prod_mof`, `orb_prod` | MOF 专用模型效果更好 |

### 4.2 按体系规模

| 原子数 | 推荐模型 | 说明 |
|--------|---------|------|
| < 500 | 任意模型 | 所有模型都能高效处理 |
| 500 - 2000 | `mace_prod`, `omat24_prod`, `sevennet_prod` | 平衡精度与速度 |
| > 2000 | `orb_prod`, `orb_prod_v3` | ORB 系列显存占用低 |

### 4.3 按元素组成

| 体系类型 | 推荐模型 |
|---------|---------|
| 含过渡金属 MOF | `mace_prod`, `omat24_prod`, `mace_prod_mof` |
| 纯有机框架 (COF) | `mace_prod`, `orb_prod` |
| 含镧系/锕系 | `omat24_prod` |

---

## 五、快速测试模型

使用内置测试脚本验证模型是否正确安装：

```bash
# 测试单个模型
python mof_benchmark/setup/test_calculator.py mace_prod

# 测试所有已安装模型
python mof_benchmark/setup/test_calculator.py --all
```

---

## 六、引用信息

如果您在研究中使用了这些模型，请引用相应的论文：

### MOFSimBench
```bibtex
@article{mofsimbench2025,
  title={MOFSimBench: evaluating universal machine learning interatomic potentials in metal-organic framework molecular modeling},
  journal={npj Computational Materials},
  year={2025},
  doi={10.1038/s41524-025-01872-3}
}
```

### 模型引用
- **MACE**: Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", NeurIPS 2022.
- **ORB**: Orbital Materials, "ORB: A Fast and General Graph Neural Network for Molecular Properties", 2023.
- **OMAT24**: Meta FAIR, "Open Materials 2024 (OMAT24) Dataset and Models", 2024.
- **GRACE**: Bochkarev et al., "Efficient parametrization of the atomic cluster expansion", Phys. Rev. Materials, 2022.
- **MatterSim**: Microsoft Research, "MatterSim: A Deep Learning Atomistic Model Across Elements, Temperatures and Pressures", 2024.
- **SevenNet**: Park et al., "Scalable Parallel Algorithm for Graph Neural Network Interatomic Potentials", 2024.

---

*文档版本：v1.1*  
*更新日期：2025年12月30日*
