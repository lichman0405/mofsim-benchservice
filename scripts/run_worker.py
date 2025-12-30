#!/usr/bin/env python
"""
启动 Celery Worker

使用方式:
    python scripts/run_worker.py
    python scripts/run_worker.py --gpu 0 --concurrency 1
"""
import argparse
import os

from workers.celery_app import celery_app
from logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="启动 Celery Worker")
    parser.add_argument("--gpu", type=int, default=None, help="指定 GPU ID")
    parser.add_argument("--concurrency", type=int, default=1, help="并发数")
    parser.add_argument("--queue", default="default", help="监听的队列")
    parser.add_argument("--loglevel", default="INFO", help="日志级别")
    
    args = parser.parse_args()
    
    # 设置 GPU
    if args.gpu is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    
    # 配置日志
    setup_logging(level=args.loglevel)
    
    # 启动 Worker
    celery_app.worker_main([
        "worker",
        f"--concurrency={args.concurrency}",
        f"--queues={args.queue}",
        f"--loglevel={args.loglevel}",
        "--pool=solo",  # GPU 任务使用单进程
    ])


if __name__ == "__main__":
    main()
