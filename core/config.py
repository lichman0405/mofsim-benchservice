"""
配置管理系统

参考文档: 
- docs/engineering_requirements.md 第八节
- docs/phase1_tasks.md 任务 1.3

支持:
1. 环境变量读取
2. .env 文件
3. 类型验证
4. 敏感信息脱敏
"""
from functools import lru_cache
from typing import Optional, List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, ge=1, le=65535, description="数据库端口")
    user: str = Field(default="mofsim", description="数据库用户")
    password: str = Field(default="", description="数据库密码")
    name: str = Field(default="mofsim_bench", description="数据库名称")
    
    pool_size: int = Field(default=5, ge=1, le=20, description="连接池大小")
    max_overflow: int = Field(default=10, ge=0, le=50, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, ge=5, description="连接超时（秒）")
    
    @property
    def url(self) -> str:
        """构建数据库连接 URL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def async_url(self) -> str:
        """构建异步数据库连接 URL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis 配置"""
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="Redis 主机")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis 端口")
    password: Optional[str] = Field(default=None, description="Redis 密码")
    db: int = Field(default=0, ge=0, le=15, description="Redis 数据库编号")
    
    @property
    def url(self) -> str:
        """构建 Redis 连接 URL"""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class CelerySettings(BaseSettings):
    """Celery 配置"""
    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        extra="ignore"
    )
    
    broker_url: Optional[str] = Field(default=None, description="Broker URL（覆盖 Redis）")
    result_backend: Optional[str] = Field(default=None, description="结果后端 URL")
    
    task_soft_timeout: int = Field(default=3600, ge=60, description="任务软超时（秒）")
    task_hard_timeout: int = Field(default=3900, ge=120, description="任务硬超时（秒）")
    
    worker_prefetch: int = Field(default=1, ge=1, le=10, description="Worker 预取数")
    task_acks_late: bool = Field(default=True, description="延迟确认")


class GPUSettings(BaseSettings):
    """GPU 配置"""
    model_config = SettingsConfigDict(
        env_prefix="GPU_",
        extra="ignore"
    )
    
    visible_devices: Optional[str] = Field(default=None, description="可见 GPU 设备 ID，如 '0,1,2'")
    memory_fraction: float = Field(default=0.9, ge=0.1, le=1.0, description="GPU 显存使用比例")
    
    @property
    def device_list(self) -> List[int]:
        """解析 GPU 设备列表"""
        if not self.visible_devices:
            return []
        return [int(d.strip()) for d in self.visible_devices.split(",") if d.strip()]


class StorageSettings(BaseSettings):
    """存储配置"""
    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        extra="ignore"
    )
    
    base_path: str = Field(default="./data", description="存储根目录")
    upload_path: str = Field(default="./data/uploads", description="上传目录")
    result_path: str = Field(default="./data/results", description="结果目录")
    model_path: str = Field(default="./data/models", description="模型目录")
    log_path: str = Field(default="./data/logs", description="日志目录")
    
    max_upload_size_mb: int = Field(default=100, ge=1, le=1000, description="最大上传大小 (MB)")


class LoggingSettings(BaseSettings):
    """日志配置"""
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore"
    )
    
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="json", description="日志格式: json, console")
    file_path: Optional[str] = Field(default=None, description="日志文件路径")
    max_size_mb: int = Field(default=100, ge=1, le=1000, description="日志文件最大大小 (MB)")
    backup_count: int = Field(default=7, ge=1, le=30, description="保留日志文件数")
    
    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"日志级别必须是 {allowed} 之一")
        return v


class Settings(BaseSettings):
    """
    主配置类
    
    层级:
    1. 环境变量 (最高优先级)
    2. .env 文件
    3. 默认值 (最低优先级)
    
    使用示例:
    >>> settings = Settings()
    >>> print(settings.database.url)
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # 应用基础配置
    app_name: str = Field(default="MOFSimBench", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    debug: bool = Field(default=False, description="调试模式")
    environment: str = Field(default="development", description="运行环境: development, staging, production")
    
    # API 配置
    api_host: str = Field(default="0.0.0.0", description="API 监听地址")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API 监听端口")
    api_prefix: str = Field(default="/api/v1", description="API 路径前缀")
    cors_origins: str = Field(default="*", description="CORS 允许的源，逗号分隔")
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    gpu: GPUSettings = Field(default_factory=GPUSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        v = v.lower()
        if v not in allowed:
            raise ValueError(f"环境必须是 {allowed} 之一")
        return v
    
    @property
    def cors_origin_list(self) -> List[str]:
        """解析 CORS 源列表"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
    
    def get_celery_broker_url(self) -> str:
        """获取 Celery broker URL"""
        return self.celery.broker_url or self.redis.url
    
    def get_celery_result_backend(self) -> str:
        """获取 Celery 结果后端 URL"""
        return self.celery.result_backend or self.redis.url
    
    def display_config(self) -> dict:
        """返回脱敏后的配置（用于日志/调试）"""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "debug": self.debug,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "database_host": self.database.host,
            "database_name": self.database.name,
            "redis_host": self.redis.host,
            "gpu_visible_devices": self.gpu.visible_devices,
        }


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（缓存）"""
    return Settings()
