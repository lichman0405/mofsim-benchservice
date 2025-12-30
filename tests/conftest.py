"""
pytest 配置
"""
import pytest
import os

# 测试时使用测试数据库
os.environ.setdefault("DB_NAME", "mofsim_bench_test")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture(scope="session")
def test_settings():
    """测试配置"""
    from core.config import Settings
    return Settings()


@pytest.fixture(scope="function")
def db_session():
    """
    数据库会话 fixture
    
    每个测试函数使用独立事务，测试后回滚
    """
    # TODO: Phase 1.5 Alembic 配置后实现
    pass
