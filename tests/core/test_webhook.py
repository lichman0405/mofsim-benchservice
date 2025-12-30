"""
Webhook 回调客户端测试
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID
from datetime import datetime

from core.callback.webhook import (
    WebhookClient,
    WebhookConfig,
    CallbackEvent,
    CallbackRecord,
    get_webhook_client,
    send_task_callback,
)


class TestCallbackEvent:
    """CallbackEvent 测试"""

    def test_event_values(self):
        """测试事件值"""
        assert CallbackEvent.TASK_CREATED.value == "task.created"
        assert CallbackEvent.TASK_STARTED.value == "task.started"
        assert CallbackEvent.TASK_COMPLETED.value == "task.completed"
        assert CallbackEvent.TASK_FAILED.value == "task.failed"
        assert CallbackEvent.TASK_CANCELLED.value == "task.cancelled"
        assert CallbackEvent.TASK_TIMEOUT.value == "task.timeout"
        assert CallbackEvent.TASK_PROGRESS.value == "task.progress"


class TestWebhookConfig:
    """WebhookConfig 测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = WebhookConfig(url="https://example.com/webhook")
        
        assert config.url == "https://example.com/webhook"
        assert config.secret is None
        assert config.max_retries == 3
        assert config.timeout == 30.0

    def test_custom_config(self):
        """测试自定义配置"""
        config = WebhookConfig(
            url="https://api.example.com/callback",
            secret="my-secret-key",
            max_retries=5,
            timeout=60.0,
            headers={"X-Custom": "value"},
        )
        
        assert config.url == "https://api.example.com/callback"
        assert config.secret == "my-secret-key"
        assert config.max_retries == 5
        assert config.timeout == 60.0
        assert config.headers == {"X-Custom": "value"}

    def test_default_events(self):
        """测试默认订阅事件"""
        config = WebhookConfig(url="https://example.com/webhook")
        
        assert CallbackEvent.TASK_COMPLETED in config.events
        assert CallbackEvent.TASK_FAILED in config.events


class TestCallbackRecord:
    """CallbackRecord 测试"""

    def test_record_creation(self):
        """测试记录创建"""
        record = CallbackRecord(
            id="cb_test123",
            task_id="task_456",
            event=CallbackEvent.TASK_COMPLETED,
            url="https://example.com/webhook",
            payload={"task_id": "123", "status": "completed"},
            created_at=datetime.utcnow(),
        )
        
        assert record.id == "cb_test123"
        assert record.task_id == "task_456"
        assert record.event == CallbackEvent.TASK_COMPLETED
        assert record.success is False
        assert record.retries == 0
        assert record.response_status is None
        assert record.error is None

    def test_record_to_dict(self):
        """测试记录转字典"""
        record = CallbackRecord(
            id="cb_test456",
            task_id="task_789",
            event=CallbackEvent.TASK_FAILED,
            url="https://example.com/webhook",
            payload={"task_id": "456", "error": "timeout"},
            created_at=datetime.utcnow(),
        )
        
        data = record.to_dict()
        
        assert data["id"] == "cb_test456"
        assert data["task_id"] == "task_789"
        assert data["event"] == "task.failed"
        assert data["success"] is False
        assert "created_at" in data


class TestWebhookClient:
    """WebhookClient 测试"""

    def test_client_creation(self):
        """测试客户端创建"""
        client = WebhookClient()
        assert client is not None
        assert client.default_max_retries == 3
        assert client.default_timeout == 30.0

    def test_custom_client_creation(self):
        """测试自定义客户端创建"""
        client = WebhookClient(
            default_timeout=60.0,
            default_max_retries=5,
            default_retry_delay=10.0,
        )
        
        assert client.default_timeout == 60.0
        assert client.default_max_retries == 5
        assert client.default_retry_delay == 10.0

    def test_get_records_empty(self):
        """测试获取空记录列表"""
        client = WebhookClient()
        records = client.get_records()
        assert records == []

    def test_get_stats_empty(self):
        """测试获取空统计"""
        client = WebhookClient()
        stats = client.get_stats()
        
        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_send_skips_unsubscribed_event(self):
        """测试跳过未订阅的事件"""
        client = WebhookClient()
        
        config = WebhookConfig(
            url="https://example.com/webhook",
            events=[CallbackEvent.TASK_COMPLETED],  # 只订阅完成事件
        )
        
        # 发送失败事件（未订阅）
        record = await client.send(
            config=config,
            event=CallbackEvent.TASK_FAILED,
            task_id="task_123",
            payload={"status": "failed"},
        )
        
        # 应该返回 None（跳过）
        assert record is None


class TestGetWebhookClient:
    """get_webhook_client 单例测试"""

    def test_singleton(self):
        """测试单例模式"""
        client1 = get_webhook_client()
        client2 = get_webhook_client()
        assert client1 is client2


class TestSendTaskCallback:
    """send_task_callback 便捷函数测试"""

    @pytest.mark.asyncio
    async def test_no_callback_url(self):
        """测试无回调 URL 时返回 None"""
        result = await send_task_callback(
            task_id="task_123",
            event=CallbackEvent.TASK_COMPLETED,
            callback_url=None,
            callback_events=None,
            payload={"status": "completed"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_events_parsing(self):
        """测试回调事件解析"""
        # 使用 mock 避免实际 HTTP 请求
        with patch.object(WebhookClient, 'send', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = None
            
            await send_task_callback(
                task_id="task_123",
                event=CallbackEvent.TASK_COMPLETED,
                callback_url="https://example.com/webhook",
                callback_events=["task.completed", "task.failed"],
                payload={"status": "completed"},
            )
            
            # 验证 send 被调用
            assert mock_send.called
