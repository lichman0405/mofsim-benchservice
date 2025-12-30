"""
文件存储管理

参考文档: docs/engineering_requirements.md 第八节
"""
import os
import hashlib
from pathlib import Path
from typing import Optional, BinaryIO
import shutil
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)


class FileStorage:
    """
    文件存储管理器
    
    管理:
    - 结构文件上传
    - 结果文件存储
    - 日志文件
    - 自定义模型
    """
    
    def __init__(self):
        settings = get_settings()
        self.base_path = Path(settings.storage.base_path)
        self.upload_path = Path(settings.storage.upload_path)
        self.result_path = Path(settings.storage.result_path)
        self.model_path = Path(settings.storage.model_path)
        self.log_path = Path(settings.storage.log_path)
        self.max_upload_size = settings.storage.max_upload_size_mb * 1024 * 1024
        
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """确保目录存在"""
        for path in [self.base_path, self.upload_path, self.result_path, self.model_path, self.log_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def save_upload(self, file: BinaryIO, filename: str, subdir: str = "structures") -> tuple[str, str, int]:
        """
        保存上传文件
        
        Args:
            file: 文件对象
            filename: 原始文件名
            subdir: 子目录
        
        Returns:
            (文件路径, 校验和, 文件大小)
        """
        target_dir = self.upload_path / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 计算 SHA256
        sha256 = hashlib.sha256()
        content = file.read()
        sha256.update(content)
        checksum = sha256.hexdigest()
        
        # 使用校验和作为文件名前缀避免冲突
        safe_name = f"{checksum[:8]}_{filename}"
        file_path = target_dir / safe_name
        
        # 写入文件
        with open(file_path, "wb") as f:
            f.write(content)
        
        file_size = len(content)
        
        logger.info(
            "file_uploaded",
            filename=filename,
            path=str(file_path),
            size=file_size,
            checksum=checksum[:16],
        )
        
        return str(file_path), checksum, file_size
    
    def save_result(self, task_id: str, filename: str, content: bytes) -> str:
        """
        保存任务结果文件
        
        Args:
            task_id: 任务 ID
            filename: 文件名
            content: 文件内容
        
        Returns:
            文件路径
        """
        task_dir = self.result_path / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = task_dir / filename
        with open(file_path, "wb") as f:
            f.write(content)
        
        return str(file_path)
    
    def get_result_path(self, task_id: str) -> Path:
        """获取任务结果目录"""
        return self.result_path / task_id
    
    def read_file(self, path: str) -> bytes:
        """读取文件内容"""
        with open(path, "rb") as f:
            return f.read()
    
    def delete_file(self, path: str) -> bool:
        """删除文件"""
        try:
            os.remove(path)
            logger.info("file_deleted", path=path)
            return True
        except OSError as e:
            logger.error("file_delete_failed", path=path, error=str(e))
            return False
    
    def cleanup_task_results(self, task_id: str) -> bool:
        """清理任务结果目录"""
        task_dir = self.result_path / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)
            logger.info("task_results_cleaned", task_id=task_id)
            return True
        return False
