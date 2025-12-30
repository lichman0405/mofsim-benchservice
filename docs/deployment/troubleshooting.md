# 故障排除指南

## 一、概述

本文档提供 MOFSimBench 常见问题的诊断和解决方案。

---

## 二、快速诊断

### 2.1 系统健康检查

```bash
#!/bin/bash
# health_check.sh

echo "=== 服务状态 ==="
docker-compose -f docker-compose.production.yml ps

echo "=== API 健康 ==="
curl -s http://localhost:8000/health | jq .

echo "=== 数据库连接 ==="
docker-compose exec postgres pg_isready

echo "=== Redis 连接 ==="
docker-compose exec redis redis-cli ping

echo "=== GPU 状态 ==="
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv

echo "=== 磁盘空间 ==="
df -h /data

echo "=== 内存使用 ==="
free -h
```

### 2.2 问题分类

| 症状 | 可能原因 | 章节 |
|------|---------|------|
| API 无响应 | 服务崩溃、端口占用 | §3.1 |
| 任务不执行 | Worker 故障、队列阻塞 | §4.1 |
| 任务失败 | 模型错误、内存不足 | §4.2 |
| GPU 错误 | 驱动问题、显存不足 | §5 |
| 数据库错误 | 连接池满、磁盘满 | §6 |

---

## 三、API 问题

### 3.1 API 无响应

**症状**：访问 API 超时或返回 502/503

**诊断**：

```bash
# 检查容器状态
docker-compose ps api

# 查看日志
docker-compose logs --tail=100 api

# 检查端口
ss -tlnp | grep 8000
```

**解决方案**：

```bash
# 重启 API
docker-compose restart api

# 如果端口被占用
fuser -k 8000/tcp
docker-compose up -d api

# 如果内存不足
docker-compose down api
docker system prune -f
docker-compose up -d api
```

### 3.2 认证失败

**症状**：返回 401 Unauthorized 或 403 Forbidden

**诊断**：

```bash
# 验证 API Key
curl -v -H "Authorization: Bearer <your_key>" http://localhost:8000/api/v1/tasks

# 检查数据库中的 API Key
docker-compose exec postgres psql -U mofsim -d mofsim -c "SELECT id, name, is_active FROM api_keys;"
```

**解决方案**：

```bash
# 重新生成 API Key
docker-compose exec api python -m scripts.generate_api_key --name "admin"

# 激活已存在的 Key
docker-compose exec postgres psql -U mofsim -d mofsim -c "UPDATE api_keys SET is_active = true WHERE name = 'admin';"
```

### 3.3 请求超时

**症状**：大文件上传或长任务查询超时

**解决方案**：

调整 Nginx 超时设置：

```nginx
location /api/ {
    proxy_connect_timeout 300s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    client_max_body_size 100M;
}
```

---

## 四、任务问题

### 4.1 任务不执行

**症状**：任务状态一直是 PENDING 或 QUEUED

**诊断**：

```bash
# 检查 Worker 状态
docker-compose ps | grep worker

# 检查 Worker 日志
docker-compose logs --tail=50 worker-gpu0

# 检查队列
redis-cli LLEN mofsim:queue:gpu-0

# 检查 Celery
docker-compose exec worker-gpu0 celery -A workers.celery_app inspect active
```

**解决方案**：

```bash
# 重启 Worker
docker-compose restart worker-gpu0 worker-gpu1 ...

# 清理卡住的任务
redis-cli DEL mofsim:queue:gpu-0

# 重新调度任务
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/reschedule
```

### 4.2 任务失败

**症状**：任务状态变为 FAILED

**诊断**：

```bash
# 查看任务详情
curl http://localhost:8000/api/v1/tasks/{task_id}

# 查看任务日志
curl http://localhost:8000/api/v1/tasks/{task_id}/logs

# 查看完整错误
docker-compose logs worker-gpu0 | grep {task_id}
```

**常见错误及解决方案**：

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `CUDA out of memory` | GPU 显存不足 | 减少批量大小、使用更小的模型 |
| `Model not found` | 模型未加载 | 检查模型配置、重新加载模型 |
| `Invalid structure` | 结构文件格式错误 | 验证 CIF 文件、检查原子坐标 |
| `Timeout` | 计算超时 | 增加超时时间、优化参数 |

### 4.3 任务卡住

**症状**：任务状态是 RUNNING 但长时间无进展

**诊断**：

```bash
# 检查 GPU 使用
nvidia-smi pmon -s um

# 检查进程
ps aux | grep python

# 检查任务日志
tail -f /var/log/mofsim/tasks/{task_id}.log
```

**解决方案**：

```bash
# 强制取消任务
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/force-cancel

# 杀死僵尸进程
kill -9 <pid>

# 重启对应的 Worker
docker-compose restart worker-gpu0
```

---

## 五、GPU 问题

### 5.1 GPU 不可用

**症状**：`CUDA is not available` 或无法检测到 GPU

**诊断**：

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi
```

**解决方案**：

```bash
# 重新加载 NVIDIA 驱动
sudo rmmod nvidia_uvm nvidia
sudo modprobe nvidia nvidia_uvm

# 重启 Docker
sudo systemctl restart docker

# 重启 Worker
docker-compose restart worker-gpu0
```

### 5.2 GPU 显存不足

**症状**：`CUDA out of memory` 错误

**诊断**：

```bash
# 查看显存使用
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# 查看 GPU 进程
nvidia-smi pmon -s um
```

**解决方案**：

```bash
# 清理 GPU 内存
fuser -v /dev/nvidia*

# 杀死占用显存的进程
kill -9 <pid>

# 调整任务参数
# 减少批量大小、使用较小的模型、启用混合精度
```

### 5.3 GPU 计算错误

**症状**：`CUDA error`、`cuBLAS error`

**诊断**：

```bash
# 检查 GPU 健康
nvidia-smi -q | grep "Gpu"

# 检查温度
nvidia-smi --query-gpu=temperature.gpu --format=csv
```

**解决方案**：

```bash
# 重置 GPU
nvidia-smi --gpu-reset -i 0

# 检查散热
# 如果温度过高（>85°C），需要检查散热系统

# 降低功耗限制
nvidia-smi -pl 250
```

---

## 六、数据库问题

### 6.1 连接失败

**症状**：`Connection refused` 或 `too many connections`

**诊断**：

```bash
# 检查 PostgreSQL 状态
docker-compose exec postgres pg_isready

# 查看连接数
docker-compose exec postgres psql -U mofsim -c "SELECT count(*) FROM pg_stat_activity;"
```

**解决方案**：

```bash
# 重启 PostgreSQL
docker-compose restart postgres

# 增加连接数限制
# 在 postgresql.conf 中：
# max_connections = 200

# 清理空闲连接
docker-compose exec postgres psql -U mofsim -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE state = 'idle' AND query_start < now() - interval '1 hour';
"
```

### 6.2 磁盘空间不足

**症状**：`No space left on device`

**诊断**：

```bash
df -h
du -sh /var/lib/docker/volumes/*
```

**解决方案**：

```bash
# 清理 PostgreSQL 日志
docker-compose exec postgres sh -c "rm -f /var/log/postgresql/*.log"

# 执行 VACUUM
docker-compose exec postgres psql -U mofsim -d mofsim -c "VACUUM FULL;"

# 删除旧数据
docker-compose exec postgres psql -U mofsim -d mofsim -c "
    DELETE FROM task_logs WHERE created_at < NOW() - INTERVAL '90 days';
"
```

### 6.3 查询缓慢

**症状**：API 响应慢、数据库 CPU 高

**诊断**：

```bash
# 查看慢查询
docker-compose exec postgres psql -U mofsim -d mofsim -c "
    SELECT query, calls, mean_time 
    FROM pg_stat_statements 
    ORDER BY mean_time DESC 
    LIMIT 10;
"
```

**解决方案**：

```bash
# 更新统计信息
docker-compose exec postgres psql -U mofsim -d mofsim -c "ANALYZE;"

# 重建索引
docker-compose exec postgres psql -U mofsim -d mofsim -c "REINDEX DATABASE mofsim;"
```

---

## 七、Redis 问题

### 7.1 连接失败

**症状**：`Connection refused` 或 `Connection reset`

**诊断**：

```bash
# 检查 Redis 状态
docker-compose exec redis redis-cli ping

# 查看 Redis 日志
docker-compose logs --tail=50 redis
```

**解决方案**：

```bash
# 重启 Redis
docker-compose restart redis

# 检查内存
docker-compose exec redis redis-cli info memory
```

### 7.2 内存不足

**症状**：`OOM command not allowed`

**解决方案**：

```bash
# 清理过期数据
docker-compose exec redis redis-cli --scan --pattern "mofsim:*" | xargs redis-cli del

# 增加内存限制
# 在 redis.conf 中：
# maxmemory 8gb
# maxmemory-policy volatile-lru
```

---

## 八、网络问题

### 8.1 DNS 解析失败

**症状**：无法访问外部服务

**解决方案**：

```bash
# 检查 DNS
docker-compose exec api nslookup google.com

# 使用自定义 DNS
# 在 docker-compose.yml 中添加：
# dns:
#   - 8.8.8.8
#   - 8.8.4.4
```

### 8.2 容器间通信失败

**症状**：服务之间无法连接

**诊断**：

```bash
# 检查网络
docker network ls
docker network inspect mofsim-bench_default
```

**解决方案**：

```bash
# 重建网络
docker-compose down
docker network prune
docker-compose up -d
```

---

## 九、日志分析

### 9.1 常见错误模式

```bash
# 查找错误
grep -i "error\|exception\|failed" /var/log/mofsim/api.log | tail -20

# 统计错误类型
grep -oP '"error_type": "\K[^"]+' /var/log/mofsim/api.log | sort | uniq -c | sort -rn

# 查找特定时间段的错误
grep "2024-01-15" /var/log/mofsim/api.log | grep -i error
```

### 9.2 性能分析

```bash
# API 响应时间分析
grep -oP '"response_time_ms": \K[0-9.]+' /var/log/mofsim/api.log | \
  awk '{sum+=$1; count++} END {print "平均响应时间:", sum/count, "ms"}'

# 任务执行时间分析
grep "task_completed" /var/log/mofsim/worker.log | \
  grep -oP '"duration_seconds": \K[0-9.]+' | \
  awk '{sum+=$1; count++} END {print "平均任务时间:", sum/count, "s"}'
```

---

## 十、获取帮助

如果上述方法无法解决问题：

1. 收集诊断信息：

```bash
./scripts/collect_diagnostics.sh > diagnostics.tar.gz
```

2. 提交 Issue：https://github.com/AI4ChemS/mofsim-bench/issues

3. 联系支持：support@example.com

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
