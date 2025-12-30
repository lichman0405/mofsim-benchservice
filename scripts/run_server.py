#!/usr/bin/env python
"""
启动 API 服务器

使用方式:
    python scripts/run_server.py
    python scripts/run_server.py --host 0.0.0.0 --port 8000 --reload
"""
import argparse
import uvicorn

from core.config import get_settings
from logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="启动 MOFSimBench API 服务器")
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开启热重载")
    parser.add_argument("--workers", type=int, default=1, help="Worker 数量")
    
    args = parser.parse_args()
    settings = get_settings()
    
    # 配置日志
    setup_logging()
    
    # 运行服务器
    uvicorn.run(
        "api.main:app",
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        reload=args.reload or settings.debug,
        workers=args.workers if not args.reload else 1,
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
