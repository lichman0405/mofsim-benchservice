# MOFSimBench 工程化开发计划

## 一、项目概述

将 MOFSimBench 基准测试项目工程化为可部署的服务端应用，支持通过 API 接口提交计算任务、异步执行、获取结构化结果。

**依据文档**：
- [工程化需求规格说明书](../engineering_requirements.md)
- [系统架构设计](../architecture/architecture_design.md)
- [数据库设计](../architecture/database_design.md)
- [API 详细设计](../architecture/api_design.md)
- [开发环境指南](./development_guide.md)

---

## 二、开发环境说明

| 环境 | 用途 | 配置 |
|------|------|------|
| **开发环境** | 代码编写、单元测试 | Windows 11，无 GPU，使用 Mock |
| **测试服务器** | 集成测试、API 测试 | Linux，CPU Only |
| **部署服务器** | 生产运行 | Linux，8 × RTX 3090 |

**关键约束**：
1. 开发环境（Windows）不运行 GPU 相关测试
2. 需要 GPU 的测试统一在测试服务器进行
3. 每个阶段验收后再迁移到测试服务器进行验证

---

## 三、开发阶段规划

### Phase 1：基础框架搭建
**预估周期**：1 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 1.1 项目结构初始化 | 按文档创建目录结构 | 目录结构与 `engineering_requirements.md` 第十五节一致 |
| 1.2 依赖管理配置 | 更新 `pyproject.toml` | 包含所有服务端依赖（FastAPI、Celery、SQLAlchemy 等） |
| 1.3 配置系统实现 | 实现 `core/config.py` | 支持 YAML 配置文件加载、环境变量覆盖 |
| 1.4 数据库模型定义 | 实现 `db/models.py` | 包含 tasks、task_results、task_logs、structures、models 等表 |
| 1.5 数据库迁移脚本 | Alembic 迁移配置 | 可通过 `alembic upgrade head` 创建所有表 |
| 1.6 FastAPI 应用骨架 | 实现 `api/main.py` | 应用可启动，`/docs` 显示 Swagger UI |

**验收检查点**：
- [ ] `uvicorn api.main:app --reload` 可正常启动
- [ ] 访问 `http://localhost:8000/docs` 显示 API 文档
- [ ] 访问 `http://localhost:8000/api/v1/health` 返回 `{"status": "ok"}`
- [ ] 数据库表创建成功（PostgreSQL）

---

### Phase 2：任务队列与 GPU 调度
**预估周期**：1.5 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 2.1 Celery 应用配置 | 实现 `workers/celery_app.py` | Celery 可连接 Redis，Worker 可启动 |
| 2.2 优先级队列实现 | 实现 `core/scheduler/priority_queue.py` | 支持 4 级优先级（CRITICAL/HIGH/NORMAL/LOW） |
| 2.3 GPU 调度器实现 | 实现 `core/scheduler/scheduler.py` | 支持 GPU 分配、释放、负载均衡 |
| 2.4 GPU 状态监控 | 实现 GPU 状态查询 | 返回各 GPU 显存使用、温度、任务状态 |
| 2.5 Worker 绑定 GPU | 每个 Worker 绑定特定 GPU | Worker 启动时设置 `CUDA_VISIBLE_DEVICES` |
| 2.6 任务生命周期管理 | 状态转换逻辑 | 支持 PENDING→QUEUED→ASSIGNED→RUNNING→COMPLETED/FAILED |

**验收检查点**：
- [ ] Celery Worker 可正常启动并连接 Redis
- [ ] GPU 状态 API 返回正确的 GPU 信息（开发环境可 Mock）
- [ ] 任务可入队并按优先级排序
- [ ] 任务状态转换符合设计文档

---

### Phase 3：核心任务 API 实现
**预估周期**：2 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 3.1 统一响应格式 | 实现 `api/schemas/response.py` | 符合 `engineering_requirements.md` 5.1 节格式 |
| 3.2 错误处理中间件 | 实现统一错误处理 | 错误响应符合文档格式，包含 request_id |
| 3.3 任务提交 API | 实现 `POST /api/v1/tasks/{type}` | 支持 6 种任务类型提交 |
| 3.4 任务查询 API | 实现 `GET /api/v1/tasks/{task_id}` | 返回任务状态和基本信息 |
| 3.5 任务结果 API | 实现 `GET /api/v1/tasks/{task_id}/result` | 返回结构化结果（符合 5.3 节格式） |
| 3.6 任务取消 API | 实现 `POST /api/v1/tasks/{task_id}/cancel` | 可取消 QUEUED/RUNNING 状态任务 |
| 3.7 任务列表 API | 实现 `GET /api/v1/tasks` | 支持分页、状态过滤 |
| 3.8 批量提交 API | 实现 `POST /api/v1/tasks/batch` | 支持批量提交任务 |

**验收检查点**：
- [ ] 所有任务 API 端点可访问
- [ ] 请求/响应格式符合 API 设计文档
- [ ] 错误码符合 `engineering_requirements.md` 5.4 节定义
- [ ] 分页功能正常

---

### Phase 4：任务执行器实现
**预估周期**：2 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 4.1 任务执行器基类 | 实现 `core/tasks/base.py` | 定义统一的任务执行接口 |
| 4.2 优化任务执行器 | 实现 `core/tasks/optimization.py` | 调用 mof_benchmark 执行优化，返回结构化结果 |
| 4.3 稳定性任务执行器 | 实现 `core/tasks/stability.py` | 支持 opt→NVT→NPT 三阶段 |
| 4.4 体积模量执行器 | 实现 `core/tasks/bulk_modulus.py` | 返回 B0、V0 等指标 |
| 4.5 热容执行器 | 实现 `core/tasks/heat_capacity.py` | 基于 phonopy 计算热容 |
| 4.6 相互作用能执行器 | 实现 `core/tasks/interaction_energy.py` | 计算 MOF-气体相互作用能 |
| 4.7 单点能量执行器 | 实现 `core/tasks/single_point.py` | 返回能量、力、应力 |
| 4.8 Celery 任务处理器 | 实现 `workers/task_handlers.py` | 将任务分发到对应执行器 |

**验收检查点**：
- [ ] 在测试服务器上，优化任务可完整执行并返回结果
- [ ] 结果格式符合 `engineering_requirements.md` 5.3 节
- [ ] 任务执行过程有日志输出
- [ ] GPU 显存正确分配和释放

**⚠️ 需迁移到测试服务器验证**

---

### Phase 5：模型与结构管理
**预估周期**：1.5 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 5.1 模型注册表 | 实现 `core/models/registry.py` | 管理所有可用模型配置 |
| 5.2 模型加载器 | 实现 `core/models/loader.py` | 支持 MACE/ORB/OMAT24/GRACE/SevenNet 等 |
| 5.3 模型预加载 API | 实现 `POST /api/v1/models/{name}/load` | 预热模型到指定 GPU |
| 5.4 模型卸载 API | 实现 `POST /api/v1/models/{name}/unload` | 从 GPU 释放模型 |
| 5.5 自定义模型上传 | 实现 `POST /api/v1/models/custom` | 支持上传 .model/.pt 文件 |
| 5.6 自定义模型验证 | 实现 `POST /api/v1/models/custom/{id}/validate` | 测试模型可加载和推理 |
| 5.7 结构文件上传 | 实现 `POST /api/v1/structures` | 支持 CIF/XYZ 格式 |
| 5.8 结构文件验证 | 验证上传的结构文件 | 使用 ASE 解析验证 |

**验收检查点**：
- [ ] `GET /api/v1/models` 返回所有可用模型
- [ ] 结构文件上传并解析成功
- [ ] 自定义模型上传和验证流程完整
- [ ] 模型亲和性调度生效

---

### Phase 6：日志系统完善
**预估周期**：1 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 6.1 结构化日志配置 | 实现 `logging/config.py` | 使用 structlog，输出 JSON 格式 |
| 6.2 任务日志存储 | 日志写入数据库 | 任务执行日志持久化到 task_logs 表 |
| 6.3 日志查询 API | 实现 `GET /api/v1/tasks/{id}/logs` | 支持级别过滤、分页 |
| 6.4 实时日志流 | 实现 SSE 日志推送 | `GET /api/v1/tasks/{id}/logs/stream` |
| 6.5 请求日志中间件 | 记录 API 请求/响应 | 包含 request_id、耗时、状态码 |
| 6.6 日志文件归档 | 按日期归档日志 | 符合 `engineering_requirements.md` 6.5/6.6 节 |

**验收检查点**：
- [ ] 任务执行过程的日志可通过 API 查询
- [ ] SSE 实时日志流正常工作
- [ ] 日志格式符合文档 6.3 节
- [ ] 日志文件按策略归档

---

### Phase 7：回调与告警系统
**预估周期**：1 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 7.1 Webhook 回调 | 实现 `core/callback/webhook.py` | 任务完成后发送 HTTP 回调 |
| 7.2 回调重试机制 | 失败重试 | 支持配置重试次数和间隔 |
| 7.3 告警规则引擎 | 实现 `alerts/rules.py` | 支持内置告警规则 |
| 7.4 告警检查器 | 实现 `alerts/checker.py` | 定时检查告警条件 |
| 7.5 告警通知器 | 实现 `alerts/notifier.py` | 通过 Webhook 发送告警 |
| 7.6 告警 API | 实现告警相关 API | 规则列表、历史查询、当前告警 |

**验收检查点**：
- [ ] 任务完成后 Webhook 回调发送成功
- [ ] 回调失败自动重试
- [ ] 告警规则可触发（如 GPU 不可用）
- [ ] 告警历史可查询

---

### Phase 8：系统管理与监控
**预估周期**：0.5 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 8.1 健康检查 API | 实现 `/api/v1/health` | 返回服务健康状态 |
| 8.2 GPU 状态 API | 实现 `/api/v1/system/gpus` | 返回各 GPU 详细状态 |
| 8.3 队列状态 API | 实现 `/api/v1/system/queue` | 返回队列统计信息 |
| 8.4 Prometheus 指标 | 暴露 `/metrics` 端点 | 包含任务、GPU、队列指标 |
| 8.5 系统配置 API | 实现 `/api/v1/system/config` | 返回当前系统配置（脱敏） |

**验收检查点**：
- [ ] 健康检查端点可用
- [ ] Prometheus 可抓取指标
- [ ] 系统状态 API 信息准确

---

### Phase 9：Python SDK 开发
**预估周期**：1.5 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 9.1 SDK 项目结构 | 创建 `sdk/mofsim_client/` | 独立可发布的 Python 包 |
| 9.2 同步客户端 | 实现 `client.py` | 支持所有 API 的同步调用 |
| 9.3 异步客户端 | 实现 `async_client.py` | 支持 async/await |
| 9.4 任务对象 | 实现 Task 类 | 支持 `wait()`、`stream_logs()` |
| 9.5 异常处理 | 实现 `exceptions.py` | 自定义异常类型 |
| 9.6 类型注解 | 完整的类型注解 | 支持 IDE 自动补全 |
| 9.7 SDK 文档 | 编写使用文档 | 包含示例代码 |

**验收检查点**：
- [ ] SDK 可通过 pip 安装
- [ ] 基本使用示例可运行
- [ ] 类型提示完整
- [ ] 同步/异步接口均可用

---

### Phase 10：测试与文档
**预估周期**：1.5 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 10.1 API 单元测试 | 测试所有 API 端点 | 覆盖率 > 80% |
| 10.2 核心逻辑测试 | 测试调度器、执行器 | 关键路径覆盖 |
| 10.3 集成测试 | 端到端测试 | 完整任务流程可通过 |
| 10.4 SDK 测试 | 测试 SDK 功能 | 所有方法测试通过 |
| 10.5 API 文档更新 | 完善 OpenAPI 描述 | 所有端点有详细说明 |
| 10.6 部署文档 | 编写部署指南 | 可按文档完成部署 |

**验收检查点**：
- [ ] 所有测试通过
- [ ] 测试覆盖率达标
- [ ] 文档完整可用

**⚠️ 集成测试需在测试服务器执行**

---

### Phase 11：部署优化
**预估周期**：1 周

| 任务 | 说明 | 验收标准 |
|------|------|---------|
| 11.1 Docker 镜像 | 编写 Dockerfile | 镜像可构建成功 |
| 11.2 Docker Compose | 编写 docker-compose.yml | 一键启动所有服务 |
| 11.3 生产配置 | 生产环境配置文件 | 安全、性能优化 |
| 11.4 服务管理脚本 | 启动/停止/重启脚本 | 便于运维操作 |
| 11.5 数据备份脚本 | 数据库、文件备份 | 自动化备份 |
| 11.6 部署验证 | 完整部署测试 | 所有功能正常 |

**验收检查点**：
- [ ] Docker Compose 可一键部署
- [ ] 生产环境运行稳定
- [ ] 备份恢复验证通过

**⚠️ 在部署服务器执行**

---

## 四、Checklist 文件位置

每个阶段完成后更新：
- `docs/development/checklist.md`

---

## 五、依赖安装顺序

```bash
# Phase 1: 基础框架
pip install fastapi uvicorn pydantic pydantic-settings
pip install sqlalchemy alembic asyncpg psycopg2-binary
pip install pyyaml python-dotenv

# Phase 2: 任务队列
pip install celery redis

# Phase 6: 日志
pip install structlog

# Phase 8: 监控
pip install prometheus-client

# Phase 9: SDK
pip install httpx aiohttp

# 开发工具
pip install pytest pytest-asyncio pytest-cov
pip install black isort mypy
pip install mkdocs mkdocs-material
```

---

## 六、Git 分支策略

| 分支 | 用途 |
|------|------|
| `main` | 稳定版本 |
| `develop` | 开发集成 |
| `feature/phase-{N}-*` | 各阶段功能分支 |
| `release/v*` | 发布分支 |

---

## 七、代码审查要点

每个阶段完成后检查：
1. 代码是否符合文档设计
2. 类型注解是否完整
3. 错误处理是否完善
4. 日志记录是否充分
5. 测试是否覆盖关键路径

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
