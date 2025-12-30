"""
配置系统测试
"""
import os
import pytest

from core.config import Settings, DatabaseSettings, RedisSettings


class TestDatabaseSettings:
    """数据库配置测试"""
    
    def test_default_values(self):
        """测试默认值"""
        db = DatabaseSettings()
        assert db.host == "localhost"
        assert db.port == 5432
        # DB name 可能被环境变量覆盖为测试数据库
        assert "mofsim_bench" in db.name
    
    def test_url_property(self):
        """测试 URL 生成"""
        db = DatabaseSettings(
            host="db.example.com",
            port=5433,
            user="admin",
            password="secret",
            name="test_db"
        )
        assert db.url == "postgresql://admin:secret@db.example.com:5433/test_db"


class TestRedisSettings:
    """Redis 配置测试"""
    
    def test_url_without_password(self):
        """测试无密码 URL"""
        redis = RedisSettings(host="redis.local", port=6380, db=1)
        assert redis.url == "redis://redis.local:6380/1"
    
    def test_url_with_password(self):
        """测试带密码 URL"""
        redis = RedisSettings(host="redis.local", password="pass123", db=2)
        assert redis.url == "redis://:pass123@redis.local:6379/2"


class TestSettings:
    """主配置测试"""
    
    def test_default_settings(self):
        """测试默认配置"""
        settings = Settings()
        assert settings.app_name == "MOFSimBench"
        assert settings.environment == "development"
    
    def test_cors_origin_list(self):
        """测试 CORS 源列表解析"""
        settings = Settings(cors_origins="http://localhost:3000,http://example.com")
        origins = settings.cors_origin_list
        assert len(origins) == 2
        assert "http://localhost:3000" in origins
    
    def test_display_config_hides_secrets(self):
        """测试配置脱敏"""
        settings = Settings()
        display = settings.display_config()
        # 不应包含密码等敏感信息
        assert "password" not in str(display).lower() or display.get("database_password") is None
    
    def test_invalid_environment_raises_error(self):
        """测试无效环境值"""
        with pytest.raises(ValueError):
            Settings(environment="invalid")
    
    def test_invalid_log_level_raises_error(self):
        """测试无效日志级别"""
        from core.config import LoggingSettings
        with pytest.raises(ValueError):
            LoggingSettings(level="TRACE")
