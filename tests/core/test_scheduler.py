"""
调度器模块测试

测试 GPU 调度器、优先级队列、任务生命周期管理
"""
import pytest
import time
import asyncio

from core.scheduler import (
    PriorityQueue,
    MockPriorityQueue,
    TaskPriority,
    QueuedTask,
    GPUManager,
    GPUState,
    GPUStatus,
    Scheduler,
    TaskLifecycle,
    TaskState,
    TaskStateTransition,
    TaskTimeoutManager,
)


class TestMockPriorityQueue:
    """测试内存优先级队列"""
    
    def test_enqueue_dequeue(self):
        """测试入队和出队"""
        queue = MockPriorityQueue()
        
        queue.enqueue("task-1", TaskPriority.NORMAL)
        queue.enqueue("task-2", TaskPriority.HIGH)
        queue.enqueue("task-3", TaskPriority.LOW)
        
        assert queue.size() == 3
        
        # 高优先级应该先出队
        assert queue.dequeue() == "task-2"
        assert queue.dequeue() == "task-1"
        assert queue.dequeue() == "task-3"
        assert queue.dequeue() is None
    
    def test_priority_order(self):
        """测试优先级排序"""
        queue = MockPriorityQueue()
        
        queue.enqueue("low-1", TaskPriority.LOW)
        queue.enqueue("critical-1", TaskPriority.CRITICAL)
        queue.enqueue("normal-1", TaskPriority.NORMAL)
        queue.enqueue("high-1", TaskPriority.HIGH)
        
        tasks = queue.peek(10)
        priorities = [t.priority for t in tasks]
        
        assert priorities == [
            TaskPriority.CRITICAL,
            TaskPriority.HIGH,
            TaskPriority.NORMAL,
            TaskPriority.LOW,
        ]
    
    def test_fifo_within_priority(self):
        """测试同优先级 FIFO"""
        queue = MockPriorityQueue()
        
        queue.enqueue("task-1", TaskPriority.NORMAL)
        time.sleep(0.01)  # 确保时间戳不同
        queue.enqueue("task-2", TaskPriority.NORMAL)
        time.sleep(0.01)
        queue.enqueue("task-3", TaskPriority.NORMAL)
        
        assert queue.dequeue() == "task-1"
        assert queue.dequeue() == "task-2"
        assert queue.dequeue() == "task-3"
    
    def test_remove(self):
        """测试移除任务"""
        queue = MockPriorityQueue()
        
        queue.enqueue("task-1", TaskPriority.NORMAL)
        queue.enqueue("task-2", TaskPriority.NORMAL)
        
        assert queue.remove("task-1") is True
        assert queue.size() == 1
        assert queue.remove("task-1") is False  # 已移除
    
    def test_position(self):
        """测试获取位置"""
        queue = MockPriorityQueue()
        
        queue.enqueue("task-1", TaskPriority.HIGH)
        queue.enqueue("task-2", TaskPriority.LOW)
        
        assert queue.position("task-1") == 0
        assert queue.position("task-2") == 1
        assert queue.position("task-3") is None
    
    def test_size_by_priority(self):
        """测试按优先级统计"""
        queue = MockPriorityQueue()
        
        queue.enqueue("t1", TaskPriority.CRITICAL)
        queue.enqueue("t2", TaskPriority.HIGH)
        queue.enqueue("t3", TaskPriority.HIGH)
        queue.enqueue("t4", TaskPriority.NORMAL)
        
        counts = queue.size_by_priority()
        
        assert counts["CRITICAL"] == 1
        assert counts["HIGH"] == 2
        assert counts["NORMAL"] == 1
        assert counts["LOW"] == 0
    
    def test_reprioritize(self):
        """测试修改优先级"""
        queue = MockPriorityQueue()
        
        queue.enqueue("task-1", TaskPriority.LOW)
        queue.enqueue("task-2", TaskPriority.NORMAL)
        
        # task-1 从 LOW 升级到 CRITICAL
        assert queue.reprioritize("task-1", TaskPriority.CRITICAL) is True
        
        # 现在 task-1 应该先出队
        assert queue.dequeue() == "task-1"


class TestGPUManager:
    """测试 GPU 管理器"""
    
    def test_mock_mode(self):
        """测试模拟模式"""
        manager = GPUManager(gpu_ids=[0, 1], mock_mode=True)
        
        assert manager.mock_mode is True
        assert len(manager.gpu_ids) == 2
        assert 0 in manager.gpu_states
        assert 1 in manager.gpu_states
    
    def test_get_free_gpus(self):
        """测试获取空闲 GPU"""
        manager = GPUManager(gpu_ids=[0, 1, 2], mock_mode=True)
        
        free_gpus = manager.get_free_gpus()
        assert len(free_gpus) == 3
        
        # 分配一个 GPU
        asyncio.run(manager.allocate(0, "task-1"))
        
        free_gpus = manager.get_free_gpus()
        assert len(free_gpus) == 2
        assert 0 not in free_gpus
    
    def test_allocate_release(self):
        """测试分配和释放"""
        manager = GPUManager(gpu_ids=[0], mock_mode=True)
        
        # 分配
        result = asyncio.run(manager.allocate(0, "task-1"))
        assert result is True
        assert manager.gpu_states[0].status == GPUStatus.BUSY
        assert manager.gpu_states[0].current_task_id == "task-1"
        
        # 再次分配应该失败
        result = asyncio.run(manager.allocate(0, "task-2"))
        assert result is False
        
        # 释放
        asyncio.run(manager.release(0))
        assert manager.gpu_states[0].status == GPUStatus.FREE
        assert manager.gpu_states[0].current_task_id is None
    
    def test_reserved_gpus(self):
        """测试保留 GPU"""
        manager = GPUManager(
            gpu_ids=[0, 1, 2],
            reserved_gpu_ids=[2],
            mock_mode=True
        )
        
        assert manager.gpu_states[2].status == GPUStatus.RESERVED
        assert 2 not in manager.get_free_gpus()
    
    def test_model_cache(self):
        """测试模型缓存"""
        manager = GPUManager(gpu_ids=[0], mock_mode=True)
        
        manager.add_loaded_model(0, "model-a")
        assert "model-a" in manager.gpu_states[0].loaded_models
        
        manager.add_loaded_model(0, "model-b")
        assert len(manager.gpu_states[0].loaded_models) == 2
        
        # 超过最大数量时应该淘汰最早的
        manager.add_loaded_model(0, "model-c")
        assert len(manager.gpu_states[0].loaded_models) == 2
        assert "model-a" not in manager.gpu_states[0].loaded_models
    
    def test_get_gpu_with_model(self):
        """测试获取已加载模型的 GPU"""
        manager = GPUManager(gpu_ids=[0, 1], mock_mode=True)
        
        manager.add_loaded_model(1, "mace-mp-0")
        
        gpu_id = manager.get_gpu_with_model("mace-mp-0")
        assert gpu_id == 1
        
        gpu_id = manager.get_gpu_with_model("unknown-model")
        assert gpu_id is None
    
    def test_summary(self):
        """测试状态摘要"""
        manager = GPUManager(gpu_ids=[0, 1], mock_mode=True)
        asyncio.run(manager.allocate(0, "task-1"))
        
        summary = manager.get_summary()
        
        assert summary["total_gpus"] == 2
        assert summary["free_gpus"] == 1
        assert summary["busy_gpus"] == 1
        assert summary["mock_mode"] is True


class TestTaskLifecycle:
    """测试任务生命周期"""
    
    def test_valid_transitions(self):
        """测试有效状态转换"""
        assert TaskLifecycle.can_transition(TaskState.PENDING, TaskState.QUEUED)
        assert TaskLifecycle.can_transition(TaskState.QUEUED, TaskState.ASSIGNED)
        assert TaskLifecycle.can_transition(TaskState.ASSIGNED, TaskState.RUNNING)
        assert TaskLifecycle.can_transition(TaskState.RUNNING, TaskState.COMPLETED)
        assert TaskLifecycle.can_transition(TaskState.RUNNING, TaskState.FAILED)
    
    def test_invalid_transitions(self):
        """测试无效状态转换"""
        assert not TaskLifecycle.can_transition(TaskState.PENDING, TaskState.COMPLETED)
        assert not TaskLifecycle.can_transition(TaskState.COMPLETED, TaskState.RUNNING)
        assert not TaskLifecycle.can_transition(TaskState.FAILED, TaskState.PENDING)
    
    def test_cancellable_states(self):
        """测试可取消状态"""
        assert TaskLifecycle.can_cancel(TaskState.PENDING)
        assert TaskLifecycle.can_cancel(TaskState.QUEUED)
        assert TaskLifecycle.can_cancel(TaskState.RUNNING)
        assert not TaskLifecycle.can_cancel(TaskState.COMPLETED)
        assert not TaskLifecycle.can_cancel(TaskState.FAILED)
    
    def test_terminal_states(self):
        """测试终止状态"""
        assert TaskLifecycle.is_terminal(TaskState.COMPLETED)
        assert TaskLifecycle.is_terminal(TaskState.FAILED)
        assert TaskLifecycle.is_terminal(TaskState.CANCELLED)
        assert not TaskLifecycle.is_terminal(TaskState.RUNNING)
    
    def test_create_transition(self):
        """测试创建状态转换记录"""
        transition = TaskLifecycle.create_transition(
            TaskState.QUEUED,
            TaskState.ASSIGNED,
            reason="GPU available"
        )
        
        assert transition.from_state == TaskState.QUEUED
        assert transition.to_state == TaskState.ASSIGNED
        assert transition.reason == "GPU available"
        assert transition.timestamp > 0
    
    def test_invalid_transition_raises(self):
        """测试无效转换抛出异常"""
        with pytest.raises(ValueError):
            TaskLifecycle.create_transition(
                TaskState.COMPLETED,
                TaskState.RUNNING
            )


class TestTaskTimeoutManager:
    """测试超时管理器"""
    
    def test_default_timeout(self):
        """测试默认超时"""
        timeout = TaskTimeoutManager.get_timeout("unknown-type")
        assert timeout == TaskTimeoutManager.DEFAULT_TIMEOUT
    
    def test_task_type_timeout(self):
        """测试任务类型超时"""
        timeout = TaskTimeoutManager.get_timeout("optimization")
        assert timeout == 1800
        
        timeout = TaskTimeoutManager.get_timeout("stability")
        assert timeout == 7200
    
    def test_custom_timeout(self):
        """测试自定义超时"""
        timeout = TaskTimeoutManager.get_timeout("optimization", custom_timeout=600)
        assert timeout == 600
    
    def test_max_timeout(self):
        """测试最大超时限制"""
        timeout = TaskTimeoutManager.get_timeout("optimization", custom_timeout=999999)
        assert timeout == TaskTimeoutManager.MAX_TIMEOUT
    
    def test_is_timed_out(self):
        """测试超时检查"""
        started_at = time.time() - 100  # 100 秒前
        
        # 单点能量超时 600 秒，还未超时
        assert not TaskTimeoutManager.is_timed_out(started_at, "single-point")
        
        # 如果自定义超时 50 秒，则已超时
        assert TaskTimeoutManager.is_timed_out(started_at, "single-point", custom_timeout=50)


class TestScheduler:
    """测试调度器"""
    
    def test_estimate_memory(self):
        """测试显存估算"""
        manager = GPUManager(gpu_ids=[0], mock_mode=True)
        queue = MockPriorityQueue()
        scheduler = Scheduler(manager, queue)
        
        task_info = {
            "model_name": "mace-mp-0-medium",
            "task_type": "optimization",
            "n_atoms": 100,
        }
        
        memory = scheduler._estimate_memory(task_info)
        
        # 4000 (base) + 200 (atoms) * 1.2 (multiplier) = 5040
        assert memory == 5040
    
    def test_gpu_score_calculation(self):
        """测试 GPU 评分"""
        manager = GPUManager(gpu_ids=[0, 1], mock_mode=True)
        queue = MockPriorityQueue()
        scheduler = Scheduler(manager, queue)
        
        # GPU 0 已加载模型
        manager.add_loaded_model(0, "mace-mp-0")
        
        score_0 = scheduler._calculate_gpu_score(
            manager.gpu_states[0], "mace-mp-0"
        )
        score_1 = scheduler._calculate_gpu_score(
            manager.gpu_states[1], "mace-mp-0"
        )
        
        # GPU 0 有模型亲和性，分数更高
        assert score_0 > score_1
    
    def test_schedule_stats(self):
        """测试调度统计"""
        manager = GPUManager(gpu_ids=[0], mock_mode=True)
        queue = MockPriorityQueue()
        scheduler = Scheduler(manager, queue)
        
        stats = scheduler.get_stats()
        
        assert "schedule_attempts" in stats
        assert "queue_size" in stats
        assert "gpu_summary" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
