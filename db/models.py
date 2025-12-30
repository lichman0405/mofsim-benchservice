"""
数据库模型定义

参考文档: docs/architecture/database_design.md 第三节
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey,
    Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


# ===== 枚举类型 =====

import enum

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class TaskType(str, enum.Enum):
    OPTIMIZATION = "optimization"
    STABILITY = "stability"
    BULK_MODULUS = "bulk-modulus"
    HEAT_CAPACITY = "heat-capacity"
    INTERACTION_ENERGY = "interaction-energy"
    SINGLE_POINT_ENERGY = "single-point-energy"


class TaskPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class AlertLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


# ===== 模型定义 =====

class Task(Base):
    """
    任务表
    
    存储所有计算任务信息
    """
    __tablename__ = "tasks"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 基本信息
    task_type = Column(SQLEnum(TaskType), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    priority = Column(SQLEnum(TaskPriority), nullable=False, default=TaskPriority.NORMAL, index=True)
    
    # 关联
    model_name = Column(String(100), nullable=False, index=True)
    structure_id = Column(UUID(as_uuid=True), ForeignKey("structures.id"), nullable=True)
    structure_name = Column(String(255), nullable=True)  # 冗余字段，便于查询
    
    # 参数与结果
    parameters = Column(JSONB, default={})
    result = Column(JSONB, nullable=True)
    output_files = Column(JSONB, nullable=True)  # {"optimized_structure": "...", "trajectory": "..."}
    
    # 执行信息
    gpu_id = Column(Integer, nullable=True)
    celery_task_id = Column(String(50), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # 性能指标
    duration_seconds = Column(Float, nullable=True)
    peak_memory_mb = Column(Integer, nullable=True)
    
    # 回调配置
    callback_url = Column(String(500), nullable=True)
    callback_events = Column(JSONB, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    structure = relationship("Structure", back_populates="tasks")
    
    # 索引
    __table_args__ = (
        Index("ix_tasks_status_priority", "status", "priority"),
        Index("ix_tasks_created_at_desc", "created_at", postgresql_using="btree"),
    )


class Structure(Base):
    """
    结构文件表
    
    存储上传的结构文件元数据
    """
    __tablename__ = "structures"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 文件信息
    name = Column(String(255), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    format = Column(String(20), nullable=False)  # cif, xyz
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False, unique=True)  # SHA256
    
    # 结构信息（解析后填充）
    n_atoms = Column(Integer, nullable=True)
    formula = Column(String(200), nullable=True)
    
    # 元数据
    is_builtin = Column(Boolean, default=False, index=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    tasks = relationship("Task", back_populates="structure")


class Model(Base):
    """
    模型注册表
    
    存储可用的 MLIP 模型信息
    """
    __tablename__ = "models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模型标识
    name = Column(String(100), nullable=False, unique=True, index=True)
    framework = Column(String(50), nullable=False, index=True)  # mace, orb, omat24, grace, sevennet, mattersim
    
    # 模型信息
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=True)
    
    # 配置
    config = Column(JSONB, default={})
    supported_elements = Column(JSONB, nullable=True)  # ["C", "H", "O", "N", "Cu", ...]
    with_d3 = Column(Boolean, default=False)
    
    # 状态
    is_builtin = Column(Boolean, default=True)
    is_enabled = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomModel(Base):
    """
    自定义模型表
    
    存储用户上传的模型
    """
    __tablename__ = "custom_models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模型信息
    name = Column(String(100), nullable=False, index=True)
    framework = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    
    # 文件信息
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)
    
    # 配置
    config = Column(JSONB, default={})
    with_d3 = Column(Boolean, default=False)
    
    # 验证状态
    is_validated = Column(Boolean, default=False)
    validation_message = Column(Text, nullable=True)
    
    # 所有者（预留认证）
    owner_id = Column(UUID(as_uuid=True), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AlertRule(Base):
    """
    告警规则表
    """
    __tablename__ = "alert_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 规则信息
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 条件
    level = Column(SQLEnum(AlertLevel), nullable=False, default=AlertLevel.WARNING)
    condition = Column(JSONB, nullable=False)  # {"metric": "queue_length", "op": ">", "value": 100}
    
    # 通知配置
    notification_channels = Column(JSONB, default=[])  # ["email", "webhook"]
    cooldown_seconds = Column(Integer, default=300)  # 触发间隔
    
    # 状态
    is_enabled = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    alerts = relationship("Alert", back_populates="rule")


class Alert(Base):
    """
    告警记录表
    """
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联规则
    rule_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=True)
    
    # 告警信息
    level = Column(SQLEnum(AlertLevel), nullable=False)
    alert_type = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSONB, default={})
    
    # 状态
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关系
    rule = relationship("AlertRule", back_populates="alerts")
    
    # 索引
    __table_args__ = (
        Index("ix_alerts_resolved_created", "resolved", "created_at"),
    )
