# GPU 调度器设计

## 一、概述

GPU 调度器负责将任务分配到合适的 GPU 上执行，实现资源的高效利用和任务的公平调度。

---

## 二、调度器架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            GPU Scheduler                                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Priority Queue                               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │    │
│  │  │ CRITICAL │ │   HIGH   │ │  NORMAL  │ │   LOW    │               │    │
│  │  │  Queue   │ │  Queue   │ │  Queue   │ │  Queue   │               │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Resource Allocator                             │    │
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐           │    │
│  │  │ Memory Checker │ │ Model Affinity │ │ Load Balancer  │           │    │
│  │  └────────────────┘ └────────────────┘ └────────────────┘           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                          GPU Pool                                    │    │
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐       │    │
│  │  │ GPU 0 │ │ GPU 1 │ │ GPU 2 │ │ GPU 3 │ │ GPU 4 │ │ GPU 5 │ ...   │    │
│  │  │ BUSY  │ │ FREE  │ │ BUSY  │ │ FREE  │ │ FREE  │ │ BUSY  │       │    │
│  │  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件

### 3.1 优先级队列

```python
class PriorityQueue:
    """基于 Redis Sorted Set 的优先级队列"""
    
    PRIORITY_WEIGHTS = {
        "CRITICAL": 0,
        "HIGH": 1,
        "NORMAL": 2,
        "LOW": 3
    }
    
    def enqueue(self, task_id: str, priority: str):
        """入队：score = priority_weight * 1e12 + timestamp"""
        weight = self.PRIORITY_WEIGHTS[priority]
        score = weight * 1e12 + time.time()
        self.redis.zadd("task_queue", {task_id: score})
    
    def dequeue(self) -> Optional[str]:
        """出队：取 score 最小的任务"""
        result = self.redis.zpopmin("task_queue", count=1)
        if result:
            return result[0][0]
        return None
    
    def peek(self) -> List[dict]:
        """查看队列前 N 个任务"""
        return self.redis.zrange("task_queue", 0, 9, withscores=True)
    
    def remove(self, task_id: str):
        """移除任务（用于取消）"""
        self.redis.zrem("task_queue", task_id)
    
    def position(self, task_id: str) -> int:
        """获取任务在队列中的位置"""
        return self.redis.zrank("task_queue", task_id)
```

### 3.2 GPU 资源管理器

```python
@dataclass
class GPUState:
    id: int
    name: str
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_percent: int
    temperature_c: int
    status: str  # "free", "busy", "error"
    current_task_id: Optional[str]
    loaded_models: List[str]


class GPUManager:
    """GPU 资源管理"""
    
    def __init__(self, gpu_ids: List[int]):
        self.gpu_ids = gpu_ids
        self.gpu_states = {i: self._init_gpu_state(i) for i in gpu_ids}
        self.locks = {i: asyncio.Lock() for i in gpu_ids}
    
    def get_free_gpus(self) -> List[int]:
        """获取空闲 GPU 列表"""
        return [
            gpu_id for gpu_id, state in self.gpu_states.items()
            if state.status == "free"
        ]
    
    def get_gpu_with_model(self, model_name: str) -> Optional[int]:
        """获取已加载指定模型的空闲 GPU"""
        for gpu_id, state in self.gpu_states.items():
            if state.status == "free" and model_name in state.loaded_models:
                return gpu_id
        return None
    
    async def allocate(self, gpu_id: int, task_id: str) -> bool:
        """分配 GPU 给任务"""
        async with self.locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            if state.status != "free":
                return False
            
            state.status = "busy"
            state.current_task_id = task_id
            return True
    
    async def release(self, gpu_id: int):
        """释放 GPU"""
        async with self.locks[gpu_id]:
            state = self.gpu_states[gpu_id]
            state.status = "free"
            state.current_task_id = None
    
    def refresh_states(self):
        """刷新 GPU 状态（从 nvidia-smi）"""
        import pynvml
        pynvml.nvmlInit()
        
        for gpu_id in self.gpu_ids:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            self.gpu_states[gpu_id].memory_total_mb = memory.total // 1024 // 1024
            self.gpu_states[gpu_id].memory_used_mb = memory.used // 1024 // 1024
            self.gpu_states[gpu_id].memory_free_mb = memory.free // 1024 // 1024
            self.gpu_states[gpu_id].utilization_percent = util.gpu
            self.gpu_states[gpu_id].temperature_c = temp
```

### 3.3 调度器

```python
class Scheduler:
    """任务调度器"""
    
    def __init__(self, gpu_manager: GPUManager, queue: PriorityQueue):
        self.gpu_manager = gpu_manager
        self.queue = queue
        self.model_memory_estimates = {}  # 模型显存估算
    
    async def schedule_next(self) -> Optional[Tuple[str, int]]:
        """调度下一个任务"""
        
        # 1. 获取空闲 GPU
        free_gpus = self.gpu_manager.get_free_gpus()
        if not free_gpus:
            return None
        
        # 2. 从队列获取任务
        task_id = self.queue.peek_first()
        if not task_id:
            return None
        
        task = await self.get_task(task_id)
        
        # 3. 选择最佳 GPU
        gpu_id = await self.select_best_gpu(task, free_gpus)
        if gpu_id is None:
            return None
        
        # 4. 分配 GPU
        if await self.gpu_manager.allocate(gpu_id, task_id):
            self.queue.dequeue()
            return (task_id, gpu_id)
        
        return None
    
    async def select_best_gpu(self, task: Task, free_gpus: List[int]) -> Optional[int]:
        """选择最佳 GPU"""
        
        model_name = task.model_name
        required_memory = self.estimate_memory(task)
        
        candidates = []
        
        for gpu_id in free_gpus:
            state = self.gpu_manager.gpu_states[gpu_id]
            
            # 检查显存是否足够
            if state.memory_free_mb < required_memory:
                continue
            
            # 计算得分
            score = 0
            
            # 模型亲和性：已加载模型的 GPU 得分更高
            if model_name in state.loaded_models:
                score += 100
            
            # 空闲显存越多得分越高
            score += state.memory_free_mb / 1000
            
            # 温度越低得分越高
            score += (100 - state.temperature_c) / 10
            
            candidates.append((gpu_id, score))
        
        if not candidates:
            return None
        
        # 返回得分最高的 GPU
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def estimate_memory(self, task: Task) -> int:
        """估算任务所需显存（MB）"""
        base_memory = self.model_memory_estimates.get(task.model_name, 4000)
        
        # 根据结构大小调整
        n_atoms = task.structure_n_atoms or 500
        atom_memory = n_atoms * 2  # 每原子约 2MB
        
        # 根据任务类型调整
        task_multiplier = {
            "optimization": 1.2,
            "stability": 1.5,
            "heat-capacity": 2.0,
            "bulk-modulus": 1.3,
        }.get(task.task_type, 1.0)
        
        return int((base_memory + atom_memory) * task_multiplier)
```

---

## 四、调度策略

### 4.1 优先级调度

| 优先级 | 权重 | 说明 |
|--------|------|------|
| CRITICAL | 0 | 最高优先级，立即调度 |
| HIGH | 1 | 高优先级，优先处理 |
| NORMAL | 2 | 普通优先级（默认） |
| LOW | 3 | 低优先级，批量任务 |

**调度规则**：
1. 高优先级任务优先调度
2. 同优先级按提交时间 FIFO
3. 不抢占正在运行的任务

### 4.2 模型亲和性

```python
def model_affinity_score(gpu_state: GPUState, model_name: str) -> int:
    """计算模型亲和性得分"""
    if model_name in gpu_state.loaded_models:
        # 模型已加载，无需重新加载
        return 100
    elif len(gpu_state.loaded_models) < 2:
        # GPU 还有空间缓存更多模型
        return 50
    else:
        # GPU 缓存已满，需要卸载其他模型
        return 0
```

**模型缓存策略**：
- 每个 GPU 最多缓存 2 个模型
- LRU 策略淘汰不常用模型
- 预热：系统启动时预加载常用模型

### 4.3 负载均衡

```python
def load_balance_score(gpu_state: GPUState) -> int:
    """计算负载均衡得分"""
    scores = []
    
    # 可用显存得分（0-40分）
    memory_ratio = gpu_state.memory_free_mb / gpu_state.memory_total_mb
    scores.append(memory_ratio * 40)
    
    # GPU 利用率得分（0-30分）
    util_score = (100 - gpu_state.utilization_percent) / 100 * 30
    scores.append(util_score)
    
    # 温度得分（0-20分）
    temp_score = (100 - gpu_state.temperature_c) / 100 * 20
    scores.append(temp_score)
    
    # 等待时间得分（0-10分）
    # GPU 空闲时间越长得分越高
    
    return sum(scores)
```

### 4.4 显存保护

```python
MEMORY_SAFETY_MARGIN_MB = 2000  # 保留 2GB 安全余量

def check_memory_available(gpu_state: GPUState, required_mb: int) -> bool:
    """检查显存是否足够"""
    available = gpu_state.memory_free_mb - MEMORY_SAFETY_MARGIN_MB
    return available >= required_mb
```

---

## 五、Worker 管理

### 5.1 Worker 进程模型

```python
# 每个 GPU 一个 Worker
celery_workers = [
    CeleryWorker(
        name=f"worker-gpu-{i}",
        concurrency=1,
        queues=[f"gpu-{i}"],
        env={"CUDA_VISIBLE_DEVICES": str(i)}
    )
    for i in range(8)
]
```

### 5.2 Worker 心跳监控

```python
class WorkerMonitor:
    """Worker 心跳监控"""
    
    HEARTBEAT_INTERVAL = 10  # 秒
    HEARTBEAT_TIMEOUT = 30   # 秒
    
    async def monitor_workers(self):
        while True:
            for worker_id, last_heartbeat in self.heartbeats.items():
                if time.time() - last_heartbeat > self.HEARTBEAT_TIMEOUT:
                    await self.handle_worker_down(worker_id)
            
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)
    
    async def handle_worker_down(self, worker_id: str):
        """处理 Worker 离线"""
        gpu_id = self.worker_to_gpu[worker_id]
        
        # 1. 标记 GPU 为错误状态
        self.gpu_manager.gpu_states[gpu_id].status = "error"
        
        # 2. 获取该 Worker 正在执行的任务
        task_id = self.gpu_manager.gpu_states[gpu_id].current_task_id
        if task_id:
            # 标记任务失败
            await self.fail_task(task_id, "Worker offline")
        
        # 3. 发送告警
        await self.alert_worker_down(worker_id, gpu_id)
        
        # 4. 尝试重启 Worker
        await self.restart_worker(worker_id)
```

---

## 六、故障处理

### 6.1 GPU 故障

```python
async def handle_gpu_error(gpu_id: int, error: Exception):
    """处理 GPU 错误"""
    
    # 1. 标记 GPU 不可用
    gpu_manager.gpu_states[gpu_id].status = "error"
    
    # 2. 取消该 GPU 上的任务
    task_id = gpu_manager.gpu_states[gpu_id].current_task_id
    if task_id:
        await fail_task(task_id, f"GPU error: {error}")
    
    # 3. 发送告警
    await send_alert(
        level="CRITICAL",
        type="gpu_error",
        message=f"GPU {gpu_id} 发生错误: {error}",
        details={"gpu_id": gpu_id, "error": str(error)}
    )
    
    # 4. 尝试恢复
    if await try_recover_gpu(gpu_id):
        gpu_manager.gpu_states[gpu_id].status = "free"
    else:
        # 需要人工介入
        await send_alert(level="CRITICAL", type="gpu_unrecoverable", ...)
```

### 6.2 OOM 处理

```python
async def handle_oom(task_id: str, gpu_id: int):
    """处理显存不足"""
    
    # 1. 记录失败
    await fail_task(task_id, "CUDA out of memory")
    
    # 2. 清理 GPU
    torch.cuda.empty_cache()
    
    # 3. 更新显存估算
    task = await get_task(task_id)
    current_estimate = model_memory_estimates[task.model_name]
    model_memory_estimates[task.model_name] = current_estimate * 1.2
    
    # 4. 释放 GPU
    await gpu_manager.release(gpu_id)
```

---

## 七、监控指标

### 7.1 调度器指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `scheduler_queue_size` | Gauge | 队列中的任务数 |
| `scheduler_queue_wait_seconds` | Histogram | 任务等待时间 |
| `scheduler_schedule_total` | Counter | 调度次数 |
| `scheduler_schedule_failures` | Counter | 调度失败次数 |

### 7.2 GPU 指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `gpu_memory_used_bytes` | Gauge | GPU 显存使用量 |
| `gpu_memory_total_bytes` | Gauge | GPU 总显存 |
| `gpu_utilization_percent` | Gauge | GPU 利用率 |
| `gpu_temperature_celsius` | Gauge | GPU 温度 |
| `gpu_tasks_total` | Counter | GPU 处理的任务总数 |

---

## 八、配置参数

```yaml
scheduler:
  # 调度间隔
  poll_interval_ms: 100
  
  # 显存安全余量
  memory_safety_margin_mb: 2000
  
  # 模型缓存
  max_models_per_gpu: 2
  model_cache_ttl_seconds: 3600
  
  # Worker 监控
  worker_heartbeat_interval_seconds: 10
  worker_heartbeat_timeout_seconds: 30
  
  # 任务超时
  default_task_timeout_seconds: 3600
  max_task_timeout_seconds: 86400
  
  # GPU 配置
  gpu_ids: [0, 1, 2, 3, 4, 5, 6, 7]
  reserved_gpu_ids: []  # 保留的 GPU（不参与调度）
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
