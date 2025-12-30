# 运维手册

## 一、概述

本文档提供 MOFSimBench 服务的日常运维指南。

---

## 二、服务管理

### 2.1 服务启停

```bash
# 启动所有服务
docker-compose -f docker-compose.production.yml up -d

# 停止所有服务
docker-compose -f docker-compose.production.yml down

# 重启服务
docker-compose -f docker-compose.production.yml restart

# 重启特定服务
docker-compose -f docker-compose.production.yml restart api
docker-compose -f docker-compose.production.yml restart worker-gpu0
```

### 2.2 查看服务状态

```bash
# 查看容器状态
docker-compose -f docker-compose.production.yml ps

# 查看容器资源使用
docker stats

# 查看服务日志
docker-compose -f docker-compose.production.yml logs -f api
docker-compose -f docker-compose.production.yml logs -f worker-gpu0
```

### 2.3 扩缩容

```bash
# 增加 API worker
docker-compose -f docker-compose.production.yml up -d --scale api=2

# 注意：GPU Worker 不支持自动扩缩，需要手动配置
```

---

## 三、监控

### 3.1 系统监控

**CPU 和内存**:

```bash
# 实时监控
htop

# 历史查看
sar -u 1 10  # CPU
sar -r 1 10  # 内存
```

**磁盘**:

```bash
# 磁盘使用
df -h

# IO 监控
iostat -x 1
```

**网络**:

```bash
# 网络连接
ss -tuln

# 网络流量
iftop
```

### 3.2 GPU 监控

```bash
# 实时 GPU 状态
nvidia-smi

# 持续监控
watch -n 1 nvidia-smi

# 详细信息
nvidia-smi -q

# GPU 进程
nvidia-smi pmon -s um
```

### 3.3 应用监控

**API 健康检查**:

```bash
curl http://localhost:8000/health
```

**队列状态**:

```bash
# 查看队列长度
redis-cli LLEN mofsim:queue:gpu-0

# 查看所有队列
redis-cli KEYS "mofsim:queue:*"
```

**任务统计**:

```bash
curl http://localhost:8000/api/v1/system/stats
```

### 3.4 Grafana 仪表板

访问 `http://your-server:3000` 查看：

- 系统资源使用
- GPU 使用率
- 任务统计
- API 响应时间
- 错误率

---

## 四、日志管理

### 4.1 日志位置

| 日志类型 | 位置 |
|---------|------|
| API 日志 | `/var/log/mofsim/api.log` |
| Worker 日志 | `/var/log/mofsim/worker-*.log` |
| 任务日志 | `/var/log/mofsim/tasks/*.log` |
| 系统日志 | `/var/log/mofsim/system.log` |

### 4.2 日志查看

```bash
# 查看最新日志
tail -f /var/log/mofsim/api.log

# 搜索错误
grep -i error /var/log/mofsim/api.log

# JSON 日志格式化
tail -f /var/log/mofsim/api.log | jq .

# 按任务 ID 过滤
grep "task_xxx" /var/log/mofsim/tasks/*.log
```

### 4.3 日志轮转

日志自动轮转配置（logrotate）:

```
/var/log/mofsim/*.log {
    daily
    rotate 180
    compress
    delaycompress
    notifempty
    create 644 mofsim mofsim
    sharedscripts
    postrotate
        docker-compose -f /opt/mofsim/docker-compose.production.yml kill -s HUP api
    endscript
}
```

### 4.4 日志清理

```bash
# 清理超过 180 天的日志
find /var/log/mofsim -name "*.log.gz" -mtime +180 -delete

# 清理任务日志
find /var/log/mofsim/tasks -name "*.log" -mtime +30 -delete
```

---

## 五、数据库维护

### 5.1 备份

```bash
# 全量备份
docker-compose exec postgres pg_dump -U mofsim mofsim > /backup/mofsim_$(date +%Y%m%d).sql

# 压缩备份
docker-compose exec postgres pg_dump -U mofsim mofsim | gzip > /backup/mofsim_$(date +%Y%m%d).sql.gz
```

### 5.2 恢复

```bash
# 从备份恢复
docker-compose exec -T postgres psql -U mofsim mofsim < /backup/mofsim_20231201.sql

# 从压缩备份恢复
gunzip -c /backup/mofsim_20231201.sql.gz | docker-compose exec -T postgres psql -U mofsim mofsim
```

### 5.3 维护

```bash
# 清理过期数据
docker-compose exec postgres psql -U mofsim -d mofsim -c "
    DELETE FROM task_logs WHERE created_at < NOW() - INTERVAL '180 days';
    DELETE FROM task_results WHERE created_at < NOW() - INTERVAL '180 days';
"

# 数据库优化
docker-compose exec postgres psql -U mofsim -d mofsim -c "VACUUM ANALYZE;"

# 检查数据库大小
docker-compose exec postgres psql -U mofsim -d mofsim -c "
    SELECT pg_size_pretty(pg_database_size('mofsim'));
"
```

---

## 六、任务管理

### 6.1 查看任务

```bash
# 查看运行中的任务
curl http://localhost:8000/api/v1/tasks?status=RUNNING

# 查看特定任务
curl http://localhost:8000/api/v1/tasks/{task_id}

# 查看任务日志
curl http://localhost:8000/api/v1/tasks/{task_id}/logs
```

### 6.2 取消任务

```bash
# 取消单个任务
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/cancel

# 批量取消
curl -X POST http://localhost:8000/api/v1/tasks/batch-cancel \
  -H "Content-Type: application/json" \
  -d '{"task_ids": ["task1", "task2"]}'
```

### 6.3 重试任务

```bash
# 重试失败的任务
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/retry
```

### 6.4 清理任务

```bash
# 清理已完成的任务（保留结果）
curl -X POST http://localhost:8000/api/v1/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"older_than_days": 30, "status": "COMPLETED"}'
```

---

## 七、GPU 管理

### 7.1 GPU 状态

```bash
# 查看 GPU 分配状态
curl http://localhost:8000/api/v1/system/gpus

# 查看 GPU 详细信息
nvidia-smi -q
```

### 7.2 GPU 问题处理

**GPU 显存不足**:

```bash
# 查看占用显存的进程
nvidia-smi pmon -s um

# 杀死僵尸进程
fuser -v /dev/nvidia*
```

**GPU 无响应**:

```bash
# 重置 GPU
nvidia-smi --gpu-reset -i 0

# 重启 Worker
docker-compose restart worker-gpu0
```

### 7.3 GPU 维护模式

```bash
# 将 GPU 标记为维护中
curl -X POST http://localhost:8000/api/v1/system/gpus/0/maintenance

# 取消维护模式
curl -X DELETE http://localhost:8000/api/v1/system/gpus/0/maintenance
```

---

## 八、常见问题处理

### 8.1 服务无响应

```bash
# 检查容器状态
docker-compose ps

# 查看错误日志
docker-compose logs --tail=100 api

# 重启服务
docker-compose restart api
```

### 8.2 任务卡住

```bash
# 检查 Worker 状态
celery -A workers.celery_app inspect active

# 检查 Redis 连接
redis-cli ping

# 强制终止并重试
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/force-retry
```

### 8.3 磁盘空间不足

```bash
# 检查磁盘使用
df -h

# 清理 Docker
docker system prune -a

# 清理旧日志
find /var/log/mofsim -name "*.log.gz" -mtime +30 -delete

# 清理旧结果
find /data/mofsim/results -mtime +90 -delete
```

### 8.4 内存不足

```bash
# 检查内存使用
free -h

# 查看内存占用进程
ps aux --sort=-%mem | head

# 重启服务释放内存
docker-compose restart
```

---

## 九、定期维护任务

### 9.1 每日任务

- [ ] 检查服务健康状态
- [ ] 查看错误日志
- [ ] 检查磁盘空间
- [ ] 查看任务统计

### 9.2 每周任务

- [ ] 数据库备份验证
- [ ] 清理过期日志
- [ ] 检查 GPU 健康
- [ ] 更新监控告警

### 9.3 每月任务

- [ ] 数据库优化（VACUUM）
- [ ] 系统安全更新
- [ ] 性能分析报告
- [ ] 容量规划评估

---

## 十、联系支持

- 紧急问题：xxx@example.com
- 文档：https://docs.example.com
- Issue：https://github.com/AI4ChemS/mofsim-bench/issues

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
