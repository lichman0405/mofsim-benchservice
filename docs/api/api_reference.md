# API 参考文档

## 一、概述

本文档提供 MOFSimBench API 的完整参考。

**Base URL**: `https://your-server/api/v1`

**认证**: 所有请求需要在 Header 中包含 `Authorization: Bearer <api_key>`

---

## 二、通用响应格式

### 成功响应

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

### 错误响应

```json
{
  "success": false,
  "error": {
    "code": 40001,
    "message": "错误描述",
    "details": { ... }
  }
}
```

---

## 三、任务 API

### 3.1 提交优化任务

**POST** `/tasks/optimization`

提交结构优化任务。

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "upload",
    "file_id": "file_xxx"
  },
  "parameters": {
    "fmax": 0.001,
    "max_steps": 500,
    "optimizer": "LBFGS"
  },
  "priority": "NORMAL",
  "webhook_url": "https://your-server/callback"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称 |
| structure | object | 是 | 结构来源 |
| parameters | object | 否 | 任务参数 |
| priority | string | 否 | 优先级：CRITICAL, HIGH, NORMAL, LOW |
| webhook_url | string | 否 | 完成时回调 URL |

**响应**：

```json
{
  "success": true,
  "data": {
    "task_id": "task_abc123",
    "status": "PENDING",
    "estimated_wait_seconds": 120
  },
  "message": "任务已提交"
}
```

---

### 3.2 提交稳定性分析任务

**POST** `/tasks/stability`

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "builtin",
    "name": "MOF-5_primitive"
  },
  "parameters": {
    "temperature_k": 300,
    "timestep_fs": 1.0,
    "total_steps": 1000,
    "equilibration_steps": 100
  }
}
```

---

### 3.3 提交体积模量计算任务

**POST** `/tasks/bulk-modulus`

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "upload",
    "file_id": "file_xxx"
  },
  "parameters": {
    "strain_range": 0.05,
    "num_points": 5,
    "fitting_method": "birch_murnaghan"
  }
}
```

---

### 3.4 提交热容计算任务

**POST** `/tasks/heat-capacity`

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "upload",
    "file_id": "file_xxx"
  },
  "parameters": {
    "temperature_range": [100, 500],
    "temperature_step": 50,
    "supercell": [2, 2, 2]
  }
}
```

---

### 3.5 提交相互作用能计算任务

**POST** `/tasks/interaction-energy`

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "upload",
    "file_id": "file_xxx"
  },
  "parameters": {
    "adsorbate": "CO2",
    "grid_spacing": 0.5
  }
}
```

---

### 3.6 提交单点能量计算任务

**POST** `/tasks/single-point-energy`

**请求体**：

```json
{
  "model": "mace_off_prod",
  "structure": {
    "source": "upload",
    "file_id": "file_xxx"
  },
  "parameters": {
    "compute_forces": true,
    "compute_stress": true
  }
}
```

---

### 3.7 查询任务状态

**GET** `/tasks/{task_id}`

**响应**：

```json
{
  "success": true,
  "data": {
    "task_id": "task_abc123",
    "task_type": "optimization",
    "status": "RUNNING",
    "model": "mace_off_prod",
    "progress": 45,
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:31:00Z",
    "gpu_id": 0
  }
}
```

**状态值**：

| 状态 | 说明 |
|------|------|
| PENDING | 已提交，等待入队 |
| QUEUED | 在队列中等待 |
| ASSIGNED | 已分配 GPU |
| RUNNING | 正在执行 |
| COMPLETED | 已完成 |
| FAILED | 执行失败 |
| CANCELLED | 已取消 |
| TIMEOUT | 超时 |

---

### 3.8 获取任务结果

**GET** `/tasks/{task_id}/result`

**响应（优化任务）**：

```json
{
  "success": true,
  "data": {
    "task_id": "task_abc123",
    "result": {
      "converged": true,
      "steps": 156,
      "final_energy_eV": -1234.567,
      "max_force_eV_A": 0.00098,
      "energy_history": [-1230.1, -1232.5, ...],
      "final_structure": {
        "format": "cif",
        "content": "data_...",
        "file_url": "/files/task_abc123/optimized.cif"
      }
    },
    "execution_time_seconds": 245.6
  }
}
```

---

### 3.9 获取任务日志

**GET** `/tasks/{task_id}/logs`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| level | string | 日志级别过滤 |
| limit | int | 返回条数（默认 100） |
| offset | int | 偏移量 |

**响应**：

```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "timestamp": "2024-01-15T10:31:00.123Z",
        "level": "INFO",
        "message": "任务开始执行",
        "context": {"gpu_id": 0}
      }
    ],
    "total": 50
  }
}
```

---

### 3.10 取消任务

**POST** `/tasks/{task_id}/cancel`

**响应**：

```json
{
  "success": true,
  "data": {
    "task_id": "task_abc123",
    "previous_status": "RUNNING",
    "current_status": "CANCELLED"
  }
}
```

---

### 3.11 重试任务

**POST** `/tasks/{task_id}/retry`

**响应**：

```json
{
  "success": true,
  "data": {
    "new_task_id": "task_def456",
    "original_task_id": "task_abc123"
  }
}
```

---

### 3.12 批量查询任务

**GET** `/tasks`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态过滤 |
| task_type | string | 任务类型过滤 |
| model | string | 模型过滤 |
| created_after | datetime | 创建时间起始 |
| created_before | datetime | 创建时间截止 |
| page | int | 页码（默认 1） |
| page_size | int | 每页条数（默认 20） |

**响应**：

```json
{
  "success": true,
  "data": {
    "tasks": [...],
    "pagination": {
      "total": 150,
      "page": 1,
      "page_size": 20,
      "total_pages": 8
    }
  }
}
```

---

## 四、结构 API

### 4.1 上传结构文件

**POST** `/structures/upload`

**Content-Type**: `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| file | file | 结构文件（CIF, XYZ, POSCAR） |
| name | string | 可选名称 |

**响应**：

```json
{
  "success": true,
  "data": {
    "file_id": "file_xxx",
    "filename": "MOF-5.cif",
    "format": "cif",
    "n_atoms": 424,
    "formula": "Zn4O(BDC)3"
  }
}
```

---

### 4.2 获取内置结构列表

**GET** `/structures/builtin`

**响应**：

```json
{
  "success": true,
  "data": {
    "structures": [
      {
        "name": "MOF-5_primitive",
        "formula": "Zn4O(BDC)3",
        "n_atoms": 106,
        "category": "benchmark"
      }
    ]
  }
}
```

---

### 4.3 下载结构文件

**GET** `/structures/{file_id}`

返回结构文件内容。

---

## 五、模型 API

### 5.1 获取模型列表

**GET** `/models`

**响应**：

```json
{
  "success": true,
  "data": {
    "models": [
      {
        "id": "mace_off_prod",
        "name": "MACE-OFF Production",
        "family": "mace",
        "version": "1.0.0",
        "supported_elements": ["H", "C", "N", "O", ...],
        "max_atoms": 5000,
        "d3_available": true
      }
    ]
  }
}
```

---

### 5.2 上传自定义模型

**POST** `/models/upload`

**Content-Type**: `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| model_file | file | 模型检查点文件 |
| config | json | 模型配置 |

---

### 5.3 删除自定义模型

**DELETE** `/models/{model_id}`

---

## 六、系统 API

### 6.1 健康检查

**GET** `/health`

**响应**：

```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "gpus": 8
}
```

---

### 6.2 获取系统状态

**GET** `/system/stats`

**响应**：

```json
{
  "success": true,
  "data": {
    "tasks": {
      "pending": 5,
      "running": 8,
      "completed_today": 120,
      "failed_today": 3
    },
    "gpus": {
      "total": 8,
      "free": 2,
      "busy": 6
    },
    "queue": {
      "size": 15,
      "estimated_wait_seconds": 300
    }
  }
}
```

---

### 6.3 获取 GPU 状态

**GET** `/system/gpus`

**响应**：

```json
{
  "success": true,
  "data": {
    "gpus": [
      {
        "id": 0,
        "name": "NVIDIA GeForce RTX 3090",
        "status": "busy",
        "memory_used_mb": 18000,
        "memory_total_mb": 24576,
        "current_task": "task_abc123",
        "loaded_models": ["mace_off_prod"]
      }
    ]
  }
}
```

---

## 七、文件 API

### 7.1 下载文件

**GET** `/files/{task_id}/{filename}`

下载任务生成的文件。

### 7.2 获取任务文件列表

**GET** `/files/{task_id}`

**响应**：

```json
{
  "success": true,
  "data": {
    "files": [
      {
        "filename": "optimized.cif",
        "size_bytes": 12345,
        "url": "/files/task_abc123/optimized.cif"
      },
      {
        "filename": "trajectory.xyz",
        "size_bytes": 234567,
        "url": "/files/task_abc123/trajectory.xyz"
      }
    ]
  }
}
```

---

## 八、速率限制

| 端点 | 限制 |
|------|------|
| 任务提交 | 100 次/分钟 |
| 状态查询 | 1000 次/分钟 |
| 文件上传 | 10 次/分钟 |
| 其他 | 500 次/分钟 |

超过限制返回 `429 Too Many Requests`。

---

## 九、Webhook 回调

任务完成时，系统会向指定的 `webhook_url` 发送 POST 请求：

```json
{
  "event": "task.completed",
  "task_id": "task_abc123",
  "status": "COMPLETED",
  "timestamp": "2024-01-15T10:35:00Z",
  "result_url": "https://your-server/api/v1/tasks/task_abc123/result"
}
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
