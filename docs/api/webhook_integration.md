# Webhook 集成指南

## 一、概述

MOFSimBench 支持通过 Webhook 在任务完成时向外部系统发送通知。

---

## 二、配置 Webhook

### 2.1 提交任务时指定

```python
task = client.optimization.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    webhook_url="https://your-server.com/webhook/mofsim"
)
```

### 2.2 API 请求

```bash
curl -X POST https://api.mofsim.com/v1/tasks/optimization \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mace_off_prod",
    "structure": {"source": "builtin", "name": "MOF-5_primitive"},
    "webhook_url": "https://your-server.com/webhook/mofsim"
  }'
```

---

## 三、Webhook 请求格式

### 3.1 任务完成

```json
{
  "event": "task.completed",
  "timestamp": "2024-01-15T10:35:00.123Z",
  "task_id": "task_abc123",
  "task_type": "optimization",
  "status": "COMPLETED",
  "model": "mace_off_prod",
  "execution_time_seconds": 245.6,
  "result_url": "https://api.mofsim.com/v1/tasks/task_abc123/result"
}
```

### 3.2 任务失败

```json
{
  "event": "task.failed",
  "timestamp": "2024-01-15T10:35:00.123Z",
  "task_id": "task_abc123",
  "task_type": "optimization",
  "status": "FAILED",
  "model": "mace_off_prod",
  "error": {
    "type": "OptimizationNotConverged",
    "message": "优化在 500 步后未收敛"
  }
}
```

### 3.3 任务超时

```json
{
  "event": "task.timeout",
  "timestamp": "2024-01-15T10:35:00.123Z",
  "task_id": "task_abc123",
  "task_type": "optimization",
  "status": "TIMEOUT",
  "model": "mace_off_prod",
  "timeout_seconds": 86400
}
```

---

## 四、请求头

每个 Webhook 请求包含以下 HTTP 头：

| Header | 说明 |
|--------|------|
| `Content-Type` | `application/json` |
| `X-MOFSim-Event` | 事件类型 |
| `X-MOFSim-Timestamp` | 事件时间戳 |
| `X-MOFSim-Signature` | 请求签名（如果配置了密钥） |
| `X-MOFSim-Delivery` | 唯一的交付 ID |

---

## 五、签名验证

### 5.1 配置签名密钥

```python
task = client.optimization.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    webhook_url="https://your-server.com/webhook/mofsim",
    webhook_secret="your_webhook_secret"
)
```

### 5.2 验证签名

```python
import hmac
import hashlib

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """验证 Webhook 签名。
    
    Args:
        payload: 请求体原始字节
        signature: X-MOFSim-Signature 头值
        secret: Webhook 密钥
    
    Returns:
        bool: 签名是否有效
    """
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### 5.3 Flask 示例

```python
from flask import Flask, request, abort
import json

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

@app.route("/webhook/mofsim", methods=["POST"])
def handle_webhook():
    # 验证签名
    signature = request.headers.get("X-MOFSim-Signature")
    if not verify_webhook_signature(request.data, signature, WEBHOOK_SECRET):
        abort(401)
    
    # 处理事件
    event = request.json
    event_type = event["event"]
    task_id = event["task_id"]
    
    if event_type == "task.completed":
        handle_task_completed(event)
    elif event_type == "task.failed":
        handle_task_failed(event)
    
    return "", 200

def handle_task_completed(event):
    print(f"任务 {event['task_id']} 完成")
    # 获取结果
    result_url = event["result_url"]
    # ...

def handle_task_failed(event):
    print(f"任务 {event['task_id']} 失败: {event['error']['message']}")
```

### 5.4 FastAPI 示例

```python
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
WEBHOOK_SECRET = "your_webhook_secret"

@app.post("/webhook/mofsim")
async def handle_webhook(request: Request):
    # 获取原始请求体
    payload = await request.body()
    
    # 验证签名
    signature = request.headers.get("X-MOFSim-Signature")
    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 解析事件
    event = await request.json()
    
    # 异步处理
    import asyncio
    asyncio.create_task(process_event(event))
    
    return {"status": "ok"}

async def process_event(event: dict):
    if event["event"] == "task.completed":
        # 异步获取结果
        async with httpx.AsyncClient() as client:
            response = await client.get(
                event["result_url"],
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
            result = response.json()
            # 处理结果...
```

---

## 六、重试机制

### 6.1 重试策略

MOFSimBench 对失败的 Webhook 请求会自动重试：

| 重试次数 | 延迟 |
|---------|------|
| 第 1 次 | 立即 |
| 第 2 次 | 1 分钟后 |
| 第 3 次 | 5 分钟后 |
| 第 4 次 | 15 分钟后 |
| 第 5 次 | 1 小时后 |

### 6.2 失败条件

以下情况视为失败：

- 连接超时（30 秒）
- HTTP 状态码 >= 400
- 响应超时（30 秒）

### 6.3 成功条件

以下状态码视为成功：

- 200 OK
- 201 Created
- 202 Accepted
- 204 No Content

---

## 七、最佳实践

### 7.1 快速响应

Webhook 处理程序应该尽快返回响应：

```python
@app.post("/webhook/mofsim")
async def handle_webhook(request: Request):
    event = await request.json()
    
    # 立即返回，异步处理
    asyncio.create_task(process_event_async(event))
    
    return {"status": "accepted"}
```

### 7.2 幂等处理

使用 `X-MOFSim-Delivery` 头确保幂等：

```python
processed_deliveries = set()

@app.post("/webhook/mofsim")
async def handle_webhook(request: Request):
    delivery_id = request.headers.get("X-MOFSim-Delivery")
    
    # 检查是否已处理
    if delivery_id in processed_deliveries:
        return {"status": "already_processed"}
    
    # 处理事件
    event = await request.json()
    await process_event(event)
    
    # 记录已处理
    processed_deliveries.add(delivery_id)
    
    return {"status": "ok"}
```

### 7.3 错误处理

```python
@app.post("/webhook/mofsim")
async def handle_webhook(request: Request):
    try:
        event = await request.json()
        await process_event(event)
        return {"status": "ok"}
    except Exception as e:
        # 记录错误但返回 200，避免不必要的重试
        logger.error(f"Webhook 处理错误: {e}")
        return {"status": "error", "message": str(e)}
```

---

## 八、调试

### 8.1 查看 Webhook 历史

```python
# 获取任务的 Webhook 历史
deliveries = client.get_webhook_deliveries(task_id="task_abc123")

for d in deliveries:
    print(f"{d.timestamp}: {d.status} ({d.response_code})")
```

### 8.2 手动重发

```python
# 手动触发 Webhook 重发
client.resend_webhook(task_id="task_abc123")
```

### 8.3 测试 Webhook

使用 webhook.site 或 ngrok 进行本地测试：

```bash
# 使用 ngrok 暴露本地端口
ngrok http 8000

# 使用暴露的 URL 作为 webhook_url
```

---

## 九、事件类型

| 事件 | 说明 |
|------|------|
| `task.completed` | 任务成功完成 |
| `task.failed` | 任务执行失败 |
| `task.timeout` | 任务超时 |
| `task.cancelled` | 任务被取消 |
| `task.started` | 任务开始执行（可选） |
| `task.progress` | 任务进度更新（可选） |

### 9.1 启用额外事件

```python
task = client.optimization.submit(
    model="mace_off_prod",
    structure="./my_mof.cif",
    webhook_url="https://your-server.com/webhook/mofsim",
    webhook_events=["task.completed", "task.failed", "task.progress"]
)
```

---

## 十、与常见平台集成

### 10.1 Slack

```python
import requests

def send_to_slack(event):
    if event["event"] == "task.completed":
        color = "good"
        text = f"✅ 任务完成: {event['task_id']}"
    else:
        color = "danger"
        text = f"❌ 任务失败: {event['task_id']}"
    
    requests.post(
        "https://hooks.slack.com/services/xxx",
        json={
            "attachments": [{
                "color": color,
                "text": text,
                "fields": [
                    {"title": "类型", "value": event["task_type"], "short": True},
                    {"title": "模型", "value": event["model"], "short": True}
                ]
            }]
        }
    )
```

### 10.2 Discord

```python
def send_to_discord(event):
    requests.post(
        "https://discord.com/api/webhooks/xxx",
        json={
            "embeds": [{
                "title": f"任务 {event['status']}",
                "description": f"任务 ID: {event['task_id']}",
                "color": 0x00ff00 if event["event"] == "task.completed" else 0xff0000
            }]
        }
    )
```

### 10.3 Email

```python
import smtplib
from email.mime.text import MIMEText

def send_email(event):
    msg = MIMEText(f"任务 {event['task_id']} {event['status']}")
    msg["Subject"] = f"MOFSimBench 任务通知"
    msg["From"] = "noreply@example.com"
    msg["To"] = "user@example.com"
    
    with smtplib.SMTP("smtp.example.com") as server:
        server.send_message(msg)
```

---

*文档版本：v1.0*  
*创建日期：2025年12月30日*
