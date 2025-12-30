"""
Webhook 回调客户端

参考文档: docs/engineering_requirements.md 第七节
实现任务完成后的 HTTP 回调通知
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from threading import Lock
import httpx
import structlog

logger = structlog.get_logger(__name__)


class CallbackEvent(str, Enum):
    """回调事件类型"""
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMEOUT = "task.timeout"
    TASK_PROGRESS = "task.progress"


@dataclass
class WebhookConfig:
    """Webhook 配置"""
    url: str
    events: List[CallbackEvent] = field(default_factory=lambda: [
        CallbackEvent.TASK_COMPLETED,
        CallbackEvent.TASK_FAILED,
    ])
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 5.0  # 初始重试延迟（秒）
    retry_backoff: float = 2.0  # 重试延迟倍增因子
    secret: Optional[str] = None  # 用于签名验证


@dataclass
class CallbackRecord:
    """回调记录"""
    id: str
    task_id: str
    event: CallbackEvent
    url: str
    payload: Dict[str, Any]
    created_at: datetime
    sent_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    retries: int = 0
    success: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "event": self.event.value,
            "url": self.url,
            "created_at": self.created_at.isoformat() + "Z",
            "sent_at": self.sent_at.isoformat() + "Z" if self.sent_at else None,
            "response_status": self.response_status,
            "retries": self.retries,
            "success": self.success,
            "error": self.error,
        }


class WebhookClient:
    """
    Webhook 回调客户端
    
    功能:
    - 发送 HTTP POST 回调
    - 失败自动重试（指数退避）
    - 签名验证支持
    - 回调记录追踪
    """
    
    def __init__(
        self,
        default_timeout: float = 30.0,
        default_max_retries: int = 3,
        default_retry_delay: float = 5.0,
    ):
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        self.default_retry_delay = default_retry_delay
        
        # 回调记录（内存缓存，最近 1000 条）
        self._records: List[CallbackRecord] = []
        self._max_records = 1000
        self._lock = Lock()
        
        # 待重试队列
        self._retry_queue: asyncio.Queue = asyncio.Queue()
        self._retry_task: Optional[asyncio.Task] = None
    
    async def send(
        self,
        config: WebhookConfig,
        event: CallbackEvent,
        task_id: str,
        payload: Dict[str, Any],
    ) -> CallbackRecord:
        """
        发送 Webhook 回调
        
        Args:
            config: Webhook 配置
            event: 事件类型
            task_id: 任务 ID
            payload: 回调数据
        
        Returns:
            回调记录
        """
        # 检查事件是否需要回调
        if event not in config.events:
            logger.debug("callback_event_skipped", callback_event=event.value, task_id=task_id)
            return None
        
        # 构建完整的回调数据
        callback_payload = {
            "event": event.value,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": payload,
        }
        
        # 添加签名（如果配置了 secret）
        if config.secret:
            callback_payload["signature"] = self._sign_payload(callback_payload, config.secret)
        
        # 创建记录
        record = CallbackRecord(
            id=f"cb_{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            event=event,
            url=config.url,
            payload=callback_payload,
            created_at=datetime.utcnow(),
        )
        
        # 发送请求
        await self._send_with_retry(config, record)
        
        # 保存记录
        self._save_record(record)
        
        return record
    
    async def _send_with_retry(
        self,
        config: WebhookConfig,
        record: CallbackRecord,
    ) -> None:
        """带重试的发送"""
        retry_delay = config.retry_delay
        
        for attempt in range(config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=config.timeout) as client:
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "MOFSimBench-Webhook/1.0",
                        "X-Webhook-Event": record.event.value,
                        "X-Webhook-ID": record.id,
                        **config.headers,
                    }
                    
                    response = await client.post(
                        config.url,
                        json=record.payload,
                        headers=headers,
                    )
                    
                    record.sent_at = datetime.utcnow()
                    record.response_status = response.status_code
                    record.response_body = response.text[:1000] if response.text else None
                    record.retries = attempt
                    
                    if response.is_success:
                        record.success = True
                        logger.info(
                            "webhook_sent",
                            record_id=record.id,
                            task_id=record.task_id,
                            event=record.event.value,
                            status=response.status_code,
                            retries=attempt,
                        )
                        return
                    else:
                        record.error = f"HTTP {response.status_code}"
                        logger.warning(
                            "webhook_failed",
                            record_id=record.id,
                            task_id=record.task_id,
                            status=response.status_code,
                            attempt=attempt + 1,
                        )
                        
            except httpx.TimeoutException as e:
                record.error = f"Timeout: {e}"
                logger.warning(
                    "webhook_timeout",
                    record_id=record.id,
                    task_id=record.task_id,
                    attempt=attempt + 1,
                )
            except httpx.RequestError as e:
                record.error = f"Request error: {e}"
                logger.warning(
                    "webhook_request_error",
                    record_id=record.id,
                    task_id=record.task_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
            except Exception as e:
                record.error = f"Unexpected error: {e}"
                logger.error(
                    "webhook_unexpected_error",
                    record_id=record.id,
                    task_id=record.task_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
            
            # 等待后重试
            if attempt < config.max_retries:
                await asyncio.sleep(retry_delay)
                retry_delay *= config.retry_backoff
        
        # 所有重试都失败
        record.retries = config.max_retries
        logger.error(
            "webhook_all_retries_failed",
            record_id=record.id,
            task_id=record.task_id,
            event=record.event.value,
            url=config.url,
        )
    
    def _sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """签名回调数据"""
        import hashlib
        import hmac
        import json
        
        # 排除签名字段本身
        data = {k: v for k, v in payload.items() if k != "signature"}
        message = json.dumps(data, sort_keys=True, separators=(",", ":"))
        
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def _save_record(self, record: CallbackRecord) -> None:
        """保存回调记录"""
        with self._lock:
            self._records.append(record)
            # 保持最大记录数
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
    
    def get_records(
        self,
        task_id: Optional[str] = None,
        event: Optional[CallbackEvent] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[CallbackRecord]:
        """
        获取回调记录
        
        Args:
            task_id: 按任务 ID 过滤
            event: 按事件类型过滤
            success: 按成功状态过滤
            limit: 返回数量限制
        
        Returns:
            回调记录列表
        """
        with self._lock:
            records = self._records[:]
        
        # 过滤
        if task_id:
            records = [r for r in records if r.task_id == task_id]
        if event:
            records = [r for r in records if r.event == event]
        if success is not None:
            records = [r for r in records if r.success == success]
        
        # 按时间倒序返回
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取回调统计"""
        with self._lock:
            records = self._records[:]
        
        total = len(records)
        success = sum(1 for r in records if r.success)
        failed = total - success
        
        # 按事件统计
        by_event = {}
        for r in records:
            event = r.event.value
            if event not in by_event:
                by_event[event] = {"total": 0, "success": 0, "failed": 0}
            by_event[event]["total"] += 1
            if r.success:
                by_event[event]["success"] += 1
            else:
                by_event[event]["failed"] += 1
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
            "by_event": by_event,
        }


# 全局单例
_webhook_client: Optional[WebhookClient] = None


def get_webhook_client() -> WebhookClient:
    """获取 Webhook 客户端单例"""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = WebhookClient()
    return _webhook_client


async def send_task_callback(
    task_id: str,
    event: CallbackEvent,
    callback_url: Optional[str],
    callback_events: Optional[List[str]],
    payload: Dict[str, Any],
) -> Optional[CallbackRecord]:
    """
    便捷函数：发送任务回调
    
    Args:
        task_id: 任务 ID
        event: 事件类型
        callback_url: 回调 URL
        callback_events: 订阅的事件列表
        payload: 回调数据
    
    Returns:
        回调记录（如果发送了）
    """
    if not callback_url:
        return None
    
    # 转换事件字符串为枚举
    events = [CallbackEvent.TASK_COMPLETED, CallbackEvent.TASK_FAILED]
    if callback_events:
        events = []
        for e in callback_events:
            try:
                events.append(CallbackEvent(e))
            except ValueError:
                pass
    
    config = WebhookConfig(
        url=callback_url,
        events=events,
    )
    
    client = get_webhook_client()
    return await client.send(config, event, task_id, payload)
