"""
统一响应格式

参考文档: docs/engineering_requirements.md 5.1 节
"""
from pydantic import BaseModel, Field
from typing import TypeVar, Generic, Optional, Any
from datetime import datetime
import uuid

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """错误详情"""
    type: str = Field(..., description="错误类型")
    detail: str = Field(..., description="错误详细说明")
    field: Optional[str] = Field(None, description="相关字段")


class APIResponse(BaseModel, Generic[T]):
    """
    统一 API 响应格式
    
    成功响应:
    {
        "success": true,
        "code": 200,
        "message": "操作成功",
        "data": { ... },
        "timestamp": "2025-12-30T10:00:00Z",
        "request_id": "req_abc123"
    }
    
    错误响应:
    {
        "success": false,
        "code": 40001,
        "message": "结构文件格式不支持",
        "error": { ... },
        "timestamp": "2025-12-30T10:00:00Z",
        "request_id": "req_abc123"
    }
    """
    success: bool = Field(..., description="请求是否成功")
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    error: Optional[ErrorDetail] = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间")
    request_id: str = Field(
        default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}",
        description="请求 ID"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_items: int = Field(..., description="总条目数")
    total_pages: int = Field(..., description="总页数")


def success_response(
    data: Any = None,
    message: str = "操作成功",
    code: int = 200,
) -> dict:
    """构建成功响应"""
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow(),
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
    }


def error_response(
    message: str,
    code: int,
    error_type: str = "Error",
    detail: str = "",
    field: Optional[str] = None,
) -> dict:
    """构建错误响应"""
    return {
        "success": False,
        "code": code,
        "message": message,
        "error": {
            "type": error_type,
            "detail": detail,
            "field": field,
        },
        "timestamp": datetime.utcnow(),
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
    }
