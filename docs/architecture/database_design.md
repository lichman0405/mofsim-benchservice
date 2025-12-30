# 数据库设计

## 一、概述

MOFSimBench 服务端使用 PostgreSQL 作为主数据库，存储任务元数据、日志、告警等信息。本文档详细说明数据库表结构设计。

---

## 二、ER 图

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     tasks       │       │   task_logs     │       │   task_results  │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │──────<│ task_id (FK)    │       │ task_id (PK,FK) │
│ task_type       │       │ id (PK)         │       │ result_data     │
│ status          │       │ level           │       │ output_files    │
│ model           │       │ message         │       │ metrics         │
│ priority        │       │ extra           │       │ created_at      │
│ ...             │       │ created_at      │       └─────────────────┘
└─────────────────┘       └─────────────────┘               │
        │                                                    │
        │                                                    │
        ▼                                                    │
┌─────────────────┐       ┌─────────────────┐               │
│   structures    │       │   models        │               │
├─────────────────┤       ├─────────────────┤               │
│ id (PK)         │       │ id (PK)         │               │
│ name            │       │ name            │               │
│ file_path       │       │ framework       │               │
│ format          │       │ file_path       │               │
│ is_builtin      │       │ is_custom       │               │
│ ...             │       │ ...             │               │
└─────────────────┘       └─────────────────┘               │
                                                             │
┌─────────────────┐       ┌─────────────────┐               │
│     alerts      │       │  alert_rules    │               │
├─────────────────┤       ├─────────────────┤               │
│ id (PK)         │       │ id (PK)         │               │
│ rule_id (FK)    │──────>│ name            │               │
│ level           │       │ condition       │               │
│ message         │       │ level           │               │
│ resolved        │       │ enabled         │               │
│ ...             │       │ ...             │               │
└─────────────────┘       └─────────────────┘               │
```

---

## 三、表结构详细设计

### 3.1 任务表 (tasks)

存储所有任务的元数据。

```sql
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       VARCHAR(50) NOT NULL,           -- 任务类型
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority        INTEGER NOT NULL DEFAULT 2,      -- 0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW
    
    -- 关联信息
    model_name      VARCHAR(100) NOT NULL,          -- 使用的模型
    structure_id    UUID REFERENCES structures(id),  -- 结构文件
    
    -- 任务参数
    parameters      JSONB NOT NULL DEFAULT '{}',    -- 任务参数
    options         JSONB NOT NULL DEFAULT '{}',    -- 任务选项
    
    -- 执行信息
    gpu_id          INTEGER,                        -- 分配的 GPU
    worker_id       VARCHAR(100),                   -- 执行的 Worker
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    
    -- 回调配置
    callback_url    VARCHAR(500),
    callback_events VARCHAR(200)[],
    callback_secret VARCHAR(200),
    
    -- 错误信息
    error_type      VARCHAR(100),
    error_message   TEXT,
    
    -- 索引优化字段
    is_completed    BOOLEAN GENERATED ALWAYS AS (status IN ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT')) STORED
);

-- 索引
CREATE INDEX idx_tasks_status ON tasks(status) WHERE NOT is_completed;
CREATE INDEX idx_tasks_priority_created ON tasks(priority, created_at) WHERE status = 'QUEUED';
CREATE INDEX idx_tasks_model ON tasks(model_name);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_gpu ON tasks(gpu_id) WHERE status = 'RUNNING';
```

**状态枚举**：
| 状态 | 说明 |
|------|------|
| PENDING | 待验证 |
| QUEUED | 已入队 |
| ASSIGNED | 已分配 GPU |
| RUNNING | 执行中 |
| COMPLETED | 成功完成 |
| FAILED | 执行失败 |
| CANCELLED | 已取消 |
| TIMEOUT | 超时 |

### 3.2 任务结果表 (task_results)

存储任务执行结果。

```sql
CREATE TABLE task_results (
    task_id         UUID PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    
    -- 结果数据
    result_data     JSONB NOT NULL,                 -- 结构化结果
    output_files    JSONB NOT NULL DEFAULT '{}',    -- 输出文件路径
    
    -- 性能指标
    metrics         JSONB NOT NULL DEFAULT '{}',    -- 执行指标
    duration_seconds FLOAT,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_task_results_created ON task_results(created_at);
```

**result_data 示例**（优化任务）：
```json
{
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
  }
}
```

### 3.3 任务日志表 (task_logs)

存储任务执行过程的详细日志。

```sql
CREATE TABLE task_logs (
    id              BIGSERIAL PRIMARY KEY,
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    
    -- 日志内容
    level           VARCHAR(10) NOT NULL,           -- DEBUG/INFO/WARNING/ERROR
    logger          VARCHAR(100) NOT NULL,          -- 日志来源
    message         TEXT NOT NULL,
    extra           JSONB DEFAULT '{}',             -- 额外信息
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_task_logs_task_id ON task_logs(task_id);
CREATE INDEX idx_task_logs_task_created ON task_logs(task_id, created_at);
CREATE INDEX idx_task_logs_level ON task_logs(level) WHERE level IN ('ERROR', 'WARNING');

-- 分区（按月）
-- 可根据数据量决定是否启用分区
```

### 3.4 结构文件表 (structures)

存储上传的结构文件信息。

```sql
CREATE TABLE structures (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 文件信息
    name            VARCHAR(200) NOT NULL,
    original_name   VARCHAR(200) NOT NULL,          -- 原始文件名
    file_path       VARCHAR(500) NOT NULL,          -- 存储路径
    file_size       INTEGER NOT NULL,               -- 文件大小（字节）
    format          VARCHAR(20) NOT NULL,           -- cif/xyz
    checksum        VARCHAR(64) NOT NULL,           -- SHA256
    
    -- 结构信息
    n_atoms         INTEGER,
    formula         VARCHAR(200),
    space_group     VARCHAR(50),
    
    -- 分类
    is_builtin      BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE,       -- 过期时间（180天）
    
    UNIQUE(checksum)
);

-- 索引
CREATE INDEX idx_structures_name ON structures(name);
CREATE INDEX idx_structures_builtin ON structures(is_builtin);
CREATE INDEX idx_structures_expires ON structures(expires_at) WHERE expires_at IS NOT NULL;
```

### 3.5 模型表 (models)

存储模型信息（包括内置和自定义模型）。

```sql
CREATE TABLE models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 模型信息
    name            VARCHAR(100) NOT NULL UNIQUE,
    display_name    VARCHAR(200),
    framework       VARCHAR(50) NOT NULL,           -- mace/orb/sevennet/...
    description     TEXT,
    
    -- 文件信息
    file_path       VARCHAR(500),                   -- 自定义模型路径
    file_size       INTEGER,
    checksum        VARCHAR(64),
    
    -- 配置
    config          JSONB NOT NULL DEFAULT '{}',    -- 模型配置
    with_d3         BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 分类
    is_custom       BOOLEAN NOT NULL DEFAULT FALSE,
    is_validated    BOOLEAN NOT NULL DEFAULT FALSE, -- 是否验证通过
    
    -- 状态
    is_loaded       BOOLEAN NOT NULL DEFAULT FALSE, -- 是否已加载
    loaded_gpu_id   INTEGER,                        -- 加载到哪个 GPU
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    validated_at    TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_models_framework ON models(framework);
CREATE INDEX idx_models_custom ON models(is_custom);
CREATE INDEX idx_models_loaded ON models(is_loaded) WHERE is_loaded = TRUE;
```

### 3.6 告警规则表 (alert_rules)

存储告警规则配置。

```sql
CREATE TABLE alert_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 规则信息
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    level           VARCHAR(20) NOT NULL,           -- CRITICAL/WARNING/INFO
    
    -- 规则条件
    rule_type       VARCHAR(50) NOT NULL,           -- gpu_memory/gpu_temp/queue_size/...
    condition       JSONB NOT NULL,                 -- 条件配置
    
    -- 通知配置
    notify_channels VARCHAR(50)[] NOT NULL DEFAULT '{}',
    
    -- 状态
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### 3.7 告警记录表 (alerts)

存储告警历史。

```sql
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID REFERENCES alert_rules(id),
    
    -- 告警信息
    level           VARCHAR(20) NOT NULL,
    alert_type      VARCHAR(50) NOT NULL,
    message         TEXT NOT NULL,
    details         JSONB DEFAULT '{}',
    
    -- 状态
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_alerts_level ON alerts(level);
CREATE INDEX idx_alerts_resolved ON alerts(is_resolved) WHERE NOT is_resolved;
CREATE INDEX idx_alerts_created ON alerts(created_at);
```

### 3.8 系统日志表 (system_logs)

存储系统级别日志。

```sql
CREATE TABLE system_logs (
    id              BIGSERIAL PRIMARY KEY,
    
    -- 日志内容
    level           VARCHAR(10) NOT NULL,
    logger          VARCHAR(100) NOT NULL,
    message         TEXT NOT NULL,
    extra           JSONB DEFAULT '{}',
    
    -- 来源
    source          VARCHAR(50),                    -- api/worker/scheduler/...
    request_id      VARCHAR(50),
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_system_logs_level ON system_logs(level);
CREATE INDEX idx_system_logs_created ON system_logs(created_at);
CREATE INDEX idx_system_logs_request ON system_logs(request_id) WHERE request_id IS NOT NULL;

-- 按月分区（可选）
```

### 3.9 API Key 表 (api_keys)

存储 API 密钥（虽然不需要用户系统，但需要认证）。

```sql
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Key 信息
    key_hash        VARCHAR(64) NOT NULL UNIQUE,    -- SHA256(api_key)
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    
    -- 权限
    permissions     VARCHAR(50)[] NOT NULL DEFAULT '{"read", "write"}',
    
    -- 限制
    rate_limit      INTEGER DEFAULT 100,            -- 每分钟请求数
    
    -- 状态
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMP WITH TIME ZONE,
    expires_at      TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
```

---

## 四、数据保留策略

| 表 | 保留策略 | 清理方式 |
|---|---------|---------|
| tasks | 永久 | - |
| task_results | 180 天 | 定期归档 |
| task_logs | 永久 | 按月分区 |
| structures | 180 天（自定义）/ 永久（内置） | 定期清理 |
| models | 永久 | 手动删除 |
| alerts | 1 年 | 定期归档 |
| system_logs | 永久 | 按月分区 |

---

## 五、性能优化

### 5.1 索引策略

- 任务查询：复合索引 (status, priority, created_at)
- 日志查询：分区 + 索引 (task_id, created_at)
- 告警查询：索引 (is_resolved, created_at)

### 5.2 分区策略

大表按时间分区：
- `task_logs`: 按月分区
- `system_logs`: 按月分区
- `alerts`: 按月分区

### 5.3 连接池配置

```python
# SQLAlchemy 连接池配置
SQLALCHEMY_DATABASE_URL = "postgresql://user:pass@localhost/mofsim"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)
```

---

## 六、备份策略

| 备份类型 | 频率 | 保留期 |
|---------|------|--------|
| 全量备份 | 每日 | 30 天 |
| 增量备份 | 每小时 | 7 天 |
| WAL 归档 | 实时 | 7 天 |

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
