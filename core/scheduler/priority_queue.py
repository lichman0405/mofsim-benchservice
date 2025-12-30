"""
优先级队列实现

基于 Redis Sorted Set 实现的优先级队列
参考文档: docs/architecture/gpu_scheduler_design.md 3.1 节
"""
from enum import IntEnum
from typing import Optional, List, Tuple
from dataclasses import dataclass
import time

import structlog
from redis import Redis

logger = structlog.get_logger(__name__)


class TaskPriority(IntEnum):
    """任务优先级"""
    CRITICAL = 0  # 最高优先级，立即调度
    HIGH = 1      # 高优先级，优先处理
    NORMAL = 2    # 普通优先级（默认）
    LOW = 3       # 低优先级，批量任务


@dataclass
class QueuedTask:
    """队列中的任务"""
    task_id: str
    priority: TaskPriority
    enqueued_at: float
    score: float
    position: int = 0


class PriorityQueue:
    """
    基于 Redis Sorted Set 的优先级队列
    
    Score 计算: priority_weight * 1e12 + timestamp
    - 较小的 score 优先出队
    - 同优先级按时间 FIFO
    """
    
    QUEUE_KEY = "mofsim:task_queue"
    TASK_META_PREFIX = "mofsim:task_meta:"
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    def _calculate_score(self, priority: TaskPriority) -> float:
        """计算任务 score"""
        return priority.value * 1e12 + time.time()
    
    def enqueue(
        self,
        task_id: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: Optional[dict] = None
    ) -> float:
        """
        任务入队
        
        Args:
            task_id: 任务 ID
            priority: 优先级
            metadata: 任务元数据（可选）
        
        Returns:
            任务的 score
        """
        score = self._calculate_score(priority)
        
        # 使用事务保证原子性
        pipe = self.redis.pipeline()
        pipe.zadd(self.QUEUE_KEY, {task_id: score})
        
        if metadata:
            meta_key = f"{self.TASK_META_PREFIX}{task_id}"
            pipe.hset(meta_key, mapping={
                "priority": priority.name,
                "enqueued_at": str(time.time()),
                **{k: str(v) for k, v in metadata.items()}
            })
            pipe.expire(meta_key, 86400 * 7)  # 7 天过期
        
        pipe.execute()
        
        logger.info(
            "task_enqueued",
            task_id=task_id,
            priority=priority.name,
            score=score,
            queue_size=self.size()
        )
        
        return score
    
    def dequeue(self) -> Optional[str]:
        """
        出队：取 score 最小的任务
        
        Returns:
            任务 ID，如果队列为空返回 None
        """
        result = self.redis.zpopmin(self.QUEUE_KEY, count=1)
        if result:
            task_id = result[0][0]
            if isinstance(task_id, bytes):
                task_id = task_id.decode()
            
            logger.info(
                "task_dequeued",
                task_id=task_id,
                queue_size=self.size()
            )
            return task_id
        return None
    
    def peek(self, count: int = 10) -> List[QueuedTask]:
        """
        查看队列前 N 个任务（不移除）
        
        Args:
            count: 返回数量
        
        Returns:
            QueuedTask 列表
        """
        results = self.redis.zrange(
            self.QUEUE_KEY, 0, count - 1, withscores=True
        )
        
        tasks = []
        for i, (task_id, score) in enumerate(results):
            if isinstance(task_id, bytes):
                task_id = task_id.decode()
            
            # 反向计算优先级和入队时间
            priority_value = int(score // 1e12)
            enqueued_at = score % 1e12
            
            tasks.append(QueuedTask(
                task_id=task_id,
                priority=TaskPriority(min(priority_value, 3)),
                enqueued_at=enqueued_at,
                score=score,
                position=i
            ))
        
        return tasks
    
    def peek_first(self) -> Optional[str]:
        """查看队首任务"""
        result = self.redis.zrange(self.QUEUE_KEY, 0, 0)
        if result:
            task_id = result[0]
            if isinstance(task_id, bytes):
                task_id = task_id.decode()
            return task_id
        return None
    
    def remove(self, task_id: str) -> bool:
        """
        移除任务（用于取消）
        
        Args:
            task_id: 任务 ID
        
        Returns:
            是否成功移除
        """
        removed = self.redis.zrem(self.QUEUE_KEY, task_id)
        if removed:
            # 清理元数据
            self.redis.delete(f"{self.TASK_META_PREFIX}{task_id}")
            logger.info("task_removed_from_queue", task_id=task_id)
        return bool(removed)
    
    def position(self, task_id: str) -> Optional[int]:
        """
        获取任务在队列中的位置
        
        Args:
            task_id: 任务 ID
        
        Returns:
            位置（0-indexed），不在队列中返回 None
        """
        rank = self.redis.zrank(self.QUEUE_KEY, task_id)
        return rank
    
    def size(self) -> int:
        """获取队列大小"""
        return self.redis.zcard(self.QUEUE_KEY)
    
    def size_by_priority(self) -> dict:
        """按优先级统计队列大小"""
        counts = {p.name: 0 for p in TaskPriority}
        
        # 获取所有任务的 score
        all_tasks = self.redis.zrange(self.QUEUE_KEY, 0, -1, withscores=True)
        
        for _, score in all_tasks:
            priority_value = int(score // 1e12)
            priority = TaskPriority(min(priority_value, 3))
            counts[priority.name] += 1
        
        return counts
    
    def clear(self) -> int:
        """清空队列（慎用）"""
        count = self.redis.zcard(self.QUEUE_KEY)
        self.redis.delete(self.QUEUE_KEY)
        logger.warning("queue_cleared", removed_count=count)
        return count
    
    def get_wait_time(self, task_id: str) -> Optional[float]:
        """获取任务等待时间（秒）"""
        meta_key = f"{self.TASK_META_PREFIX}{task_id}"
        enqueued_at = self.redis.hget(meta_key, "enqueued_at")
        if enqueued_at:
            return time.time() - float(enqueued_at)
        return None
    
    def reprioritize(self, task_id: str, new_priority: TaskPriority) -> bool:
        """
        修改任务优先级
        
        保持原有的入队时间，只修改优先级
        """
        # 获取当前 score
        current_score = self.redis.zscore(self.QUEUE_KEY, task_id)
        if current_score is None:
            return False
        
        # 提取原入队时间
        enqueued_at = current_score % 1e12
        
        # 计算新 score
        new_score = new_priority.value * 1e12 + enqueued_at
        
        # 更新
        self.redis.zadd(self.QUEUE_KEY, {task_id: new_score})
        
        logger.info(
            "task_reprioritized",
            task_id=task_id,
            new_priority=new_priority.name,
            old_score=current_score,
            new_score=new_score
        )
        
        return True


class MockPriorityQueue:
    """
    内存版优先级队列（无 Redis 时使用）
    
    仅用于开发和测试，生产环境应使用 Redis 版本
    """
    
    def __init__(self):
        self._queue: List[Tuple[str, float]] = []  # (task_id, score)
        self._metadata: dict = {}
    
    def _calculate_score(self, priority: TaskPriority) -> float:
        return priority.value * 1e12 + time.time()
    
    def enqueue(
        self,
        task_id: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: Optional[dict] = None
    ) -> float:
        score = self._calculate_score(priority)
        self._queue.append((task_id, score))
        self._queue.sort(key=lambda x: x[1])  # 按 score 排序
        
        if metadata:
            self._metadata[task_id] = {
                "priority": priority.name,
                "enqueued_at": str(time.time()),
                **metadata
            }
        
        logger.info(
            "task_enqueued_mock",
            task_id=task_id,
            priority=priority.name,
            queue_size=len(self._queue)
        )
        
        return score
    
    def dequeue(self) -> Optional[str]:
        if not self._queue:
            return None
        task_id, _ = self._queue.pop(0)
        return task_id
    
    def peek(self, count: int = 10) -> List[QueuedTask]:
        tasks = []
        for i, (task_id, score) in enumerate(self._queue[:count]):
            priority_value = int(score // 1e12)
            enqueued_at = score % 1e12
            tasks.append(QueuedTask(
                task_id=task_id,
                priority=TaskPriority(min(priority_value, 3)),
                enqueued_at=enqueued_at,
                score=score,
                position=i
            ))
        return tasks
    
    def peek_first(self) -> Optional[str]:
        if not self._queue:
            return None
        return self._queue[0][0]
    
    def remove(self, task_id: str) -> bool:
        for i, (tid, _) in enumerate(self._queue):
            if tid == task_id:
                self._queue.pop(i)
                self._metadata.pop(task_id, None)
                return True
        return False
    
    def position(self, task_id: str) -> Optional[int]:
        for i, (tid, _) in enumerate(self._queue):
            if tid == task_id:
                return i
        return None
    
    def size(self) -> int:
        return len(self._queue)
    
    def size_by_priority(self) -> dict:
        counts = {p.name: 0 for p in TaskPriority}
        for _, score in self._queue:
            priority_value = int(score // 1e12)
            priority = TaskPriority(min(priority_value, 3))
            counts[priority.name] += 1
        return counts
    
    def clear(self) -> int:
        count = len(self._queue)
        self._queue.clear()
        self._metadata.clear()
        return count
    
    def get_wait_time(self, task_id: str) -> Optional[float]:
        meta = self._metadata.get(task_id)
        if meta and "enqueued_at" in meta:
            return time.time() - float(meta["enqueued_at"])
        return None
    
    def reprioritize(self, task_id: str, new_priority: TaskPriority) -> bool:
        for i, (tid, score) in enumerate(self._queue):
            if tid == task_id:
                enqueued_at = score % 1e12
                new_score = new_priority.value * 1e12 + enqueued_at
                self._queue[i] = (task_id, new_score)
                self._queue.sort(key=lambda x: x[1])
                return True
        return False
