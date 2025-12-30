# 备份与恢复指南

## 一、概述

本文档描述 MOFSimBench 的数据备份和灾难恢复策略。

---

## 二、备份策略

### 2.1 备份对象

| 数据类型 | 重要性 | 备份频率 | 保留时间 |
|---------|--------|---------|---------|
| 数据库 | 关键 | 每日 | 30 天 |
| 结构文件 | 重要 | 每周 | 永久 |
| 结果文件 | 一般 | 每周 | 180 天 |
| 配置文件 | 关键 | 每次变更 | 永久 |
| 日志文件 | 一般 | 不备份 | 180 天 |
| 模型文件 | 重要 | 每次变更 | 永久 |

### 2.2 备份存储

```
/backup/
├── daily/                    # 每日备份
│   ├── postgres/
│   │   ├── mofsim_20240115.sql.gz
│   │   └── mofsim_20240114.sql.gz
│   └── redis/
│       └── dump_20240115.rdb
├── weekly/                   # 每周备份
│   ├── structures/
│   │   └── structures_2024w02.tar.gz
│   └── results/
│       └── results_2024w02.tar.gz
└── archive/                  # 归档
    ├── config/
    └── models/
```

---

## 三、数据库备份

### 3.1 自动备份脚本

`scripts/backup_database.sh`:

```bash
#!/bin/bash

# 配置
BACKUP_DIR="/backup/daily/postgres"
RETENTION_DAYS=30
DB_CONTAINER="mofsim-postgres"
DB_USER="mofsim"
DB_NAME="mofsim"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 生成备份文件名
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mofsim_$DATE.sql.gz"

echo "开始备份数据库..."

# 执行备份
docker exec $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "备份成功: $BACKUP_FILE"
    
    # 验证备份
    if gzip -t "$BACKUP_FILE"; then
        echo "备份文件验证通过"
    else
        echo "警告: 备份文件可能损坏"
        exit 1
    fi
else
    echo "备份失败!"
    exit 1
fi

# 清理旧备份
echo "清理 $RETENTION_DAYS 天前的备份..."
find "$BACKUP_DIR" -name "mofsim_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# 统计
echo "当前备份文件:"
ls -lh "$BACKUP_DIR" | tail -5
```

### 3.2 定时任务

```bash
# 添加到 crontab
# crontab -e

# 每天凌晨 2 点执行数据库备份
0 2 * * * /opt/mofsim/scripts/backup_database.sh >> /var/log/mofsim/backup.log 2>&1
```

### 3.3 增量备份

使用 WAL 归档实现增量备份：

`postgresql.conf`:

```conf
wal_level = replica
archive_mode = on
archive_command = 'gzip < %p > /backup/wal/%f.gz'
```

---

## 四、文件备份

### 4.1 结构文件备份

`scripts/backup_structures.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backup/weekly/structures"
SOURCE_DIR="/data/mofsim/structures"
DATE=$(date +%Y%m%d)
WEEK=$(date +%Yw%V)

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/structures_$WEEK.tar.gz"

echo "备份结构文件..."
tar -czf "$BACKUP_FILE" -C "$SOURCE_DIR" .

echo "备份完成: $BACKUP_FILE"
echo "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"
```

### 4.2 结果文件备份

`scripts/backup_results.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backup/weekly/results"
SOURCE_DIR="/data/mofsim/results"
DATE=$(date +%Y%m%d)
WEEK=$(date +%Yw%V)
RETENTION_DAYS=180

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/results_$WEEK.tar.gz"

echo "备份结果文件..."

# 只备份最近 180 天的结果
find "$SOURCE_DIR" -type f -mtime -180 -print0 | \
    tar --null -czf "$BACKUP_FILE" -T -

echo "备份完成: $BACKUP_FILE"

# 清理旧备份
find "$BACKUP_DIR" -name "results_*.tar.gz" -mtime +180 -delete
```

### 4.3 配置文件备份

```bash
#!/bin/bash

BACKUP_DIR="/backup/archive/config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    /opt/mofsim/config/ \
    /opt/mofsim/.env.production \
    /opt/mofsim/docker-compose.production.yml

echo "配置备份完成"
```

---

## 五、Redis 备份

### 5.1 RDB 备份

```bash
# 触发 RDB 快照
docker exec mofsim-redis redis-cli BGSAVE

# 等待完成
docker exec mofsim-redis redis-cli LASTSAVE

# 复制备份文件
docker cp mofsim-redis:/data/dump.rdb /backup/daily/redis/dump_$(date +%Y%m%d).rdb
```

### 5.2 AOF 备份

```bash
# 如果启用了 AOF
docker cp mofsim-redis:/data/appendonly.aof /backup/daily/redis/appendonly_$(date +%Y%m%d).aof
```

---

## 六、数据恢复

### 6.1 数据库恢复

**完全恢复**：

```bash
#!/bin/bash

BACKUP_FILE="/backup/daily/postgres/mofsim_20240115.sql.gz"

echo "停止应用服务..."
docker-compose stop api worker-gpu0 worker-gpu1 worker-gpu2 worker-gpu3 \
    worker-gpu4 worker-gpu5 worker-gpu6 worker-gpu7

echo "恢复数据库..."

# 删除现有数据库
docker exec mofsim-postgres psql -U mofsim -c "DROP DATABASE IF EXISTS mofsim;"
docker exec mofsim-postgres psql -U mofsim -c "CREATE DATABASE mofsim;"

# 恢复数据
gunzip -c "$BACKUP_FILE" | docker exec -i mofsim-postgres psql -U mofsim -d mofsim

echo "重启应用服务..."
docker-compose up -d

echo "恢复完成"
```

**选择性恢复**：

```bash
# 恢复特定表
gunzip -c backup.sql.gz | grep -A 1000 "COPY tasks" | head -1000 | \
    docker exec -i mofsim-postgres psql -U mofsim -d mofsim
```

### 6.2 文件恢复

```bash
# 恢复结构文件
tar -xzf /backup/weekly/structures/structures_2024w02.tar.gz -C /data/mofsim/structures/

# 恢复特定结果
tar -xzf /backup/weekly/results/results_2024w02.tar.gz -C /data/mofsim/results/ \
    --wildcards "*/task_xxx/*"
```

### 6.3 Redis 恢复

```bash
# 停止 Redis
docker-compose stop redis

# 恢复 RDB 文件
docker cp /backup/daily/redis/dump_20240115.rdb mofsim-redis:/data/dump.rdb

# 启动 Redis
docker-compose start redis
```

---

## 七、灾难恢复

### 7.1 恢复清单

1. **基础设施**：
   - [ ] 服务器就绪
   - [ ] Docker 已安装
   - [ ] NVIDIA 驱动已安装

2. **配置恢复**：
   - [ ] 恢复配置文件
   - [ ] 恢复 .env 文件
   - [ ] 恢复 docker-compose.yml

3. **数据恢复**：
   - [ ] 恢复数据库
   - [ ] 恢复结构文件
   - [ ] 恢复模型文件
   - [ ] 恢复结果文件（可选）

4. **服务启动**：
   - [ ] 启动数据库
   - [ ] 启动 Redis
   - [ ] 启动 API
   - [ ] 启动 Workers

5. **验证**：
   - [ ] API 健康检查
   - [ ] 提交测试任务
   - [ ] 检查 GPU 状态

### 7.2 完整恢复脚本

`scripts/disaster_recovery.sh`:

```bash
#!/bin/bash

set -e

BACKUP_BASE="/backup"
INSTALL_DIR="/opt/mofsim"
DATA_DIR="/data/mofsim"

echo "========================================"
echo "      MOFSimBench 灾难恢复脚本"
echo "========================================"

# 1. 恢复配置
echo "[1/6] 恢复配置文件..."
LATEST_CONFIG=$(ls -t $BACKUP_BASE/archive/config/config_*.tar.gz | head -1)
tar -xzf "$LATEST_CONFIG" -C /

# 2. 启动基础服务
echo "[2/6] 启动数据库和 Redis..."
cd $INSTALL_DIR
docker-compose -f docker-compose.production.yml up -d postgres redis
sleep 10

# 3. 恢复数据库
echo "[3/6] 恢复数据库..."
LATEST_DB=$(ls -t $BACKUP_BASE/daily/postgres/mofsim_*.sql.gz | head -1)
gunzip -c "$LATEST_DB" | docker exec -i mofsim-postgres psql -U mofsim -d mofsim

# 4. 恢复文件
echo "[4/6] 恢复数据文件..."
LATEST_STRUCT=$(ls -t $BACKUP_BASE/weekly/structures/structures_*.tar.gz | head -1)
tar -xzf "$LATEST_STRUCT" -C $DATA_DIR/structures/

LATEST_MODELS=$(ls -t $BACKUP_BASE/archive/models/models_*.tar.gz | head -1)
tar -xzf "$LATEST_MODELS" -C $DATA_DIR/models/

# 5. 启动所有服务
echo "[5/6] 启动所有服务..."
docker-compose -f docker-compose.production.yml up -d

# 6. 验证
echo "[6/6] 验证恢复..."
sleep 30

if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "✓ API 服务正常"
else
    echo "✗ API 服务异常"
    exit 1
fi

echo "========================================"
echo "      恢复完成!"
echo "========================================"
```

---

## 八、备份验证

### 8.1 自动验证脚本

`scripts/verify_backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backup/daily/postgres"
LATEST_BACKUP=$(ls -t $BACKUP_DIR/mofsim_*.sql.gz | head -1)

echo "验证备份: $LATEST_BACKUP"

# 创建临时数据库
docker exec mofsim-postgres psql -U mofsim -c "CREATE DATABASE mofsim_verify;"

# 恢复到临时数据库
gunzip -c "$LATEST_BACKUP" | docker exec -i mofsim-postgres psql -U mofsim -d mofsim_verify

# 验证数据
TASK_COUNT=$(docker exec mofsim-postgres psql -U mofsim -d mofsim_verify -t -c "SELECT COUNT(*) FROM tasks;")
echo "任务数: $TASK_COUNT"

# 清理
docker exec mofsim-postgres psql -U mofsim -c "DROP DATABASE mofsim_verify;"

echo "备份验证完成"
```

### 8.2 每周验证任务

```bash
# crontab
0 4 * * 0 /opt/mofsim/scripts/verify_backup.sh >> /var/log/mofsim/backup_verify.log 2>&1
```

---

## 九、备份监控

### 9.1 告警规则

```yaml
# prometheus rules
- alert: BackupMissing
  expr: time() - backup_last_success_timestamp > 86400
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "备份超过 24 小时未执行"

- alert: BackupFailed
  expr: backup_last_status == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "最近一次备份失败"
```

### 9.2 备份指标

```python
# 在备份脚本末尾添加
from prometheus_client import push_to_gateway, Gauge

backup_timestamp = Gauge('backup_last_success_timestamp', 'Last backup timestamp')
backup_status = Gauge('backup_last_status', 'Last backup status')
backup_size = Gauge('backup_size_bytes', 'Backup file size')

backup_timestamp.set(time.time())
backup_status.set(1)
backup_size.set(os.path.getsize(backup_file))

push_to_gateway('localhost:9091', job='backup', registry=registry)
```

---

## 十、最佳实践

1. **3-2-1 规则**：3 份备份，2 种介质，1 份异地
2. **定期测试恢复**：每月进行一次完整恢复演练
3. **加密敏感备份**：数据库和配置文件备份应加密
4. **监控备份状态**：确保备份任务正常执行
5. **文档更新**：备份策略变更时更新文档

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
