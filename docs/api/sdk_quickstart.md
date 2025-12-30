# SDK 快速入门

## 一、概述

MOFSimBench Python SDK 提供了简洁的接口来访问 MOFSimBench 服务。

---

## 二、安装

```bash
pip install mofsim-sdk
```

---

## 三、快速开始

### 3.1 初始化客户端

```python
from mofsim_sdk import MOFSimClient

# 使用 API Key 初始化
client = MOFSimClient(
    base_url="https://your-server/api/v1",
    api_key="your_api_key"
)
```

### 3.2 提交优化任务

```python
# 使用内置结构
task = client.optimization.submit(
    model="mace_off_prod",
    structure="MOF-5_primitive",  # 内置结构名称
    fmax=0.001,
    max_steps=500
)

print(f"任务 ID: {task.id}")
print(f"状态: {task.status}")
```

### 3.3 使用本地文件

```python
# 上传并使用本地结构文件
task = client.optimization.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",  # 本地文件路径
    fmax=0.001
)
```

### 3.4 等待任务完成

```python
# 等待任务完成（阻塞）
result = task.wait(timeout=3600)

if result.success:
    print(f"最终能量: {result.final_energy_eV} eV")
    print(f"收敛: {result.converged}")
    
    # 保存优化后的结构
    result.save_structure("optimized.cif")
else:
    print(f"任务失败: {result.error}")
```

### 3.5 异步等待

```python
import asyncio

async def main():
    task = client.optimization.submit(
        model="mace_off_prod",
        structure="./my_mof.cif"
    )
    
    # 异步等待
    result = await task.wait_async(timeout=3600)
    print(result)

asyncio.run(main())
```

---

## 四、常见任务

### 4.1 稳定性分析

```python
task = client.stability.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    temperature_k=300,
    total_steps=1000
)

result = task.wait()

if result.stable:
    print("结构稳定")
else:
    print(f"结构不稳定: {result.instability_reason}")
```

### 4.2 体积模量计算

```python
task = client.bulk_modulus.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    strain_range=0.05
)

result = task.wait()

print(f"体积模量: {result.bulk_modulus_GPa} GPa")
print(f"平衡体积: {result.equilibrium_volume_A3} Å³")
```

### 4.3 热容计算

```python
task = client.heat_capacity.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    temperature_range=[100, 500],
    temperature_step=50
)

result = task.wait()

for T, Cv in zip(result.temperatures, result.heat_capacities):
    print(f"T={T} K: Cv={Cv} J/(mol·K)")
```

### 4.4 相互作用能

```python
task = client.interaction_energy.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    adsorbate="CO2"
)

result = task.wait()

print(f"相互作用能: {result.interaction_energy_eV} eV")
```

### 4.5 单点能量

```python
task = client.single_point.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    compute_forces=True,
    compute_stress=True
)

result = task.wait()

print(f"能量: {result.energy_eV} eV")
print(f"力的最大值: {result.max_force_eV_A} eV/Å")
```

---

## 五、批量任务

### 5.1 提交多个任务

```python
structures = ["mof1.cif", "mof2.cif", "mof3.cif"]

tasks = []
for struct in structures:
    task = client.optimization.submit(
        model="mace_off_prod",
        structure=struct
    )
    tasks.append(task)

print(f"提交了 {len(tasks)} 个任务")
```

### 5.2 批量等待

```python
# 等待所有任务完成
results = client.wait_all(tasks, timeout=7200)

for task, result in zip(tasks, results):
    print(f"{task.id}: {result.status}")
```

### 5.3 使用进度条

```python
from tqdm import tqdm

# 带进度条的批量任务
results = client.wait_all(
    tasks,
    timeout=7200,
    progress_bar=True
)
```

---

## 六、任务管理

### 6.1 查询任务状态

```python
task = client.get_task("task_xxx")
print(f"状态: {task.status}")
print(f"进度: {task.progress}%")
```

### 6.2 取消任务

```python
client.cancel_task("task_xxx")
```

### 6.3 重试任务

```python
new_task = client.retry_task("task_xxx")
print(f"新任务 ID: {new_task.id}")
```

### 6.4 列出任务

```python
tasks = client.list_tasks(
    status="COMPLETED",
    task_type="optimization",
    limit=10
)

for task in tasks:
    print(f"{task.id}: {task.status}")
```

---

## 七、模型管理

### 7.1 列出可用模型

```python
models = client.list_models()

for model in models:
    print(f"{model.id}: {model.name}")
    print(f"  支持元素: {model.supported_elements}")
```

### 7.2 检查模型

```python
model = client.get_model("mace_off_prod")
print(f"最大原子数: {model.max_atoms}")
print(f"D3 校正: {model.d3_available}")
```

---

## 八、结构管理

### 8.1 上传结构

```python
file_id = client.upload_structure("./my_mof.cif")
print(f"文件 ID: {file_id}")
```

### 8.2 列出内置结构

```python
structures = client.list_builtin_structures()

for struct in structures:
    print(f"{struct.name}: {struct.formula} ({struct.n_atoms} atoms)")
```

---

## 九、错误处理

```python
from mofsim_sdk.exceptions import (
    MOFSimError,
    AuthenticationError,
    TaskNotFoundError,
    ValidationError,
    RateLimitError
)

try:
    task = client.optimization.submit(
        model="invalid_model",
        structure="./my_mof.cif"
    )
except AuthenticationError:
    print("API Key 无效")
except ValidationError as e:
    print(f"参数验证失败: {e.details}")
except RateLimitError as e:
    print(f"请求过于频繁，请在 {e.retry_after} 秒后重试")
except MOFSimError as e:
    print(f"错误: {e.message}")
```

---

## 十、配置

### 10.1 环境变量

```bash
export MOFSIM_BASE_URL="https://your-server/api/v1"
export MOFSIM_API_KEY="your_api_key"
```

```python
# 自动使用环境变量
client = MOFSimClient()
```

### 10.2 配置文件

`~/.mofsim/config.yaml`:

```yaml
base_url: https://your-server/api/v1
api_key: your_api_key
timeout: 30
max_retries: 3
```

```python
# 自动加载配置文件
client = MOFSimClient()
```

---

## 十一、日志

```python
import logging

# 启用 SDK 日志
logging.getLogger("mofsim_sdk").setLevel(logging.DEBUG)

# 或使用 SDK 配置
client = MOFSimClient(debug=True)
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
