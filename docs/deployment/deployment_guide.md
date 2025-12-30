# 部署指南

## 一、概述

本文档指导如何部署 MOFSimBench 服务到生产环境。

---

## 二、部署架构

```
┌─────────────────────────────────────────────────────────────┐
│                         服务器                               │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Nginx      │  │   API        │  │   Prometheus     │   │
│  │   (反向代理)  │→ │   Container  │  │   + Grafana      │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│           │                │                   │            │
│           ▼                ▼                   ▼            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Redis      │  │  PostgreSQL  │  │   Loki           │   │
│  │   Container  │  │  Container   │  │   (日志收集)      │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   GPU Workers (8x)                    │   │
│  │   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │   │
│  │   │GPU 0   │ │GPU 1   │ │GPU 2   │ │GPU 3   │        │   │
│  │   └────────┘ └────────┘ └────────┘ └────────┘        │   │
│  │   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │   │
│  │   │GPU 4   │ │GPU 5   │ │GPU 6   │ │GPU 7   │        │   │
│  │   └────────┘ └────────┘ └────────┘ └────────┘        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、系统要求

### 3.1 硬件要求

| 组件 | 规格 |
|------|------|
| CPU | 32+ 核（推荐 AMD EPYC / Intel Xeon） |
| 内存 | 256GB+ |
| GPU | 8 × NVIDIA RTX 3090 (24GB VRAM) |
| 存储 | 2TB+ SSD (NVMe 推荐) |
| 网络 | 1Gbps+ |

### 3.2 软件要求

| 软件 | 版本 |
|------|------|
| Ubuntu | 22.04 LTS |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| NVIDIA Driver | 535+ |
| NVIDIA Container Toolkit | 1.14+ |
| CUDA | 11.8+ |

---

## 四、环境准备

### 4.1 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 4.2 安装 NVIDIA Container Toolkit

```bash
# 添加仓库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 安装
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 4.3 验证 GPU

```bash
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
```

---

## 五、部署步骤

### 5.1 获取代码

```bash
git clone https://github.com/AI4ChemS/mofsim-bench.git
cd mofsim-bench
```

### 5.2 配置环境变量

创建 `.env.production`:

```env
# 数据库
POSTGRES_USER=mofsim
POSTGRES_PASSWORD=<强密码>
POSTGRES_DB=mofsim
DATABASE_URL=postgresql://mofsim:<密码>@postgres:5432/mofsim

# Redis
REDIS_URL=redis://redis:6379/0

# API
SECRET_KEY=<生成的密钥>
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# GPU 配置
GPU_IDS=0,1,2,3,4,5,6,7
WORKERS_PER_GPU=1

# 日志
LOG_LEVEL=INFO
LOG_DIR=/var/log/mofsim

# 存储
DATA_DIR=/data/mofsim
STRUCTURE_DIR=/data/mofsim/structures
RESULT_DIR=/data/mofsim/results
MODEL_DIR=/data/mofsim/models

# 告警
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=admin@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=<用户名>
SMTP_PASSWORD=<密码>
```

### 5.3 创建数据目录

```bash
sudo mkdir -p /data/mofsim/{structures,results,models,logs}
sudo chown -R $USER:$USER /data/mofsim
```

### 5.4 Docker Compose 配置

`docker-compose.production.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15
    container_name: mofsim-postgres
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7-alpine
    container_name: mofsim-redis
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # API 服务
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: mofsim-api
    restart: always
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - LOG_LEVEL=${LOG_LEVEL}
    ports:
      - "8000:8000"
    volumes:
      - ${DATA_DIR}:/data
      - ${LOG_DIR}:/var/log/mofsim
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # GPU Workers
  worker-gpu0:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    container_name: mofsim-worker-gpu0
    restart: always
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - CUDA_VISIBLE_DEVICES=0
      - CELERY_QUEUES=gpu-0
    volumes:
      - ${DATA_DIR}:/data
      - ${LOG_DIR}:/var/log/mofsim
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
    depends_on:
      - redis
      - postgres

  # 为每个 GPU 重复 worker 配置...
  worker-gpu1:
    extends:
      service: worker-gpu0
    container_name: mofsim-worker-gpu1
    environment:
      - CUDA_VISIBLE_DEVICES=1
      - CELERY_QUEUES=gpu-1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]

  # ... worker-gpu2 到 worker-gpu7 ...

  # Celery Beat（定时任务）
  beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    container_name: mofsim-beat
    restart: always
    command: celery -A workers.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    volumes:
      - ${LOG_DIR}:/var/log/mofsim
    depends_on:
      - redis
      - postgres

  # Prometheus
  prometheus:
    image: prom/prometheus:v2.47.0
    container_name: mofsim-prometheus
    restart: always
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  # Grafana
  grafana:
    image: grafana/grafana:10.1.0
    container_name: mofsim-grafana
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: mofsim-nginx
    restart: always
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/ssl:/etc/nginx/ssl
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### 5.5 启动服务

```bash
# 构建镜像
docker-compose -f docker-compose.production.yml build

# 启动服务
docker-compose -f docker-compose.production.yml up -d

# 查看日志
docker-compose -f docker-compose.production.yml logs -f

# 初始化数据库
docker-compose -f docker-compose.production.yml exec api alembic upgrade head
docker-compose -f docker-compose.production.yml exec api python scripts/init_db.py
```

---

## 六、Nginx 配置

`docker/nginx/nginx.conf`:

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    # HTTP 重定向到 HTTPS
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS
    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

        # API
        location /api/ {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # 超时设置
            proxy_connect_timeout 60s;
            proxy_read_timeout 300s;
        }

        # WebSocket（如果需要）
        location /ws/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        # 健康检查
        location /health {
            proxy_pass http://api;
        }
    }
}
```

---

## 七、验证部署

### 7.1 检查服务状态

```bash
# 查看容器状态
docker-compose -f docker-compose.production.yml ps

# 检查 API
curl http://localhost:8000/health

# 检查 GPU Workers
curl http://localhost:8000/api/v1/system/gpus
```

### 7.2 运行测试任务

```bash
# 提交测试任务
curl -X POST http://localhost:8000/api/v1/tasks/optimization \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mace_off_prod",
    "structure": {"source": "builtin", "name": "MOF-5_primitive"},
    "parameters": {"fmax": 0.01, "max_steps": 10}
  }'
```

---

## 八、生产优化

### 8.1 数据库优化

```sql
-- PostgreSQL 性能调优
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
```

### 8.2 Redis 优化

```conf
# redis.conf
maxmemory 8gb
maxmemory-policy volatile-lru
```

### 8.3 Worker 优化

```python
# celery_config.py
task_acks_late = True
worker_prefetch_multiplier = 1
task_reject_on_worker_lost = True
```

---

## 九、故障恢复

### 9.1 服务重启

```bash
# 重启所有服务
docker-compose -f docker-compose.production.yml restart

# 重启特定服务
docker-compose -f docker-compose.production.yml restart api worker-gpu0
```

### 9.2 数据恢复

```bash
# 从备份恢复 PostgreSQL
docker-compose -f docker-compose.production.yml exec postgres \
  pg_restore -U mofsim -d mofsim /backup/mofsim_backup.dump
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
