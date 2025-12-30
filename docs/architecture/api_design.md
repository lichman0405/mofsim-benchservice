# API 详细设计

## 一、概述

本文档详细描述 MOFSimBench 服务端 API 的设计规范，包括认证方式、请求/响应格式、所有端点的详细说明。

---

## 二、基础规范

### 2.1 Base URL

```
https://{host}:{port}/api/v1
```

### 2.2 认证方式

使用 API Key 认证，通过 HTTP Header 传递：

```http
Authorization: Bearer {api_key}
```

或使用查询参数（不推荐）：

```
?api_key={api_key}
```

### 2.3 请求格式

- Content-Type: `application/json`
- 字符编码: UTF-8
- 时间格式: ISO 8601 (`2025-12-30T10:00:00Z`)

### 2.4 响应格式

**成功响应**：

```json
{
  "success": true,
  "code": 200,
  "message": "操作成功",
  "data": { ... },
  "timestamp": "2025-12-30T10:00:00Z",
  "request_id": "req_abc123"
}
```

**错误响应**：

```json
{
  "success": false,
  "code": 40001,
  "message": "参数验证失败",
  "error": {
    "type": "ValidationError",
    "detail": "fmax 必须大于 0",
    "field": "parameters.fmax"
  },
  "timestamp": "2025-12-30T10:00:00Z",
  "request_id": "req_abc123"
}
```

### 2.5 分页参数

```
?page=1&page_size=20
```

分页响应：

```json
{
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 156,
      "total_pages": 8
    }
  }
}
```

---

## 三、任务 API

### 3.1 提交优化任务

**POST** `/tasks/optimization`

提交 MOF 结构优化任务。

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "fmax": 0.001,
    "max_steps": 1000,
    "optimizer": "BFGS",
    "filter": "FrechetCellFilter"
  },
  "options": {
    "priority": "NORMAL",
    "timeout": 3600,
    "callback": {
      "url": "https://example.com/webhook",
      "events": ["task.completed", "task.failed"],
      "secret": "webhook-secret"
    }
  }
}
```

**响应** (202 Accepted)：

```json
{
  "success": true,
  "code": 202,
  "message": "任务已提交",
  "data": {
    "task_id": "task_abc123",
    "status": "QUEUED",
    "position": 5,
    "estimated_wait_seconds": 300
  }
}
```

### 3.2 提交稳定性任务

**POST** `/tasks/stability`

提交 MD 稳定性模拟任务。

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "builtin",
    "name": "MOF-5_primitive"
  },
  "parameters": {
    "stages": ["opt", "nvt", "npt"],
    "opt": {
      "fmax": 0.001,
      "max_steps": 500
    },
    "nvt": {
      "temperature_K": 300,
      "timestep_fs": 1.0,
      "total_steps": 1000
    },
    "npt": {
      "temperature_K": 300,
      "pressure_bar": 1.0,
      "timestep_fs": 1.0,
      "total_steps": 20000
    }
  },
  "options": {
    "priority": "NORMAL",
    "timeout": 86400
  }
}
```

### 3.3 提交体积模量任务

**POST** `/tasks/bulk-modulus`

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "strain_range": 0.05,
    "n_points": 7,
    "optimize_first": true
  }
}
```

### 3.4 提交热容任务

**POST** `/tasks/heat-capacity`

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "t_min": 10,
    "t_max": 500,
    "t_step": 10,
    "supercell": [2, 2, 2]
  }
}
```

### 3.5 提交相互作用能任务

**POST** `/tasks/interaction-energy`

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "guest_molecule": "CO2"
  }
}
```

### 3.6 提交单点能量任务

**POST** `/tasks/single-point-energy`

**请求体**：

```json
{
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "compute_forces": true,
    "compute_stress": true
  }
}
```

### 3.7 批量提交任务

**POST** `/tasks/batch`

**请求体**：

```json
{
  "tasks": [
    {
      "task_type": "optimization",
      "model": "mace_prod",
      "structure": { "source": "upload", "file_id": "struct_1" }
    },
    {
      "task_type": "optimization",
      "model": "mace_prod",
      "structure": { "source": "upload", "file_id": "struct_2" }
    }
  ],
  "options": {
    "priority": "LOW"
  }
}
```

**响应**：

```json
{
  "data": {
    "batch_id": "batch_xxx",
    "tasks": [
      { "task_id": "task_1", "status": "QUEUED" },
      { "task_id": "task_2", "status": "QUEUED" }
    ],
    "total": 2
  }
}
```

### 3.8 查询任务状态

**GET** `/tasks/{task_id}`

**响应**：

```json
{
  "data": {
    "task_id": "task_abc123",
    "task_type": "optimization",
    "status": "RUNNING",
    "model": "mace_prod",
    "structure_name": "MOF-5_primitive",
    "priority": "NORMAL",
    "gpu_id": 3,
    "progress": {
      "current_step": 42,
      "total_steps": 1000,
      "percentage": 4.2
    },
    "created_at": "2025-12-30T10:00:00Z",
    "started_at": "2025-12-30T10:00:05Z"
  }
}
```

### 3.9 获取任务结果

**GET** `/tasks/{task_id}/result`

**响应**：

```json
{
  "data": {
    "task_id": "task_abc123",
    "task_type": "optimization",
    "status": "COMPLETED",
    "result": {
      "converged": true,
      "final_energy_eV": -1234.567,
      "final_fmax": 0.00095,
      "steps": 156,
      "volume_change_percent": -0.33
    },
    "output_files": {
      "optimized_structure": "/api/v1/files/result_xxx.cif",
      "trajectory": "/api/v1/files/result_xxx.traj"
    },
    "metrics": {
      "duration_seconds": 325.5,
      "peak_gpu_memory_MB": 8234
    }
  }
}
```

### 3.10 取消任务

**POST** `/tasks/{task_id}/cancel`

**响应**：

```json
{
  "data": {
    "task_id": "task_abc123",
    "status": "CANCELLED",
    "cancelled_at": "2025-12-30T10:05:00Z"
  }
}
```

### 3.11 查询任务列表

**GET** `/tasks`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态过滤 |
| task_type | string | 任务类型过滤 |
| model | string | 模型过滤 |
| page | int | 页码 |
| page_size | int | 每页数量 |

### 3.12 任务日志流

**GET** `/tasks/{task_id}/logs`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| level | string | 日志级别过滤 |
| limit | int | 返回数量 |
| since | datetime | 起始时间 |

**GET** `/tasks/{task_id}/logs/stream`

SSE 实时日志流。

```
event: log
data: {"level": "INFO", "message": "Step 42 completed", "timestamp": "..."}

event: log
data: {"level": "INFO", "message": "Step 43 completed", "timestamp": "..."}
```

---

## 四、模型 API

### 4.1 获取模型列表

**GET** `/models`

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| framework | string | 框架过滤 |
| is_custom | bool | 是否自定义模型 |

**响应**：

```json
{
  "data": {
    "items": [
      {
        "name": "mace_prod",
        "display_name": "MACE-MPA-0-medium",
        "framework": "mace",
        "is_custom": false,
        "is_loaded": true,
        "loaded_gpu_id": 0,
        "with_d3": true
      }
    ]
  }
}
```

### 4.2 获取模型详情

**GET** `/models/{model_name}`

### 4.3 预加载模型

**POST** `/models/{model_name}/load`

**请求体**：

```json
{
  "gpu_id": 0
}
```

### 4.4 卸载模型

**POST** `/models/{model_name}/unload`

### 4.5 上传自定义模型

**POST** `/models/custom`

**Content-Type**: `multipart/form-data`

**表单字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| file | file | 模型文件 |
| name | string | 模型名称 |
| framework | string | 框架类型 |
| config | json | 模型配置 |

### 4.6 验证自定义模型

**POST** `/models/custom/{model_id}/validate`

执行模型验证测试，确认可正常加载和推理。

### 4.7 删除自定义模型

**DELETE** `/models/custom/{model_id}`

---

## 五、结构文件 API

### 5.1 上传结构文件

**POST** `/structures`

**Content-Type**: `multipart/form-data`

**响应**：

```json
{
  "data": {
    "file_id": "struct_xxx",
    "name": "MOF-5.cif",
    "format": "cif",
    "n_atoms": 424,
    "formula": "Zn4O13C24H12"
  }
}
```

### 5.2 结构文件列表

**GET** `/structures`

### 5.3 内置结构列表

**GET** `/structures/builtin`

### 5.4 删除结构文件

**DELETE** `/structures/{file_id}`

---

## 六、系统 API

### 6.1 健康检查

**GET** `/health`

**响应**：

```json
{
  "data": {
    "status": "healthy",
    "components": {
      "api": "healthy",
      "database": "healthy",
      "redis": "healthy",
      "workers": "healthy"
    },
    "version": "0.1.0"
  }
}
```

### 6.2 GPU 状态

**GET** `/system/gpus`

**响应**：

```json
{
  "data": {
    "gpus": [
      {
        "id": 0,
        "name": "NVIDIA GeForce RTX 3090",
        "memory_total_mb": 24576,
        "memory_used_mb": 8234,
        "memory_free_mb": 16342,
        "utilization_percent": 45,
        "temperature_c": 62,
        "status": "busy",
        "current_task_id": "task_xxx"
      }
    ]
  }
}
```

### 6.3 队列状态

**GET** `/system/queue`

**响应**：

```json
{
  "data": {
    "pending": 12,
    "queued": 45,
    "running": 7,
    "by_priority": {
      "CRITICAL": 0,
      "HIGH": 5,
      "NORMAL": 40,
      "LOW": 12
    }
  }
}
```

### 6.4 系统配置

**GET** `/system/config`

---

## 七、告警 API

### 7.1 告警规则列表

**GET** `/system/alerts/rules`

### 7.2 当前活跃告警

**GET** `/system/alerts/active`

### 7.3 告警历史

**GET** `/system/alerts/history`

---

## 八、文件下载

### 8.1 下载结果文件

**GET** `/files/{file_id}`

返回文件内容，支持 Range 请求。

---

## 九、错误码列表

见 [error_codes.md](../api/error_codes.md)

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
