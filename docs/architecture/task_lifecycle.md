# 任务生命周期

## 一、概述

本文档详细描述 MOFSimBench 中任务从创建到完成的完整生命周期，包括状态转换、调度流程和异常处理。

---

## 二、任务状态机

### 2.1 状态定义

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              任务状态机                                      │
│                                                                              │
│    ┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐            │
│    │ PENDING │────►│ QUEUED  │────►│ ASSIGNED │────►│ RUNNING │            │
│    └─────────┘     └─────────┘     └──────────┘     └─────────┘            │
│         │               │               │               │                   │
│         │               │               │               │                   │
│         ▼               ▼               ▼               ▼                   │
│    ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌───────────┐           │
│    │ FAILED  │     │CANCELLED│     │CANCELLED│     │ COMPLETED │           │
│    └─────────┘     └─────────┘     └─────────┘     └───────────┘           │
│                                                          │                  │
│                                          ┌───────────────┼───────────────┐  │
│                                          ▼               ▼               ▼  │
│                                     ┌─────────┐    ┌─────────┐    ┌───────┐│
│                                     │ FAILED  │    │ TIMEOUT │    │SUCCESS││
│                                     └─────────┘    └─────────┘    └───────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 状态说明

| 状态 | 说明 | 可转换到 |
|------|------|---------|
| `PENDING` | 任务已接收，正在验证 | QUEUED, FAILED |
| `QUEUED` | 任务已入队，等待 GPU | ASSIGNED, CANCELLED |
| `ASSIGNED` | 已分配 GPU，准备启动 | RUNNING, CANCELLED, FAILED |
| `RUNNING` | 任务正在执行 | COMPLETED, FAILED, TIMEOUT, CANCELLED |
| `COMPLETED` | 任务成功完成 | - (终态) |
| `FAILED` | 任务执行失败 | - (终态) |
| `CANCELLED` | 用户取消任务 | - (终态) |
| `TIMEOUT` | 任务超时 | - (终态) |

---

## 三、任务生命周期详解

### 3.1 阶段一：任务提交 (PENDING)

```
Client                 API Server              Validator
  │                        │                       │
  │  POST /tasks/xxx       │                       │
  │ ──────────────────────►│                       │
  │                        │                       │
  │                        │  validate_request()   │
  │                        │ ─────────────────────►│
  │                        │                       │
  │                        │  ◄─ validation result │
  │                        │ ◄─────────────────────│
  │                        │                       │
  │  202 Accepted          │                       │
  │  {task_id, status}     │                       │
  │ ◄──────────────────────│                       │
```

**验证内容**：
1. 请求格式验证（Pydantic）
2. 模型是否存在
3. 结构文件是否有效
4. 参数范围检查
5. 显存预估检查

### 3.2 阶段二：入队等待 (QUEUED)

```
Validator              TaskService             Redis Queue
  │                        │                       │
  │  validation passed     │                       │
  │ ──────────────────────►│                       │
  │                        │                       │
  │                        │  create_task()        │
  │                        │  save to database     │
  │                        │                       │
  │                        │  enqueue(task, prio)  │
  │                        │ ─────────────────────►│
  │                        │                       │
  │                        │  queue_position       │
  │                        │ ◄─────────────────────│
```

**队列机制**：
- 使用 Redis Sorted Set 实现优先级队列
- Score = priority * 1e12 + timestamp
- 低 score 优先出队

### 3.3 阶段三：资源分配 (ASSIGNED)

```
Scheduler              Redis Queue             GPU Manager
  │                        │                       │
  │  poll_next_task()      │                       │
  │ ──────────────────────►│                       │
  │                        │                       │
  │  task                  │                       │
  │ ◄──────────────────────│                       │
  │                        │                       │
  │  request_gpu(task)     │                       │
  │ ──────────────────────────────────────────────►│
  │                        │                       │
  │                        │  ◄── gpu_id / wait    │
  │ ◄──────────────────────────────────────────────│
  │                        │                       │
  │  update_status(ASSIGNED)                       │
```

**调度策略**：
1. 检查是否有空闲 GPU
2. 模型亲和性：优先选择已加载模型的 GPU
3. 负载均衡：选择任务历史最少的 GPU
4. 显存检查：确保有足够显存

### 3.4 阶段四：任务执行 (RUNNING)

```
Worker                 Task Executor           MOF Core
  │                        │                       │
  │  start_task(task)      │                       │
  │ ──────────────────────►│                       │
  │                        │                       │
  │                        │  load_model()         │
  │                        │ ─────────────────────►│
  │                        │                       │
  │                        │  load_structure()     │
  │                        │ ─────────────────────►│
  │                        │                       │
  │                        │  run_calculation()    │
  │                        │ ─────────────────────►│
  │                        │                       │
  │  ◄─── progress updates │ ◄─── step results    │
  │ ◄──────────────────────│ ◄─────────────────────│
  │                        │                       │
  │  log_progress()        │                       │
  │  update_database()     │                       │
```

**执行过程**：
1. 加载模型（如未缓存）
2. 读取结构文件
3. 设置计算参数
4. 执行计算循环
5. 记录日志和进度
6. 保存中间结果

### 3.5 阶段五：任务完成 (COMPLETED/FAILED)

```
Task Executor          Result Handler          Callback
  │                        │                       │
  │  task_finished(result) │                       │
  │ ──────────────────────►│                       │
  │                        │                       │
  │                        │  save_result()        │
  │                        │  save_output_files()  │
  │                        │                       │
  │                        │  update_status()      │
  │                        │                       │
  │                        │  notify_callback()    │
  │                        │ ─────────────────────►│
  │                        │                       │
  │  release_gpu()         │                       │
```

---

## 四、任务取消流程

### 4.1 取消排队中的任务

```python
def cancel_queued_task(task_id):
    # 1. 从队列中移除
    redis.zrem("task_queue", task_id)
    
    # 2. 更新状态
    db.update_task(task_id, status="CANCELLED")
    
    # 3. 记录日志
    log_task_cancelled(task_id, reason="user_request")
```

### 4.2 取消运行中的任务

```python
def cancel_running_task(task_id):
    # 1. 发送取消信号
    worker = get_worker_by_task(task_id)
    worker.send_cancel_signal(task_id)
    
    # 2. Worker 收到信号后
    #    - 中断计算循环
    #    - 保存当前进度
    #    - 清理资源
    #    - 释放 GPU
    
    # 3. 更新状态
    db.update_task(task_id, status="CANCELLED")
```

---

## 五、异常处理

### 5.1 验证失败

```python
# 请求验证失败
{
    "status": "FAILED",
    "error_type": "ValidationError",
    "error_message": "参数 fmax 必须大于 0"
}
```

### 5.2 模型加载失败

```python
# 模型无法加载
{
    "status": "FAILED",
    "error_type": "ModelLoadError",
    "error_message": "无法加载模型 mace_prod: CUDA out of memory"
}
```

### 5.3 计算异常

```python
# 计算过程异常
{
    "status": "FAILED",
    "error_type": "ComputationError",
    "error_message": "优化未收敛：超过最大步数 1000"
}
```

### 5.4 超时处理

```python
async def monitor_timeout(task_id, timeout_seconds):
    await asyncio.sleep(timeout_seconds)
    
    task = get_task(task_id)
    if task.status == "RUNNING":
        # 发送超时信号
        cancel_task(task_id, reason="timeout")
        
        # 更新状态
        db.update_task(task_id, status="TIMEOUT")
```

---

## 六、进度跟踪

### 6.1 进度更新

不同任务类型的进度计算方式：

| 任务类型 | 进度计算 |
|---------|---------|
| 优化 | current_step / max_steps |
| 稳定性 | (stage_progress + stage_index) / total_stages |
| 体积模量 | current_point / total_points |
| 热容 | phonon_progress (基于 phonopy) |

### 6.2 进度推送

```python
# SSE 进度推送
async def stream_progress(task_id):
    async for progress in task_progress_stream(task_id):
        yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
```

---

## 七、回调通知

### 7.1 回调触发时机

| 事件 | 触发条件 |
|------|---------|
| `task.started` | 状态变为 RUNNING |
| `task.progress` | 进度变化（可配置间隔） |
| `task.completed` | 状态变为 COMPLETED |
| `task.failed` | 状态变为 FAILED |
| `task.cancelled` | 状态变为 CANCELLED |
| `task.timeout` | 状态变为 TIMEOUT |

### 7.2 回调重试

```python
async def send_callback(url, payload, secret, max_retries=3):
    for attempt in range(max_retries):
        try:
            signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            response = await http.post(url, json=payload, headers={
                "X-Signature": signature
            })
            if response.status_code == 200:
                return True
        except Exception as e:
            log.warning(f"Callback failed: {e}")
        
        await asyncio.sleep(10 * (attempt + 1))
    
    log.error(f"Callback failed after {max_retries} attempts")
    return False
```

---

## 八、资源清理

### 8.1 任务完成后

```python
def cleanup_after_task(task_id, gpu_id):
    # 1. 释放 GPU
    gpu_manager.release(gpu_id)
    
    # 2. 清理临时文件
    temp_dir = get_temp_dir(task_id)
    shutil.rmtree(temp_dir)
    
    # 3. 更新模型缓存状态
    model_cache.update_usage(model_name)
```

### 8.2 过期数据清理

```python
# 定时任务：清理过期数据
@celery.task
def cleanup_expired_data():
    # 清理过期结构文件
    expired_structures = db.query(
        Structure.expires_at < now()
    )
    for struct in expired_structures:
        os.remove(struct.file_path)
        db.delete(struct)
    
    # 压缩旧轨迹文件
    old_results = db.query(
        TaskResult.created_at < now() - days(30)
    )
    for result in old_results:
        compress_trajectory(result)
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
