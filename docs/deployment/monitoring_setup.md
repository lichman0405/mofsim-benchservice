# 监控配置指南

## 一、概述

本文档描述如何配置 MOFSimBench 的监控系统。

---

## 二、监控架构

```
┌────────────────────────────────────────────────────────────┐
│                    Grafana Dashboard                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 系统指标 │  │ GPU 指标 │  │ 任务指标 │  │ 告警面板 │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌───────────────────────────────────────────────────────────┐
│                      Prometheus                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   时序数据存储                       │  │
│  └─────────────────────────────────────────────────────┘  │
└───────┬─────────────┬─────────────┬─────────────┬─────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
   Node Exporter  NVIDIA Exporter  API Metrics  Redis Exporter
```

---

## 三、Prometheus 配置

### 3.1 基础配置

`docker/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'mofsim-prod'
    env: 'production'

# 告警配置
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

# 规则文件
rule_files:
  - /etc/prometheus/rules/alerts.yml
  - /etc/prometheus/rules/recording.yml

# 抓取配置
scrape_configs:
  # API 服务指标
  - job_name: 'mofsim-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  # 系统指标
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # GPU 指标
  - job_name: 'nvidia-gpu'
    static_configs:
      - targets: ['nvidia-exporter:9400']

  # Redis 指标
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # PostgreSQL 指标
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Celery 指标
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9808']
```

### 3.2 告警规则

`docker/prometheus/rules/alerts.yml`:

```yaml
groups:
  - name: mofsim-alerts
    rules:
      # API 可用性
      - alert: APIDown
        expr: up{job="mofsim-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API 服务不可用"
          description: "API 服务已停止响应超过 1 分钟"

      # API 响应时间
      - alert: APIHighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API 响应时间过长"
          description: "95% 请求响应时间超过 5 秒"

      # GPU 显存使用
      - alert: GPUMemoryHigh
        expr: (nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "GPU 显存使用率过高"
          description: "GPU {{ $labels.gpu }} 显存使用超过 90%"

      # GPU 温度
      - alert: GPUTemperatureHigh
        expr: nvidia_gpu_temperature_celsius > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "GPU 温度过高"
          description: "GPU {{ $labels.gpu }} 温度超过 85°C"

      # 任务队列积压
      - alert: TaskQueueBacklog
        expr: mofsim_queue_size > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "任务队列积压"
          description: "待处理任务超过 100 个"

      # 任务失败率
      - alert: HighTaskFailureRate
        expr: rate(mofsim_tasks_failed_total[5m]) / rate(mofsim_tasks_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "任务失败率过高"
          description: "最近 5 分钟任务失败率超过 10%"

      # 磁盘空间
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{mountpoint="/data"} / node_filesystem_size_bytes{mountpoint="/data"}) < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "磁盘空间不足"
          description: "/data 剩余空间不足 10%"

      # 内存使用
      - alert: MemoryHigh
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "内存使用率过高"
          description: "系统内存使用超过 90%"

      # Worker 不可用
      - alert: WorkerDown
        expr: up{job="celery"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Worker 不可用"
          description: "Celery Worker 已停止响应"
```

### 3.3 记录规则

`docker/prometheus/rules/recording.yml`:

```yaml
groups:
  - name: mofsim-recording
    rules:
      # 任务吞吐量
      - record: mofsim:tasks_per_minute
        expr: rate(mofsim_tasks_completed_total[1m]) * 60

      # 平均任务时间
      - record: mofsim:avg_task_duration_seconds
        expr: rate(mofsim_task_duration_seconds_sum[5m]) / rate(mofsim_task_duration_seconds_count[5m])

      # GPU 使用率
      - record: mofsim:gpu_utilization_avg
        expr: avg(nvidia_gpu_utilization_percent)

      # API 成功率
      - record: mofsim:api_success_rate
        expr: sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m]))
```

---

## 四、Grafana 配置

### 4.1 数据源配置

`docker/grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### 4.2 仪表板配置

`docker/grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: 'MOFSimBench'
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

### 4.3 主仪表板

`docker/grafana/provisioning/dashboards/main.json`:

```json
{
  "dashboard": {
    "title": "MOFSimBench Overview",
    "panels": [
      {
        "title": "任务统计",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {"expr": "sum(mofsim_tasks_total)", "legendFormat": "总任务数"}
        ]
      },
      {
        "title": "GPU 使用率",
        "type": "gauge",
        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
        "targets": [
          {"expr": "avg(nvidia_gpu_utilization_percent)", "legendFormat": "平均使用率"}
        ]
      },
      {
        "title": "任务队列",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 4, "w": 12, "h": 6},
        "targets": [
          {"expr": "mofsim_queue_size", "legendFormat": "队列大小"}
        ]
      },
      {
        "title": "GPU 显存使用",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 10, "w": 12, "h": 6},
        "targets": [
          {"expr": "nvidia_gpu_memory_used_bytes / 1024 / 1024 / 1024", "legendFormat": "GPU {{gpu}}"}
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "decgbytes"
          }
        }
      }
    ]
  }
}
```

---

## 五、应用指标

### 5.1 API 指标

在 FastAPI 中暴露指标：

```python
# api/metrics.py

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response

# 请求计数
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 响应时间
http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# 任务指标
tasks_total = Counter(
    'mofsim_tasks_total',
    'Total tasks submitted',
    ['task_type', 'model']
)

tasks_completed = Counter(
    'mofsim_tasks_completed_total',
    'Total tasks completed',
    ['task_type', 'model']
)

tasks_failed = Counter(
    'mofsim_tasks_failed_total',
    'Total tasks failed',
    ['task_type', 'model', 'error_type']
)

task_duration = Histogram(
    'mofsim_task_duration_seconds',
    'Task execution duration',
    ['task_type', 'model'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

# 队列大小
queue_size = Gauge(
    'mofsim_queue_size',
    'Number of tasks in queue',
    ['queue']
)

# GPU 状态
gpu_status = Gauge(
    'mofsim_gpu_status',
    'GPU status (0=free, 1=busy, 2=error)',
    ['gpu_id']
)

async def metrics():
    """返回 Prometheus 指标"""
    return Response(
        content=generate_latest(),
        media_type='text/plain'
    )
```

### 5.2 中间件

```python
# api/middleware/metrics.py

import time
from starlette.middleware.base import BaseHTTPMiddleware

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        http_request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response
```

---

## 六、NVIDIA GPU Exporter

### 6.1 Docker 配置

```yaml
# docker-compose 中添加
nvidia-exporter:
  image: utkuozdemir/nvidia_gpu_exporter:1.1.0
  container_name: nvidia-exporter
  restart: always
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
  ports:
    - "9400:9400"
```

### 6.2 可用指标

| 指标 | 说明 |
|------|------|
| `nvidia_gpu_utilization_percent` | GPU 使用率 |
| `nvidia_gpu_memory_used_bytes` | 已用显存 |
| `nvidia_gpu_memory_total_bytes` | 总显存 |
| `nvidia_gpu_temperature_celsius` | GPU 温度 |
| `nvidia_gpu_power_usage_watts` | 功耗 |

---

## 七、Alertmanager 配置

`docker/alertmanager/alertmanager.yml`:

```yaml
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alerts@mofsim.example.com'
  smtp_auth_username: 'alerts@mofsim.example.com'
  smtp_auth_password: 'password'

route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    - match:
        severity: critical
      receiver: 'critical'
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@example.com'

  - name: 'critical'
    email_configs:
      - to: 'oncall@example.com'
    webhook_configs:
      - url: 'https://hooks.slack.com/services/xxx'

  - name: 'warning'
    email_configs:
      - to: 'ops@example.com'
```

---

## 八、日志收集

### 8.1 Loki 配置

```yaml
# docker-compose 中添加
loki:
  image: grafana/loki:2.9.0
  container_name: loki
  ports:
    - "3100:3100"
  volumes:
    - ./docker/loki/config.yml:/etc/loki/config.yml
    - loki_data:/loki
  command: -config.file=/etc/loki/config.yml

promtail:
  image: grafana/promtail:2.9.0
  container_name: promtail
  volumes:
    - /var/log/mofsim:/var/log/mofsim:ro
    - ./docker/promtail/config.yml:/etc/promtail/config.yml
  command: -config.file=/etc/promtail/config.yml
```

### 8.2 Promtail 配置

`docker/promtail/config.yml`:

```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: mofsim
    static_configs:
      - targets:
          - localhost
        labels:
          job: mofsim
          __path__: /var/log/mofsim/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            task_id: task_id
      - labels:
          level:
          task_id:
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
