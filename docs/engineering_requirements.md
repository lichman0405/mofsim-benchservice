# MOFSimBench 工程化需求规格说明书

## 一、项目背景

将 MOFSimBench 基准测试项目工程化为一个可部署的服务端应用，支持通过 API 接口提交计算任务、异步执行、获取结构化结果，并提供完备的日志系统。

---

## 二、硬件环境

| 资源 | 规格 |
|-----|------|
| CPU | 高性能多核处理器 |
| GPU | 8 × NVIDIA RTX 3090（24GB 显存/卡） |
| 内存 | 建议 ≥256GB |
| 存储 | SSD，建议 ≥2TB（用于模型、结构文件、结果存储） |
| 网络 | 支持高并发 API 请求 |
| 部署模式 | 单节点部署，无需多节点扩展 |

### 2.1 GPU 资源规划

| GPU ID | 用途 | 说明 |
|--------|------|------|
| GPU 0-6 | 计算任务 | 用于执行 MOF 模拟任务 |
| GPU 7 | 备用/模型预热 | 可用于模型预加载或作为备用资源 |

> **注意**：RTX 3090 的 24GB 显存可满足大多数 uMLIP 模型的推理需求，但对于超大 MOF 结构（>5000 原子）可能需要特殊处理。

---

## 三、功能需求

### 3.1 核心计算任务 API

基于项目现有能力，需要暴露以下任务类型的 API：

| 任务类型 | 端点 | 说明 |
|---------|------|------|
| 结构优化 | `POST /api/v1/tasks/optimization` | 提交 MOF 结构优化任务 |
| 稳定性模拟 | `POST /api/v1/tasks/stability` | 提交 MD 稳定性模拟任务 |
| 体积模量计算 | `POST /api/v1/tasks/bulk-modulus` | 计算材料体积模量 |
| 热容计算 | `POST /api/v1/tasks/heat-capacity` | 计算热容（声子计算） |
| 相互作用能 | `POST /api/v1/tasks/interaction-energy` | 计算 MOF-气体相互作用能 |
| 单点能量计算 | `POST /api/v1/tasks/single-point-energy` | 快速单点能量计算 |

### 3.2 任务管理 API

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 查询任务状态 | `/api/v1/tasks/{task_id}` | GET | 获取任务当前状态 |
| 获取任务结果 | `/api/v1/tasks/{task_id}/result` | GET | 获取已完成任务的结果 |
| 取消任务 | `/api/v1/tasks/{task_id}/cancel` | POST | 取消排队中或运行中的任务 |
| 任务列表 | `/api/v1/tasks` | GET | 分页查询任务列表 |
| 任务日志流 | `/api/v1/tasks/{task_id}/logs` | GET (SSE) | 实时获取任务日志 |
| 批量提交任务 | `/api/v1/tasks/batch` | POST | 批量提交多个任务 |

### 3.3 资源管理 API

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 可用模型列表 | `/api/v1/models` | GET | 获取所有可用的 uMLIP 模型 |
| 模型详情 | `/api/v1/models/{model_name}` | GET | 获取模型配置和状态 |
| 预加载模型 | `/api/v1/models/{model_name}/load` | POST | 预热模型到指定 GPU |
| 卸载模型 | `/api/v1/models/{model_name}/unload` | POST | 从 GPU 释放模型 |
| **上传自定义模型** | `/api/v1/models/custom` | POST | 上传用户自定义模型文件 |
| **自定义模型列表** | `/api/v1/models/custom` | GET | 查询已上传的自定义模型 |
| **删除自定义模型** | `/api/v1/models/custom/{model_id}` | DELETE | 删除自定义模型 |
| **验证自定义模型** | `/api/v1/models/custom/{model_id}/validate` | POST | 验证模型可用性 |
| 上传结构文件 | `/api/v1/structures` | POST | 上传 CIF/XYZ 结构文件 |
| 结构文件列表 | `/api/v1/structures` | GET | 查询已上传的结构 |
| 内置结构列表 | `/api/v1/structures/builtin` | GET | 获取内置测试结构 |

### 3.4 自定义模型上传规范

支持上传以下类型的自定义模型：

| 模型框架 | 文件格式 | 说明 |
|---------|---------|------|
| MACE | `.model` | MACE 训练的模型文件 |
| ORB | `.pt` / `.pth` | ORB 模型权重 |
| SevenNet | `.pt` | SevenNet 模型文件 |
| 通用 PyTorch | `.pt` / `.pth` | 需提供配置文件说明接口 |

**上传请求格式**：

```json
{
  "name": "my_custom_mace",
  "framework": "mace",
  "description": "自定义训练的 MACE 模型",
  "with_d3": true,
  "config": {
    "precision": "float32"
  }
}
```

**注意**：自定义模型上传后需通过验证接口测试，确认可正常加载和推理后方可用于任务。

### 3.5 系统管理 API

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 健康检查 | `/api/v1/health` | GET | 服务健康状态 |
| GPU 状态 | `/api/v1/system/gpus` | GET | 各 GPU 使用情况 |
| 队列状态 | `/api/v1/system/queue` | GET | 任务队列统计 |
| 系统配置 | `/api/v1/system/config` | GET | 获取当前系统配置 |
| **告警规则列表** | `/api/v1/system/alerts/rules` | GET | 获取告警规则 |
| **告警历史** | `/api/v1/system/alerts/history` | GET | 查询告警历史 |
| **当前告警** | `/api/v1/system/alerts/active` | GET | 获取当前活跃告警 |

---

## 四、异步执行架构

### 4.1 任务生命周期

```
提交任务 → 入队等待 → 分配资源 → 执行中 → 完成/失败
   ↓           ↓          ↓         ↓
 PENDING    QUEUED    ASSIGNED   RUNNING   COMPLETED/FAILED/CANCELLED
```

### 4.2 任务状态定义

| 状态 | 说明 |
|------|------|
| `PENDING` | 任务已接收，等待验证 |
| `QUEUED` | 任务已入队，等待 GPU 资源 |
| `ASSIGNED` | 已分配 GPU，准备执行 |
| `RUNNING` | 任务正在执行 |
| `COMPLETED` | 任务成功完成 |
| `FAILED` | 任务执行失败 |
| `CANCELLED` | 任务被用户取消 |
| `TIMEOUT` | 任务超时 |

### 4.3 结果获取方式

支持两种模式：

1. **轮询模式**：客户端定期查询 `GET /api/v1/tasks/{task_id}` 获取状态
2. **推送模式**：通过 SSE（Server-Sent Events）实时推送任务状态和日志

### 4.4 GPU 资源调度策略

| 策略 | 说明 |
|------|------|
| 任务隔离 | 每个任务独占一张 GPU，避免显存冲突 |
| **优先级队列** | 支持 4 级任务优先级（见下表） |
| 模型亲和性 | 相同模型的任务优先调度到已加载该模型的 GPU |
| 负载均衡 | 优先选择空闲或负载最低的 GPU |
| 超时控制 | 单任务最大执行时间限制，防止资源长期占用 |
| **显存保护** | 任务提交前预估显存需求，避免 OOM |

### 4.5 任务优先级机制

| 优先级 | 值 | 说明 | 典型场景 |
|--------|---|------|---------|
| CRITICAL | 0 | 最高优先级 | 紧急任务，立即调度 |
| HIGH | 1 | 高优先级 | 重要任务，优先处理 |
| NORMAL | 2 | 普通优先级（默认） | 常规任务 |
| LOW | 3 | 低优先级 | 批量任务、后台任务 |

**调度规则**：
1. 高优先级任务可插队到低优先级任务之前
2. 同优先级任务按提交时间 FIFO 排序
3. 正在运行的任务不会被抢占

### 4.6 回调通知机制

任务完成后可通过 Webhook 回调通知客户端：

**回调请求格式**：

```json
{
  "event": "task.completed",
  "task_id": "task_abc123",
  "status": "COMPLETED",
  "timestamp": "2025-12-30T10:05:30Z",
  "result_url": "/api/v1/tasks/task_abc123/result",
  "summary": {
    "duration_seconds": 325.5,
    "converged": true,
    "final_energy_eV": -1234.567
  }
}
```

**支持的回调事件**：

| 事件 | 说明 |
|------|------|
| `task.started` | 任务开始执行 |
| `task.progress` | 任务进度更新（可选，按百分比） |
| `task.completed` | 任务成功完成 |
| `task.failed` | 任务执行失败 |
| `task.cancelled` | 任务被取消 |
| `task.timeout` | 任务超时 |

**回调配置**：

```json
{
  "notify_url": "https://client.example.com/webhook",
  "notify_events": ["task.completed", "task.failed"],
  "notify_secret": "your-webhook-secret",
  "retry_times": 3,
  "retry_interval_seconds": 10
}
```

---

## 五、结构化数据规范

### 5.1 统一响应格式

所有 API 响应遵循统一格式：

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

错误响应：

```json
{
  "success": false,
  "code": 40001,
  "message": "结构文件格式不支持",
  "error": {
    "type": "ValidationError",
    "detail": "仅支持 .cif 和 .xyz 格式",
    "field": "structure_file"
  },
  "timestamp": "2025-12-30T10:00:00Z",
  "request_id": "req_abc123"
}
```

### 5.2 任务提交请求格式

```json
{
  "task_type": "optimization",
  "model": "mace_prod",
  "structure": {
    "source": "upload",
    "file_id": "struct_xxx"
  },
  "parameters": {
    "fmax": 0.001,
    "max_steps": 1000,
    "optimizer": "BFGS",
    "with_d3": true
  },
  "options": {
    "priority": "NORMAL",
    "timeout": 3600,
    "notify_url": "https://client.example.com/callback"
  }
}
```

### 5.3 任务结果格式（以优化任务为例）

```json
{
  "task_id": "task_abc123",
  "task_type": "optimization",
  "status": "COMPLETED",
  "model": "mace_prod",
  "structure_name": "MOF-5_primitive",
  "created_at": "2025-12-30T10:00:00Z",
  "started_at": "2025-12-30T10:00:05Z",
  "completed_at": "2025-12-30T10:05:30Z",
  "duration_seconds": 325.5,
  "gpu_id": 3,
  "result": {
    "converged": true,
    "final_energy_eV": -1234.567,
    "final_fmax": 0.00095,
    "steps": 156,
    "initial_volume_A3": 17256.3,
    "final_volume_A3": 17198.7,
    "volume_change_percent": -0.33,
    "cell_parameters": {
      "a": 25.832, "b": 25.832, "c": 25.832,
      "alpha": 90.0, "beta": 90.0, "gamma": 90.0
    },
    "rmsd_from_initial": 0.0234,
    "output_files": {
      "optimized_structure": "/api/v1/files/result_xxx.cif",
      "trajectory": "/api/v1/files/result_xxx.traj"
    }
  },
  "metrics": {
    "peak_gpu_memory_MB": 8234,
    "avg_step_time_ms": 2085
  }
}
```

### 5.4 错误码定义

| 错误码 | 类别 | 说明 |
|-------|------|------|
| 10xxx | 系统错误 | 服务内部错误 |
| 20xxx | 认证错误 | 未授权、Token 过期等 |
| 30xxx | 资源错误 | GPU 不可用、模型未找到等 |
| 40xxx | 请求错误 | 参数验证失败、格式错误等 |
| 50xxx | 任务错误 | 任务执行失败、超时等 |

---

## 六、日志系统需求

### 6.1 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 详细调试信息（开发环境） |
| INFO | 常规运行信息 |
| WARNING | 警告信息 |
| ERROR | 错误信息 |
| CRITICAL | 严重错误 |

### 6.2 日志类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 系统日志 | 服务启动、配置加载等 | 模型加载完成、GPU 初始化 |
| 任务日志 | 任务执行过程日志 | 优化步骤、能量变化 |
| 访问日志 | API 请求日志 | 请求路径、响应时间 |
| 审计日志 | 操作审计 | 任务取消、模型卸载 |

### 6.3 日志格式（结构化 JSON）

```json
{
  "timestamp": "2025-12-30T10:00:00.123Z",
  "level": "INFO",
  "logger": "task.optimization",
  "message": "Optimization step completed",
  "task_id": "task_abc123",
  "gpu_id": 3,
  "extra": {
    "step": 42,
    "energy": -1234.567,
    "fmax": 0.0123
  }
}
```

### 6.4 客户端日志获取

1. **历史日志查询**：`GET /api/v1/tasks/{task_id}/logs?level=INFO&limit=100`
2. **实时日志流**：`GET /api/v1/tasks/{task_id}/logs/stream` (SSE)
3. **系统日志流**：`GET /api/v1/system/logs/stream` (SSE，需管理员权限)

### 6.5 日志存储

| 存储位置 | 保留策略 |
|---------|---------|
| 文件系统 | **永久保留**，按日期/月份归档压缩 |
| 数据库 | 任务日志永久保留（随任务） |
| 实时缓冲 | 内存环形缓冲区，用于 SSE 推送 |

### 6.6 日志归档策略

| 时间范围 | 存储方式 | 说明 |
|---------|---------|------|
| 最近 7 天 | 原始日志文件 | 快速访问 |
| 7-30 天 | 压缩归档 | gzip 压缩 |
| 30 天以上 | 按月打包 | 月度归档包 |

---

## 七、告警系统

### 7.1 告警级别

| 级别 | 说明 | 通知方式 |
|------|------|---------|
| CRITICAL | 严重告警，服务不可用 | 立即通知 |
| WARNING | 警告，需要关注 | 聚合后通知 |
| INFO | 信息性告警 | 仅记录 |

### 7.2 内置告警规则

| 告警类型 | 触发条件 | 级别 |
|---------|---------|------|
| GPU 不可用 | GPU 设备丢失或驱动错误 | CRITICAL |
| GPU 显存不足 | 可用显存 < 2GB | WARNING |
| GPU 温度过高 | 温度 > 85°C | WARNING |
| 任务队列积压 | 等待任务 > 100 | WARNING |
| 任务连续失败 | 同模型连续失败 > 5 次 | WARNING |
| 磁盘空间不足 | 可用空间 < 50GB | WARNING |
| 服务响应超时 | API P99 > 5s | WARNING |
| Worker 离线 | Worker 心跳丢失 | CRITICAL |

### 7.3 告警通知渠道

| 渠道 | 说明 |
|------|------|
| Webhook | HTTP POST 回调 |
| 日志 | 写入告警日志 |
| 文件 | 写入告警文件（可被外部监控系统采集） |

**告警通知格式**：

```json
{
  "alert_id": "alert_xxx",
  "level": "WARNING",
  "type": "gpu_memory_low",
  "message": "GPU 3 可用显存不足: 1.2GB",
  "details": {
    "gpu_id": 3,
    "available_memory_gb": 1.2,
    "total_memory_gb": 24.0
  },
  "timestamp": "2025-12-30T10:00:00Z",
  "resolved": false
}
```

---

## 八、数据存储需求

### 8.1 任务结果存储

| 数据类型 | 存储方式 | 保留期限 |
|---------|---------|---------|
| 任务元数据 | PostgreSQL | **永久** |
| 任务日志 | PostgreSQL + 文件 | **永久** |
| 结构化结果 | PostgreSQL (JSONB) | **≥180 天** |
| 轨迹文件 | 文件系统 | **≥180 天** |
| 优化后结构 | 文件系统 | **≥180 天** |

### 8.2 存储容量估算

基于典型使用场景估算：

| 数据类型 | 单任务大小 | 每日任务量 | 180天存储量 |
|---------|-----------|-----------|------------|
| 元数据 | ~10KB | 100 | ~180MB |
| 日志 | ~100KB | 100 | ~1.8GB |
| 轨迹文件 | ~10MB | 100 | ~180GB |
| 结构文件 | ~100KB | 100 | ~1.8GB |

**建议存储空间**：≥500GB 用于结果存储

### 8.3 数据清理策略

| 操作 | 触发条件 | 说明 |
|------|---------|------|
| 自动归档 | 任务完成后 30 天 | 轨迹文件压缩 |
| 手动清理 | 用户请求 | 提供 API 删除指定任务 |
| 过期提醒 | 临近 180 天 | 可配置是否自动延期 |

---

## 九、非功能需求

### 7.1 性能需求

| 指标 | 要求 |
|------|------|
| API 响应时间 | P99 < 200ms（非计算接口） |
| 并发任务数 | 最多 8 个（每 GPU 一个） |
| 队列容量 | ≥ 1000 个待执行任务 |
| 文件上传 | 单文件最大 100MB |

### 7.2 可靠性需求

| 需求 | 说明 |
|------|------|
| 任务持久化 | 任务状态和结果持久化到数据库，服务重启后可恢复 |
| 优雅关闭 | 服务停止时等待运行中任务完成（可配置超时） |
| 失败重试 | 瞬态错误自动重试（可配置次数和间隔） |
| 错误隔离 | 单任务失败不影响其他任务 |

### 7.3 安全需求

| 需求 | 说明 |
|------|------|
| API 认证 | 支持 API Key 认证 |
| 请求限流 | 防止恶意请求，按 API Key 限流 |
| 输入验证 | 严格验证所有输入，防止注入攻击 |
| 文件安全 | 上传文件类型和内容校验 |

### 7.4 可观测性

| 需求 | 说明 |
|------|------|
| 指标暴露 | Prometheus 格式指标端点 `/metrics` |
| 链路追踪 | 请求 ID 贯穿全链路 |
| 健康检查 | Kubernetes 兼容的健康检查端点 |

---

## 十、客户端 SDK 需求

### 10.1 SDK 设计原则

| 原则 | 说明 |
|------|------|
| 易用性 | 简洁的 API，开箱即用 |
| 可扩展性 | 支持后续扩展为 TUI（终端用户界面） |
| 异步支持 | 同时提供同步和异步接口 |
| 类型安全 | 完整的类型注解，支持 IDE 自动补全 |

### 10.2 核心功能

```python
from mofsim_client import MOFSimClient

# 初始化客户端
client = MOFSimClient(
    base_url="http://server:8000",
    api_key="your-api-key"
)

# 提交任务
task = client.submit_optimization(
    structure="path/to/mof.cif",
    model="mace_prod",
    priority="NORMAL"
)

# 等待结果（同步）
result = task.wait()

# 或异步获取
async for log in task.stream_logs():
    print(log)

result = await task.result()
```

### 10.3 TUI 扩展预留

SDK 架构需支持后续扩展为 TUI 模式：

| 组件 | 说明 |
|------|------|
| 核心层 | API 通信、数据模型（SDK 核心） |
| 适配层 | 输出格式适配（JSON/Table/Rich） |
| 展示层 | TUI 界面（后期实现） |

建议使用 [Rich](https://github.com/Textualize/rich) 或 [Textual](https://github.com/Textualize/textual) 作为 TUI 框架。

### 10.4 SDK 功能清单

| 功能 | 方法 | 说明 |
|------|------|------|
| 任务提交 | `submit_*()` | 各类任务提交 |
| 状态查询 | `get_task()` | 查询任务状态 |
| 结果获取 | `get_result()` | 获取任务结果 |
| 日志流 | `stream_logs()` | 实时日志流 |
| 任务取消 | `cancel_task()` | 取消任务 |
| 模型管理 | `list_models()` | 模型列表 |
| 上传文件 | `upload_*()` | 上传结构/模型 |
| 系统状态 | `get_system_status()` | 系统状态 |

---

## 十一、技术选型建议

### 8.1 核心框架

| 组件 | 推荐选型 | 理由 |
|------|---------|------|
| Web 框架 | FastAPI | 原生异步、自动 OpenAPI 文档、Pydantic 集成 |
| 任务队列 | Celery + Redis | 成熟稳定、支持任务优先级和结果后端 |
| 数据库 | PostgreSQL | 可靠、支持 JSON 字段存储结构化结果 |
| 缓存 | Redis | 模型状态缓存、日志缓冲 |
| 日志 | structlog + Loguru | 结构化日志、性能优秀 |

### 8.2 部署方案

| 方案 | 说明 |
|------|------|
| Docker Compose | 单机部署，适合当前场景 |
| 进程管理 | Supervisor 或 systemd 管理 Worker 进程 |
| GPU 隔离 | 每个 Worker 绑定特定 GPU（CUDA_VISIBLE_DEVICES） |

### 8.3 项目结构建议

```
mofsim-bench/
├── api/                      # API 层
│   ├── main.py               # FastAPI 入口
│   ├── routers/              # 路由模块
│   │   ├── tasks.py
│   │   ├── models.py
│   │   ├── structures.py
│   │   └── system.py
│   ├── schemas/              # Pydantic 模型
│   ├── dependencies.py       # 依赖注入
│   └── middleware/           # 中间件
├── core/                     # 核心业务逻辑
│   ├── tasks/                # 任务执行器
│   ├── models/               # 模型管理
│   ├── scheduler/            # GPU 调度器
│   └── config.py             # 配置管理
├── workers/                  # Celery Workers
│   ├── celery_app.py
│   └── task_handlers.py
├── db/                       # 数据库
│   ├── models.py             # SQLAlchemy 模型
│   └── crud.py               # 数据操作
├── logging/                  # 日志系统
│   ├── config.py
│   └── handlers.py
├── mof_benchmark/            # 原有计算核心（保持不变）
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── config/
    ├── settings.yaml
    └── logging.yaml
```

---

## 十二、API 文档需求

### 12.1 文档类型

| 文档类型 | 格式 | 说明 |
|---------|------|------|
| OpenAPI 规范 | JSON/YAML | 机器可读的 API 规范 |
| Swagger UI | HTML | 交互式 API 文档 |
| ReDoc | HTML | 美观的 API 参考文档 |
| SDK 文档 | Markdown + Sphinx | Python SDK 使用文档 |

### 12.2 文档端点

| 端点 | 说明 |
|------|------|
| `/docs` | Swagger UI 交互文档 |
| `/redoc` | ReDoc 静态文档 |
| `/openapi.json` | OpenAPI 规范文件 |

### 12.3 文档内容要求

- 所有 API 端点的详细说明
- 请求/响应示例
- 错误码说明
- 认证方式说明
- 使用示例代码（Python）

---

## 十三、已确认事项

### 13.1 硬件相关 ✅

| 事项 | 确认结果 |
|------|---------|
| GPU 型号 | NVIDIA RTX 3090，24GB 显存 |
| 多节点支持 | **不需要**，单机部署 |
| 存储要求 | 无特殊要求，使用本地 SSD |

### 13.2 功能相关 ✅

| 事项 | 确认结果 |
|------|---------|
| 用户系统 | **不需要**，无多租户 |
| 结果存储 | **需要**，保留 ≥180 天 |
| 自定义模型 | **需要**，支持用户上传模型 |
| 优先级机制 | **需要**，4 级优先级 |
| 回调通知 | **需要**，Webhook 方式 |

### 13.3 集成相关 ✅

| 事项 | 确认结果 |
|------|---------|
| 客户端形式 | Python SDK，后续可扩展 TUI |
| 现有系统集成 | **不需要**，独立部署 |
| API 文档 | **需要**，OpenAPI + Swagger |

### 13.4 运维相关 ✅

| 事项 | 确认结果 |
|------|---------|
| 日志保留 | **永久保留** |
| 告警功能 | **需要** |
| 监控对接 | 灵活选择，建议 Prometheus |

---

## 十四、开发阶段规划（建议）

| 阶段 | 内容 | 预估周期 |
|------|------|---------|
| Phase 1 | 基础框架搭建、单任务 API、基本日志 | 1-2 周 |
| Phase 2 | 任务队列、GPU 调度、异步执行、优先级 | 1-2 周 |
| Phase 3 | 完整任务类型实现、结构化结果 | 2-3 周 |
| Phase 4 | 自定义模型上传、验证 | 1 周 |
| Phase 5 | 日志系统完善、SSE 推送、回调通知 | 1 周 |
| Phase 6 | 告警系统、监控指标 | 1 周 |
| Phase 7 | Python SDK 开发 | 1-2 周 |
| Phase 8 | 测试、文档、部署优化 | 1-2 周 |

**总计**：约 10-14 周

---

## 十五、项目结构建议

```
mofsim-bench/
├── api/                      # API 服务层
│   ├── main.py               # FastAPI 入口
│   ├── routers/              # 路由模块
│   │   ├── tasks.py          # 任务相关 API
│   │   ├── models.py         # 模型管理 API
│   │   ├── structures.py     # 结构文件 API
│   │   ├── system.py         # 系统管理 API
│   │   └── alerts.py         # 告警 API
│   ├── schemas/              # Pydantic 数据模型
│   │   ├── task.py
│   │   ├── model.py
│   │   ├── response.py
│   │   └── ...
│   ├── dependencies.py       # 依赖注入
│   └── middleware/           # 中间件
│       ├── logging.py        # 请求日志
│       └── error_handler.py  # 错误处理
├── core/                     # 核心业务逻辑
│   ├── tasks/                # 任务执行器
│   │   ├── base.py
│   │   ├── optimization.py
│   │   ├── stability.py
│   │   └── ...
│   ├── models/               # 模型管理
│   │   ├── registry.py       # 模型注册表
│   │   ├── loader.py         # 模型加载器
│   │   └── custom.py         # 自定义模型处理
│   ├── scheduler/            # GPU 调度器
│   │   ├── scheduler.py
│   │   └── priority_queue.py
│   ├── callback/             # 回调通知
│   │   └── webhook.py
│   └── config.py             # 配置管理
├── workers/                  # Celery Workers
│   ├── celery_app.py
│   └── task_handlers.py
├── db/                       # 数据库层
│   ├── models.py             # SQLAlchemy 模型
│   ├── crud.py               # 数据操作
│   └── migrations/           # 数据库迁移
├── logging/                  # 日志系统
│   ├── config.py
│   ├── handlers.py
│   └── formatters.py
├── alerts/                   # 告警系统
│   ├── rules.py
│   ├── notifier.py
│   └── checker.py
├── sdk/                      # Python SDK
│   ├── mofsim_client/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── models.py
│   │   ├── async_client.py
│   │   └── exceptions.py
│   ├── setup.py
│   └── README.md
├── mof_benchmark/            # 原有计算核心（保持不变）
├── storage/                  # 存储目录
│   ├── structures/           # 上传的结构文件
│   ├── models/               # 自定义模型
│   ├── results/              # 任务结果
│   └── logs/                 # 日志文件
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
├── config/
│   ├── settings.yaml         # 主配置
│   ├── logging.yaml          # 日志配置
│   └── alerts.yaml           # 告警规则
├── docs/
│   ├── project_analysis_report.md
│   ├── engineering_requirements.md
│   └── api/                  # API 文档
└── tests/
    ├── test_api/
    ├── test_core/
    └── test_sdk/
```

---

*文档版本：v2.0*  
*更新日期：2025年12月30日*  
*状态：需求已确认*
