"""
日志归档管理

参考文档: docs/engineering_requirements.md 6.5-6.6 节
实现日志文件的归档和清理策略
"""
import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class LogArchiveManager:
    """
    日志归档管理器
    
    归档策略:
    - 最近 7 天: 原始日志文件
    - 7-30 天: gzip 压缩
    - 30 天以上: 按月打包
    """
    
    def __init__(
        self,
        log_dir: str = "logs",
        archive_dir: str = "logs/archive",
        compress_after_days: int = 7,
        monthly_archive_after_days: int = 30,
        max_retention_days: int = 365,
    ):
        self.log_dir = Path(log_dir)
        self.archive_dir = Path(archive_dir)
        self.compress_after_days = compress_after_days
        self.monthly_archive_after_days = monthly_archive_after_days
        self.max_retention_days = max_retention_days
        
        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def archive(self) -> Dict[str, Any]:
        """
        执行归档操作
        
        Returns:
            归档统计信息
        """
        stats = {
            "compressed": 0,
            "monthly_archived": 0,
            "deleted": 0,
            "errors": [],
        }
        
        now = datetime.now()
        
        # 遍历日志目录
        for log_file in self.log_dir.glob("*.log"):
            try:
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                age_days = (now - mtime).days
                
                if age_days > self.max_retention_days:
                    # 超过保留期限，删除
                    log_file.unlink()
                    stats["deleted"] += 1
                    logger.info("log_file_deleted", file=str(log_file), age_days=age_days)
                    
                elif age_days > self.monthly_archive_after_days:
                    # 按月归档
                    self._archive_monthly(log_file, mtime)
                    stats["monthly_archived"] += 1
                    
                elif age_days > self.compress_after_days:
                    # 压缩
                    self._compress_file(log_file)
                    stats["compressed"] += 1
                    
            except Exception as e:
                stats["errors"].append({"file": str(log_file), "error": str(e)})
                logger.error("log_archive_failed", file=str(log_file), error=str(e))
        
        # 处理已压缩的文件
        for gz_file in self.log_dir.glob("*.log.gz"):
            try:
                mtime = datetime.fromtimestamp(gz_file.stat().st_mtime)
                age_days = (now - mtime).days
                
                if age_days > self.max_retention_days:
                    gz_file.unlink()
                    stats["deleted"] += 1
                elif age_days > self.monthly_archive_after_days:
                    self._archive_monthly(gz_file, mtime)
                    stats["monthly_archived"] += 1
                    
            except Exception as e:
                stats["errors"].append({"file": str(gz_file), "error": str(e)})
        
        return stats
    
    def _compress_file(self, log_file: Path) -> Path:
        """压缩单个日志文件"""
        gz_path = log_file.with_suffix(log_file.suffix + ".gz")
        
        with open(log_file, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 删除原文件
        log_file.unlink()
        logger.info("log_file_compressed", original=str(log_file), compressed=str(gz_path))
        
        return gz_path
    
    def _archive_monthly(self, log_file: Path, mtime: datetime) -> None:
        """按月归档日志文件"""
        # 创建月度目录
        month_dir = self.archive_dir / mtime.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        
        # 移动文件
        dest = month_dir / log_file.name
        shutil.move(str(log_file), str(dest))
        
        logger.info("log_file_archived", file=str(log_file), archive=str(dest))
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """列出所有归档"""
        archives = []
        
        for month_dir in sorted(self.archive_dir.iterdir()):
            if month_dir.is_dir():
                files = list(month_dir.glob("*"))
                total_size = sum(f.stat().st_size for f in files)
                
                archives.append({
                    "month": month_dir.name,
                    "files": len(files),
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                })
        
        return archives
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """获取归档统计信息"""
        # 当前日志
        current_files = list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.log.gz"))
        current_size = sum(f.stat().st_size for f in current_files)
        
        # 归档
        archive_size = 0
        archive_files = 0
        for month_dir in self.archive_dir.iterdir():
            if month_dir.is_dir():
                for f in month_dir.iterdir():
                    archive_size += f.stat().st_size
                    archive_files += 1
        
        return {
            "current_logs": {
                "files": len(current_files),
                "size_mb": round(current_size / 1024 / 1024, 2),
            },
            "archived": {
                "files": archive_files,
                "size_mb": round(archive_size / 1024 / 1024, 2),
            },
            "config": {
                "compress_after_days": self.compress_after_days,
                "monthly_archive_after_days": self.monthly_archive_after_days,
                "max_retention_days": self.max_retention_days,
            },
        }
    
    def cleanup_old_archives(self, months_to_keep: int = 12) -> int:
        """
        清理旧的月度归档
        
        Args:
            months_to_keep: 保留的月数
        
        Returns:
            删除的归档数
        """
        deleted = 0
        cutoff = datetime.now() - timedelta(days=months_to_keep * 30)
        cutoff_month = cutoff.strftime("%Y-%m")
        
        for month_dir in self.archive_dir.iterdir():
            if month_dir.is_dir() and month_dir.name < cutoff_month:
                shutil.rmtree(month_dir)
                deleted += 1
                logger.info("archive_deleted", month=month_dir.name)
        
        return deleted


# 全局单例
_archive_manager: Optional[LogArchiveManager] = None


def get_archive_manager() -> LogArchiveManager:
    """获取归档管理器单例"""
    global _archive_manager
    if _archive_manager is None:
        _archive_manager = LogArchiveManager()
    return _archive_manager
