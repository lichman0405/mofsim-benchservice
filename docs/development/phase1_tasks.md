# Phase 1: 基础框架搭建 - 详细任务书

## 目标

完成 MOFSimBench 服务端的基础框架搭建，包括项目结构、配置系统、数据库模型和 FastAPI 应用骨架。

---

## 任务 1.1: 项目结构初始化

### 目标
创建符合 `engineering_requirements.md` 第十五节的目录结构。

### 执行步骤

创建以下目录结构：

```
mofsim-bench/
├── api/                      # API 服务层
│   ├── __init__.py
│   ├── main.py               # FastAPI 入口
│   ├── routers/              # 路由模块
│   │   ├── __init__.py
│   │   ├── tasks.py          # 任务相关 API
│   │   ├── models.py         # 模型管理 API
│   │   ├── structures.py     # 结构文件 API
│   │   ├── system.py         # 系统管理 API
│   │   └── alerts.py         # 告警 API
│   ├── schemas/              # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── task.py
│   │   ├── model.py
│   │   ├── structure.py
│   │   ├── system.py
│   │   └── response.py       # 统一响应格式
│   ├── dependencies.py       # 依赖注入
│   └── middleware/           # 中间件
│       ├── __init__.py
│       ├── logging.py        # 请求日志
│       └── error_handler.py  # 错误处理
├── core/                     # 核心业务逻辑
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── tasks/                # 任务执行器
│   │   ├── __init__.py
│   │   └── base.py
│   ├── models/               # 模型管理
│   │   ├── __init__.py
│   │   └── registry.py
│   ├── scheduler/            # GPU 调度器
│   │   ├── __init__.py
│   │   └── scheduler.py
│   └── callback/             # 回调通知
│       ├── __init__.py
│       └── webhook.py
├── workers/                  # Celery Workers
│   ├── __init__.py
│   ├── celery_app.py
│   └── task_handlers.py
├── db/                       # 数据库层
│   ├── __init__.py
│   ├── database.py           # 数据库连接
│   ├── models.py             # SQLAlchemy 模型
│   └── crud.py               # 数据操作
├── logging_config/           # 日志系统
│   ├── __init__.py
│   ├── config.py
│   └── handlers.py
├── alerts/                   # 告警系统
│   ├── __init__.py
│   ├── rules.py
│   ├── notifier.py
│   └── checker.py
├── sdk/                      # Python SDK
│   └── mofsim_client/
│       └── __init__.py
├── storage/                  # 存储目录
│   ├── structures/           # 上传的结构文件
│   ├── models/               # 自定义模型
│   ├── results/              # 任务结果
│   └── logs/                 # 日志文件
├── config/                   # 配置文件
│   ├── settings.yaml         # 主配置
│   ├── settings.dev.yaml     # 开发配置
│   └── logging.yaml          # 日志配置
├── scripts/                  # 脚本
│   ├── init_db.py            # 初始化数据库
│   └── start_dev.py          # 开发启动脚本
├── tests/                    # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api/
│   ├── test_core/
│   └── test_sdk/
└── docker/                   # Docker 配置
    ├── Dockerfile
    ├── Dockerfile.worker
    └── docker-compose.yml
```

### 验收标准
- [ ] 所有目录创建完成
- [ ] 所有 `__init__.py` 文件创建
- [ ] 目录结构与文档一致

---

## 任务 1.2: 依赖管理配置

### 目标
更新 `pyproject.toml`，添加服务端所需依赖。

### 依赖列表

```toml
[project]
name = "mofsim-bench"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    # 现有依赖保持不变
    "ase",
    # ...
    
    # === 服务端新增依赖 ===
    # Web 框架
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    
    # 数据库
    "sqlalchemy>=2.0.25",
    "alembic>=1.13.1",
    "asyncpg>=0.29.0",
    "psycopg2-binary>=2.9.9",
    
    # 任务队列
    "celery>=5.3.6",
    "redis>=5.0.1",
    
    # 配置
    "pyyaml>=6.0.1",
    "python-dotenv>=1.0.0",
    
    # 日志
    "structlog>=24.1.0",
    
    # 监控
    "prometheus-client>=0.19.0",
    
    # HTTP 客户端（SDK用）
    "httpx>=0.26.0",
    "aiohttp>=3.9.3",
    
    # 文件处理
    "python-multipart>=0.0.6",
    "aiofiles>=23.2.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "black>=24.1.0",
    "isort>=5.13.0",
    "mypy>=1.8.0",
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.5.0",
]
```

### 验收标准
- [ ] `pyproject.toml` 更新完成
- [ ] `pip install -e ".[dev]"` 成功

---

## 任务 1.3: 配置系统实现

### 目标
实现 `core/config.py`，支持 YAML 配置文件和环境变量。

### 配置结构

参考 `docs/development/development_guide.md` 5.1/5.2 节：

```python
# core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import yaml

class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False

class DatabaseConfig(BaseSettings):
    url: str = Field(..., env="DATABASE_URL")
    pool_size: int = 5
    max_overflow: int = 10

class RedisConfig(BaseSettings):
    url: str = Field(..., env="REDIS_URL")

class SchedulerConfig(BaseSettings):
    gpu_ids: List[int] = [0]
    poll_interval_ms: int = 500

class LoggingConfig(BaseSettings):
    level: str = "INFO"
    format: str = "json"

class Settings(BaseSettings):
    server: ServerConfig
    database: DatabaseConfig
    redis: RedisConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig
    secret_key: str = Field(..., env="SECRET_KEY")

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
```

### 配置文件示例

`config/settings.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  debug: false
  reload: false

database:
  pool_size: 10
  max_overflow: 20

redis:
  # url 从环境变量读取

scheduler:
  gpu_ids: [0, 1, 2, 3, 4, 5, 6, 7]
  poll_interval_ms: 500

logging:
  level: INFO
  format: json
```

`config/settings.dev.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
  debug: true
  reload: true

database:
  pool_size: 5

scheduler:
  gpu_ids: [0]  # 开发环境只用一个 GPU（或 Mock）

logging:
  level: DEBUG
```

### 验收标准
- [ ] 配置类定义完成
- [ ] 支持 YAML 文件加载
- [ ] 支持环境变量覆盖
- [ ] 开发/生产配置分离

---

## 任务 1.4: 数据库模型定义

### 目标
实现 `db/models.py`，定义所有数据库表。

### 参考文档
`docs/architecture/database_design.md`

### 表结构

```python
# db/models.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Float, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"

class TaskPriority(int, enum.Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING)
    priority = Column(Integer, nullable=False, default=TaskPriority.NORMAL)
    
    model_name = Column(String(100), nullable=False)
    structure_id = Column(UUID(as_uuid=True), ForeignKey("structures.id"))
    
    parameters = Column(JSONB, nullable=False, default={})
    options = Column(JSONB, nullable=False, default={})
    
    gpu_id = Column(Integer)
    worker_id = Column(String(100))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    callback_url = Column(String(500))
    callback_events = Column(ARRAY(String(50)))
    callback_secret = Column(String(200))
    
    error_type = Column(String(100))
    error_message = Column(Text)
    
    # 关联
    result = relationship("TaskResult", back_populates="task", uselist=False)
    logs = relationship("TaskLog", back_populates="task")
    structure = relationship("Structure")

class TaskResult(Base):
    __tablename__ = "task_results"
    
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    result_data = Column(JSONB, nullable=False)
    output_files = Column(JSONB, nullable=False, default={})
    metrics = Column(JSONB, nullable=False, default={})
    duration_seconds = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    task = relationship("Task", back_populates="result")

class TaskLog(Base):
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    level = Column(String(10), nullable=False)
    logger = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    extra = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    task = relationship("Task", back_populates="logs")

class Structure(Base):
    __tablename__ = "structures"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    original_name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    format = Column(String(20), nullable=False)
    checksum = Column(String(64), nullable=False)
    
    n_atoms = Column(Integer)
    formula = Column(String(200))
    is_builtin = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Model(Base):
    __tablename__ = "models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    framework = Column(String(50), nullable=False)
    file_path = Column(String(500))
    is_custom = Column(Boolean, default=False)
    is_validated = Column(Boolean, default=False)
    
    config = Column(JSONB, default={})
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    condition = Column(JSONB, nullable=False)
    level = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id"))
    level = Column(String(20), nullable=False)
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSONB, default={})
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    rule = relationship("AlertRule")
```

### 验收标准
- [ ] 所有表模型定义完成
- [ ] 符合 database_design.md 设计
- [ ] 关联关系正确

---

## 任务 1.5: 数据库迁移脚本

### 目标
配置 Alembic，生成初始迁移脚本。

### 执行步骤

```bash
# 初始化 Alembic
alembic init db/migrations

# 配置 alembic.ini 和 env.py

# 生成迁移脚本
alembic revision --autogenerate -m "initial tables"

# 执行迁移
alembic upgrade head
```

### 验收标准
- [ ] `alembic upgrade head` 成功执行
- [ ] 数据库中创建所有表

---

## 任务 1.6: FastAPI 应用骨架

### 目标
实现 `api/main.py`，创建基础 FastAPI 应用。

### 代码结构

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import tasks, models, structures, system, alerts
from core.config import get_settings
from db.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()
    yield
    # 关闭时
    pass

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="MOFSimBench API",
        description="MOF 模拟基准测试服务",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 路由
    app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
    app.include_router(models.router, prefix="/api/v1", tags=["models"])
    app.include_router(structures.router, prefix="/api/v1", tags=["structures"])
    app.include_router(system.router, prefix="/api/v1", tags=["system"])
    app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
    
    return app

app = create_app()

# 健康检查（不需要认证）
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
```

### 验收标准
- [ ] `uvicorn api.main:app --reload` 成功启动
- [ ] 访问 `/docs` 显示 Swagger UI
- [ ] 访问 `/api/v1/health` 返回正确响应

---

## 环境准备

在开始编码前，需要完成以下准备工作：

### 1. 创建虚拟环境

```bash
conda create -n mofsim-server python=3.11
conda activate mofsim-server
```

### 2. 安装 Docker（用于 PostgreSQL 和 Redis）

开发环境使用 Docker 运行数据库服务：

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

### 3. 创建 .env 文件

```env
DATABASE_URL=postgresql://mofsim:mofsim@localhost:5432/mofsim
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
LOG_LEVEL=DEBUG
DEBUG=true
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
