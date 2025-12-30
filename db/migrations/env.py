"""
Alembic 环境配置

此文件配置 Alembic 迁移运行环境
"""
from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入模型和配置
from db.database import Base
from db.models import Task, Structure, Model, CustomModel, AlertRule, Alert  # noqa
from core.config import get_settings

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 模型元数据 - 用于自动生成迁移
target_metadata = Base.metadata

# 从应用配置获取数据库 URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database.url)


def run_migrations_offline() -> None:
    """
    离线模式运行迁移
    
    只生成 SQL 语句，不实际连接数据库
    使用方式: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移
    
    连接数据库并执行迁移
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 检测列类型变化
            compare_server_default=True,  # 检测默认值变化
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
