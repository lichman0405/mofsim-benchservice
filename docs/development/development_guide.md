# 开发环境指南

## 一、概述

本文档指导开发者搭建 MOFSimBench 服务端的开发环境。

---

## 二、环境要求

### 2.1 硬件要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核以上 |
| 内存 | 16GB | 32GB 以上 |
| GPU | 1 × NVIDIA GPU (8GB) | RTX 3090 或更高 |
| 存储 | 100GB SSD | 500GB SSD |

### 2.2 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 推荐 3.11 |
| CUDA | 11.8+ | 根据 GPU 驱动 |
| Docker | 24.0+ | 可选，用于容器化开发 |
| PostgreSQL | 15+ | 开发数据库 |
| Redis | 7+ | 消息队列 |
| Git | 2.40+ | 版本控制 |

---

## 三、环境搭建

### 3.1 克隆代码

```bash
git clone https://github.com/AI4ChemS/mofsim-bench.git
cd mofsim-bench
```

### 3.2 创建 Python 环境

**使用 Conda**：

```bash
conda create -n mofsim-dev python=3.11
conda activate mofsim-dev
```

**使用 venv**：

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3.3 安装依赖

```bash
# 安装核心依赖
pip install -e ".[dev]"

# 安装模型依赖（按需）
pip install mace-torch
pip install orb-models
pip install fairchem-core
pip install sevenn
pip install mattersim

# 安装 D3 校正
pip install torch-dftd

# 安装 ASE 开发版
pip install git+https://gitlab.com/ase/ase.git
```

### 3.4 安装开发工具

```bash
# 代码格式化
pip install black isort

# 类型检查
pip install mypy

# 测试
pip install pytest pytest-asyncio pytest-cov

# 文档
pip install mkdocs mkdocs-material
```

### 3.5 配置数据库

**使用 Docker**：

```bash
# 启动 PostgreSQL
docker run -d --name mofsim-postgres \
  -e POSTGRES_USER=mofsim \
  -e POSTGRES_PASSWORD=mofsim \
  -e POSTGRES_DB=mofsim \
  -p 5432:5432 \
  postgres:15

# 启动 Redis
docker run -d --name mofsim-redis \
  -p 6379:6379 \
  redis:7
```

**本地安装**：
- PostgreSQL: https://www.postgresql.org/download/
- Redis: https://redis.io/download/

### 3.6 初始化数据库

```bash
# 运行数据库迁移
alembic upgrade head

# 初始化内置数据
python scripts/init_db.py
```

---

## 四、项目结构

```
mofsim-bench/
├── api/                      # API 服务
│   ├── main.py               # FastAPI 入口
│   ├── routers/              # 路由
│   ├── schemas/              # Pydantic 模型
│   ├── dependencies.py       # 依赖注入
│   └── middleware/           # 中间件
├── core/                     # 核心逻辑
│   ├── tasks/                # 任务执行器
│   ├── models/               # 模型管理
│   ├── scheduler/            # GPU 调度
│   └── config.py             # 配置
├── workers/                  # Celery Workers
├── db/                       # 数据库
│   ├── models.py             # ORM 模型
│   └── crud.py               # 数据操作
├── mof_benchmark/            # 原有计算核心
├── tests/                    # 测试
├── docs/                     # 文档
├── config/                   # 配置文件
├── scripts/                  # 脚本
└── docker/                   # Docker 配置
```

---

## 五、开发配置

### 5.1 环境变量

创建 `.env` 文件：

```env
# 数据库
DATABASE_URL=postgresql://mofsim:mofsim@localhost:5432/mofsim

# Redis
REDIS_URL=redis://localhost:6379/0

# 密钥
SECRET_KEY=your-dev-secret-key

# 日志
LOG_LEVEL=DEBUG

# GPU
CUDA_VISIBLE_DEVICES=0

# 开发模式
DEBUG=true
```

### 5.2 配置文件

`config/settings.dev.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  debug: true
  reload: true

database:
  url: ${DATABASE_URL}
  pool_size: 5

redis:
  url: ${REDIS_URL}

scheduler:
  gpu_ids: [0]
  poll_interval_ms: 500

logging:
  level: DEBUG
  format: json
```

---

## 六、运行开发服务

### 6.1 启动 API 服务

```bash
# 开发模式（自动重载）
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 或使用脚本
python -m api.main
```

### 6.2 启动 Worker

```bash
# 启动单个 Worker
celery -A workers.celery_app worker --loglevel=info --queues=gpu-0

# 开发模式（单进程）
celery -A workers.celery_app worker --loglevel=debug --pool=solo
```

### 6.3 启动定时任务

```bash
celery -A workers.celery_app beat --loglevel=info
```

### 6.4 一键启动（开发）

```bash
# 使用 Honcho 或 Foreman
honcho start -f Procfile.dev
```

`Procfile.dev`:

```
api: uvicorn api.main:app --reload --port 8000
worker: celery -A workers.celery_app worker --loglevel=debug --pool=solo
beat: celery -A workers.celery_app beat --loglevel=info
```

---

## 七、IDE 配置

### 7.1 VS Code

`.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

推荐扩展：
- Python
- Pylance
- Python Debugger
- GitLens
- Docker

### 7.2 PyCharm

- 设置 Python 解释器为虚拟环境
- 启用 Black 格式化
- 配置运行/调试配置

---

## 八、调试技巧

### 8.1 调试 API

```python
# 在代码中添加断点
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

VS Code `launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug API",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      }
    }
  ]
}
```

### 8.2 调试 Worker

```bash
# 使用 rdb 远程调试
celery -A workers.celery_app worker --loglevel=debug --pool=solo
```

### 8.3 查看日志

```bash
# 实时查看日志
tail -f logs/app.log | jq .

# 过滤错误日志
tail -f logs/app.log | jq 'select(.level == "ERROR")'
```

---

## 九、常见问题

### 9.1 CUDA 不可用

```bash
# 检查 CUDA
python -c "import torch; print(torch.cuda.is_available())"

# 检查 GPU
nvidia-smi
```

### 9.2 数据库连接失败

```bash
# 检查 PostgreSQL
psql -h localhost -U mofsim -d mofsim

# 检查连接字符串
echo $DATABASE_URL
```

### 9.3 Redis 连接失败

```bash
# 检查 Redis
redis-cli ping
```

---

## 十、下一步

- [代码规范](coding_standards.md)
- [测试指南](testing_guide.md)
- [添加新任务](adding_new_task.md)

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
