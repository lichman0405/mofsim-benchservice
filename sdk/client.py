"""
MOFSimBench Python SDK 客户端

参考文档: docs/user/user_guide.md 2.3 节

使用示例:
    from sdk import MOFSimBenchClient
    
    client = MOFSimBenchClient("http://localhost:8000")
    
    # 提交优化任务
    task = client.submit_optimization(
        model="mace_prod",
        structure_file="path/to/structure.cif",
        fmax=0.05
    )
    
    # 等待完成
    result = client.wait_for_result(task.task_id)
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path
import time
import httpx


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str
    status: str
    model: str
    created_at: str
    

class MOFSimBenchClient:
    """
    MOFSimBench API 客户端
    
    Args:
        base_url: API 服务器地址
        timeout: 请求超时时间（秒）
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/api/v1"
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
    
    def _url(self, path: str) -> str:
        """构建完整 URL"""
        return f"{self.base_url}{self.api_prefix}{path}"
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """发送请求"""
        response = self._client.request(method, self._url(path), **kwargs)
        response.raise_for_status()
        return response.json()
    
    # ===== 健康检查 =====
    
    def health_check(self) -> Dict[str, Any]:
        """检查服务健康状态"""
        return self._request("GET", "/health")
    
    # ===== 任务提交 =====
    
    def submit_optimization(
        self,
        model: str,
        structure_file: str,
        fmax: float = 0.05,
        max_steps: int = 500,
        optimizer: str = "BFGS",
        **kwargs
    ) -> TaskInfo:
        """
        提交结构优化任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            fmax: 收敛力阈值 (eV/Å)
            max_steps: 最大优化步数
            optimizer: 优化器类型
        """
        # 上传结构
        file_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": file_info["id"],
            },
            "parameters": {
                "fmax": fmax,
                "max_steps": max_steps,
                "optimizer": optimizer,
            },
            "options": kwargs,
        }
        
        result = self._request("POST", "/tasks/optimization", json=data)
        return TaskInfo(**result["data"])
    
    def submit_stability(
        self,
        model: str,
        structure_file: str,
        temperature: float = 300.0,
        pressure: float = 1.0,
        steps: int = 10000,
        **kwargs
    ) -> TaskInfo:
        """提交 NPT MD 稳定性任务"""
        file_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": file_info["id"],
            },
            "parameters": {
                "temperature": temperature,
                "pressure": pressure,
                "steps": steps,
            },
            "options": kwargs,
        }
        
        result = self._request("POST", "/tasks/stability", json=data)
        return TaskInfo(**result["data"])
    
    def submit_bulk_modulus(
        self,
        model: str,
        structure_file: str,
        strain_range: float = 0.05,
        n_points: int = 7,
        **kwargs
    ) -> TaskInfo:
        """提交体积模量计算任务"""
        file_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": file_info["id"],
            },
            "parameters": {
                "strain_range": strain_range,
                "n_points": n_points,
            },
            "options": kwargs,
        }
        
        result = self._request("POST", "/tasks/bulk-modulus", json=data)
        return TaskInfo(**result["data"])
    
    # ===== 结构管理 =====
    
    def _upload_structure(self, file_path: str) -> Dict[str, Any]:
        """上传结构文件"""
        path = Path(file_path)
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            result = self._request("POST", "/structures/upload", files=files)
        return result["data"]
    
    def list_structures(self) -> List[Dict[str, Any]]:
        """列出上传的结构"""
        result = self._request("GET", "/structures")
        return result["data"]["items"]
    
    def list_builtin_structures(self) -> List[Dict[str, Any]]:
        """列出内置结构"""
        result = self._request("GET", "/structures/builtin")
        return result["data"]["items"]
    
    # ===== 任务管理 =====
    
    def get_task(self, task_id: str) -> TaskInfo:
        """获取任务状态"""
        result = self._request("GET", f"/tasks/{task_id}")
        return TaskInfo(**result["data"])
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """获取任务结果"""
        result = self._request("GET", f"/tasks/{task_id}/result")
        return result["data"]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        result = self._request("POST", f"/tasks/{task_id}/cancel")
        return result["success"]
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出任务"""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        result = self._request("GET", "/tasks", params=params)
        return result["data"]
    
    def wait_for_result(
        self,
        task_id: str,
        timeout: float = 3600.0,
        poll_interval: float = 5.0,
    ) -> Dict[str, Any]:
        """
        等待任务完成并返回结果
        
        Args:
            task_id: 任务 ID
            timeout: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = self.get_task(task_id)
            
            if task.status == "COMPLETED":
                return self.get_task_result(task_id)
            elif task.status in ("FAILED", "CANCELLED", "TIMEOUT"):
                raise RuntimeError(f"任务 {task.status}: {task_id}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"等待任务 {task_id} 超时")
    
    # ===== 模型管理 =====
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        result = self._request("GET", "/models")
        return result["data"]["models"]
    
    def get_model(self, name: str) -> Dict[str, Any]:
        """获取模型信息"""
        result = self._request("GET", f"/models/{name}")
        return result["data"]
    
    # ===== 系统状态 =====
    
    def get_gpu_status(self) -> Dict[str, Any]:
        """获取 GPU 状态"""
        result = self._request("GET", "/system/gpus")
        return result["data"]
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        result = self._request("GET", "/system/queue")
        return result["data"]
    
    def close(self) -> None:
        """关闭客户端"""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
