# 配置参考

## 一、概述

本文档列出 MOFSimBench 的所有可配置项及其说明。

---

## 二、环境变量

### 2.1 必需变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT 签名密钥 | 随机 32 字节 hex |

### 2.2 API 配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `API_HOST` | `0.0.0.0` | API 监听地址 |
| `API_PORT` | `8000` | API 监听端口 |
| `API_WORKERS` | `4` | Uvicorn worker 数量 |
| `API_RELOAD` | `false` | 是否启用热重载 |
| `CORS_ORIGINS` | `*` | 允许的 CORS 来源 |

### 2.3 GPU 配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GPU_IDS` | `0,1,2,3,4,5,6,7` | 可用 GPU ID 列表 |
| `WORKERS_PER_GPU` | `1` | 每个 GPU 的 Worker 数量 |
| `GPU_MEMORY_RESERVE_MB` | `2000` | 预留显存（MB） |

### 2.4 存储配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATA_DIR` | `/data/mofsim` | 数据根目录 |
| `STRUCTURE_DIR` | `${DATA_DIR}/structures` | 结构文件目录 |
| `RESULT_DIR` | `${DATA_DIR}/results` | 结果文件目录 |
| `MODEL_DIR` | `${DATA_DIR}/models` | 模型文件目录 |
| `LOG_DIR` | `/var/log/mofsim` | 日志目录 |

### 2.5 日志配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FORMAT` | `json` | 日志格式 (json/text) |
| `LOG_RETENTION_DAYS` | `180` | 日志保留天数 |

### 2.6 告警配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `ALERT_EMAIL_ENABLED` | `false` | 启用邮件告警 |
| `ALERT_EMAIL_TO` | - | 告警邮箱 |
| `SMTP_HOST` | - | SMTP 服务器 |
| `SMTP_PORT` | `587` | SMTP 端口 |
| `SMTP_USER` | - | SMTP 用户名 |
| `SMTP_PASSWORD` | - | SMTP 密码 |
| `ALERT_WEBHOOK_URL` | - | Webhook 告警 URL |

---

## 三、配置文件

### 3.1 主配置文件

`config/settings.yaml`:

```yaml
# 服务器配置
server:
  host: ${API_HOST:0.0.0.0}
  port: ${API_PORT:8000}
  workers: ${API_WORKERS:4}
  debug: ${DEBUG:false}

# 数据库配置
database:
  url: ${DATABASE_URL}
  pool_size: 20
  max_overflow: 10
  pool_recycle: 3600
  echo: false

# Redis 配置
redis:
  url: ${REDIS_URL}
  max_connections: 100

# 调度器配置
scheduler:
  gpu_ids: ${GPU_IDS:[0,1,2,3,4,5,6,7]}
  poll_interval_ms: 100
  task_timeout_seconds: 86400
  max_retries: 3
  
  priority_weights:
    CRITICAL: 1000
    HIGH: 100
    NORMAL: 10
    LOW: 1

# 日志配置
logging:
  level: ${LOG_LEVEL:INFO}
  format: ${LOG_FORMAT:json}
  
  file:
    enabled: true
    path: ${LOG_DIR}/app.log
    rotation: "100 MB"
    retention: ${LOG_RETENTION_DAYS:180}
  
  structured:
    include_timestamp: true
    include_level: true
    include_logger: true

# 告警配置
alerts:
  enabled: true
  
  rules:
    - name: task_failure_rate
      condition: "failure_rate > 0.1"
      severity: warning
      
    - name: gpu_memory_high
      condition: "gpu_memory_usage > 0.9"
      severity: warning
      
    - name: queue_backlog
      condition: "queue_size > 100"
      severity: warning
  
  channels:
    email:
      enabled: ${ALERT_EMAIL_ENABLED:false}
      to: ${ALERT_EMAIL_TO}
      
    webhook:
      enabled: ${ALERT_WEBHOOK_URL:}
      url: ${ALERT_WEBHOOK_URL}

# 安全配置
security:
  jwt:
    secret: ${SECRET_KEY}
    algorithm: HS256
    expire_minutes: 43200
  
  api_keys:
    enabled: true
    header: Authorization
    prefix: Bearer

# 存储配置
storage:
  structures:
    path: ${STRUCTURE_DIR}
    max_file_size_mb: 50
    allowed_formats: [cif, xyz, poscar, vasp]
  
  results:
    path: ${RESULT_DIR}
    retention_days: 180
  
  models:
    path: ${MODEL_DIR}
    max_file_size_mb: 5000
```

### 3.2 模型配置

`mof_benchmark/setup/calculators.yaml`:

```yaml
# MACE 模型
mace_off_prod:
  type: mace
  name: "MACE-OFF Production"
  model: "large"
  default_dtype: float64
  dispersion: true
  resources:
    memory_mb: 8000
    
mace_mpa_prod:
  type: mace
  name: "MACE-MPA Production"
  model: "mpa-medium"
  default_dtype: float64
  resources:
    memory_mb: 6000

# ORB 模型
orb_v2_prod:
  type: orb
  name: "ORB v2 Production"
  model: orb-v2
  resources:
    memory_mb: 10000

# OMAT24 模型
omat24_prod:
  type: omat24
  name: "OMAT24 Production"
  checkpoint: /models/omat24/checkpoint.pt
  resources:
    memory_mb: 12000

# GRACE 模型
grace_2l_oat_prod:
  type: grace
  name: "GRACE-2L-OAT Production"
  resources:
    memory_mb: 8000

# MatterSim 模型
mattersim_prod:
  type: mattersim
  name: "MatterSim Production"
  resources:
    memory_mb: 10000

# SevenNet 模型
7net_prod:
  type: sevenn
  name: "SevenNet Production"
  resources:
    memory_mb: 8000

# MatGL 模型
matgl_prod:
  type: matgl
  name: "MatGL Production"
  resources:
    memory_mb: 6000
```

### 3.3 任务参数默认值

`config/task_defaults.yaml`:

```yaml
optimization:
  fmax: 0.001
  max_steps: 500
  optimizer: LBFGS
  trajectory_interval: 10

stability:
  temperature_k: 300
  timestep_fs: 1.0
  total_steps: 1000
  equilibration_steps: 100

bulk_modulus:
  strain_range: 0.05
  num_points: 5
  fitting_method: birch_murnaghan

heat_capacity:
  temperature_range: [100, 500]
  temperature_step: 50
  supercell: [2, 2, 2]

interaction_energy:
  adsorbate: CO2
  grid_spacing: 0.5
```

---

## 四、Docker 配置

### 4.1 API Dockerfile

`docker/Dockerfile.api`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[server]"

# 复制代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Worker Dockerfile

`docker/Dockerfile.worker`:

```dockerfile
FROM nvidia/cuda:11.8-runtime-ubuntu22.04

WORKDIR /app

# 安装 Python
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[worker]"

# 复制代码
COPY . .

# 启动
CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info"]
```

---

## 五、Celery 配置

`workers/celery_config.py`:

```python
# Broker 设置
broker_url = os.getenv("REDIS_URL")
result_backend = os.getenv("DATABASE_URL")

# 任务设置
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# 队列设置
task_queues = {
    f'gpu-{i}': {'routing_key': f'gpu.{i}'}
    for i in range(8)
}

# 并发设置
worker_concurrency = 1
worker_prefetch_multiplier = 1

# 可靠性设置
task_acks_late = True
task_reject_on_worker_lost = True
task_track_started = True

# 超时设置
task_time_limit = 86400  # 24 小时
task_soft_time_limit = 82800  # 23 小时

# 结果设置
result_expires = 604800  # 7 天

# 定时任务
beat_schedule = {
    'cleanup-expired-results': {
        'task': 'workers.tasks.maintenance.cleanup_expired_results',
        'schedule': crontab(hour=2, minute=0),
    },
    'check-stalled-tasks': {
        'task': 'workers.tasks.maintenance.check_stalled_tasks',
        'schedule': crontab(minute='*/5'),
    },
    'update-gpu-stats': {
        'task': 'workers.tasks.monitoring.update_gpu_stats',
        'schedule': 60.0,
    },
}
```

---

## 六、Prometheus 配置

`docker/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'mofsim-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'nvidia-gpu'
    static_configs:
      - targets: ['nvidia-exporter:9400']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/rules/*.yml
```

---

## 七、配置验证

```bash
# 验证配置文件
python -m config.validator

# 输出当前配置
python -m config.show

# 检查环境变量
python -m config.check_env
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
