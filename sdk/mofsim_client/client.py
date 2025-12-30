"""
MOFSimBench 同步客户端

提供所有 API 的同步调用接口。
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Iterator, BinaryIO

import httpx

from .models import (
    TaskInfo,
    TaskResult,
    StructureInfo,
    ModelInfo,
    GPUInfo,
    QueueInfo,
    PaginatedResult,
)
from .task import Task
from .exceptions import (
    MOFSimError,
    APIError,
    AuthenticationError,
    TaskNotFoundError,
    ModelNotFoundError,
    StructureNotFoundError,
    ValidationError,
    ConnectionError as SDKConnectionError,
    RateLimitError,
    ServerError,
)


class MOFSimClient:
    """
    MOFSimBench 同步客户端
    
    提供与 MOFSimBench 服务交互的同步 API。
    
    Example:
        ```python
        # 使用上下文管理器
        with MOFSimClient("http://localhost:8000") as client:
            task = client.submit_optimization(
                model="mace_mof_large",
                structure_file="structure.cif"
            )
            result = task.wait()
            print(result.final_energy)
        
        # 或者手动管理
        client = MOFSimClient("http://localhost:8000")
        try:
            models = client.list_models()
        finally:
            client.close()
        ```
    
    Args:
        base_url: API 服务器地址
        api_key: API 密钥（可选）
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/api/v1"
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 构建 headers
        headers = {
            "User-Agent": "MOFSimClient/1.0.0",
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # 创建 HTTP 客户端
        transport = httpx.HTTPTransport(retries=max_retries)
        self._client = httpx.Client(
            timeout=timeout,
            headers=headers,
            transport=transport,
        )
    
    def _url(self, path: str) -> str:
        """构建完整 URL"""
        if path.startswith("/api/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}{self.api_prefix}{path}"
    
    def _handle_error(self, response: httpx.Response) -> None:
        """处理错误响应"""
        try:
            data = response.json()
            message = data.get("message", data.get("detail", str(response.text)))
            code = data.get("code")
            request_id = data.get("request_id")
        except Exception:
            message = response.text or f"HTTP {response.status_code}"
            code = None
            request_id = None
        
        status = response.status_code
        
        if status == 401:
            raise AuthenticationError(message, status_code=status, code=code, request_id=request_id)
        elif status == 404:
            if "task" in message.lower():
                raise TaskNotFoundError("unknown", message=message, request_id=request_id)
            elif "model" in message.lower():
                raise ModelNotFoundError("unknown", message=message, request_id=request_id)
            elif "structure" in message.lower():
                raise StructureNotFoundError("unknown", message=message, request_id=request_id)
            raise APIError(message, status_code=status, code=code, request_id=request_id)
        elif status == 422:
            raise ValidationError(message, request_id=request_id)
        elif status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(message, retry_after=float(retry_after) if retry_after else None, request_id=request_id)
        elif status >= 500:
            raise ServerError(message, request_id=request_id)
        else:
            raise APIError(message, status_code=status, code=code, request_id=request_id)
    
    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送请求并返回 JSON"""
        try:
            response = self._client.request(method, self._url(path), **kwargs)
        except httpx.ConnectError as e:
            raise SDKConnectionError(f"Failed to connect to {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            raise SDKConnectionError(f"Request timed out: {e}")
        
        if not response.is_success:
            self._handle_error(response)
        
        return response.json()
    
    def _request_raw(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """发送请求并返回原始响应"""
        try:
            response = self._client.request(method, self._url(path), **kwargs)
        except httpx.ConnectError as e:
            raise SDKConnectionError(f"Failed to connect to {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            raise SDKConnectionError(f"Request timed out: {e}")
        
        if not response.is_success:
            self._handle_error(response)
        
        return response
    
    # ===== 健康检查 =====
    
    def health_check(self) -> Dict[str, Any]:
        """
        检查服务健康状态
        
        Returns:
            健康状态信息
        """
        return self._request("GET", "/health")
    
    def is_healthy(self) -> bool:
        """
        检查服务是否健康
        
        Returns:
            是否健康
        """
        try:
            result = self.health_check()
            return result.get("status") == "healthy"
        except Exception:
            return False
    
    # ===== 任务提交 =====
    
    def _upload_structure(
        self,
        file_path: Union[str, Path, BinaryIO],
        filename: Optional[str] = None,
    ) -> StructureInfo:
        """上传结构文件"""
        if isinstance(file_path, (str, Path)):
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Structure file not found: {path}")
            with open(path, "rb") as f:
                files = {"file": (path.name, f)}
                result = self._request("POST", "/structures/upload", files=files)
        else:
            # 文件对象
            fname = filename or "structure.cif"
            files = {"file": (fname, file_path)}
            result = self._request("POST", "/structures/upload", files=files)
        
        return StructureInfo.from_dict(result.get("data", result))
    
    def submit_optimization(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        fmax: float = 0.05,
        max_steps: int = 500,
        optimizer: str = "BFGS",
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交结构优化任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            fmax: 收敛力阈值 (eV/Å)
            max_steps: 最大优化步数
            optimizer: 优化器类型 (BFGS, LBFGS, FIRE)
            priority: 任务优先级 (CRITICAL, HIGH, NORMAL, LOW)
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "fmax": fmax,
                "max_steps": max_steps,
                "optimizer": optimizer,
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/optimization", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_stability(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        temperature: float = 300.0,
        pressure: float = 1.0,
        steps: int = 10000,
        timestep: float = 1.0,
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交 NPT MD 稳定性任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            temperature: 温度 (K)
            pressure: 压力 (GPa)
            steps: MD 步数
            timestep: 时间步长 (fs)
            priority: 任务优先级
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "temperature": temperature,
                "pressure": pressure,
                "steps": steps,
                "timestep": timestep,
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/stability", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_bulk_modulus(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        strain_range: float = 0.05,
        n_points: int = 7,
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交体积模量计算任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            strain_range: 应变范围
            n_points: 计算点数
            priority: 任务优先级
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "strain_range": strain_range,
                "n_points": n_points,
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/bulk-modulus", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_heat_capacity(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        temperature: float = 300.0,
        supercell: tuple = (2, 2, 2),
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交热容计算任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            temperature: 温度 (K)
            supercell: 超胞大小
            priority: 任务优先级
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "temperature": temperature,
                "supercell": list(supercell),
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/heat-capacity", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_interaction_energy(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        gas_molecule: str = "CO2",
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交相互作用能计算任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            gas_molecule: 气体分子类型
            priority: 任务优先级
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "gas_molecule": gas_molecule,
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/interaction-energy", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_single_point(
        self,
        model: str,
        structure_file: Union[str, Path],
        *,
        calculate_forces: bool = True,
        calculate_stress: bool = False,
        priority: str = "NORMAL",
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> Task:
        """
        提交单点能计算任务
        
        Args:
            model: 模型名称
            structure_file: 结构文件路径
            calculate_forces: 是否计算力
            calculate_stress: 是否计算应力
            priority: 任务优先级
            callback_url: 回调 URL
        
        Returns:
            Task 任务对象
        """
        structure_info = self._upload_structure(structure_file)
        
        data = {
            "model": model,
            "structure": {
                "source": "upload",
                "file_id": structure_info.structure_id,
            },
            "parameters": {
                "calculate_forces": calculate_forces,
                "calculate_stress": calculate_stress,
                **kwargs,
            },
            "options": {
                "priority": priority,
            },
        }
        if callback_url:
            data["options"]["callback_url"] = callback_url
        
        result = self._request("POST", "/tasks/single-point", json=data)
        task_info = TaskInfo.from_dict(result.get("data", result))
        return Task(task_info, self)
    
    def submit_batch(
        self,
        tasks: List[Dict[str, Any]],
    ) -> List[Task]:
        """
        批量提交任务
        
        Args:
            tasks: 任务列表，每个任务包含 type, model, structure, parameters
        
        Returns:
            Task 列表
        """
        result = self._request("POST", "/tasks/batch", json={"tasks": tasks})
        data = result.get("data", {})
        task_list = data.get("tasks", [])
        return [Task(TaskInfo.from_dict(t), self) for t in task_list]
    
    # ===== 任务管理 =====
    
    def get_task(self, task_id: str) -> Task:
        """
        获取任务对象
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Task 任务对象
        """
        task_info = self.get_task_info(task_id)
        return Task(task_info, self)
    
    def get_task_info(self, task_id: str) -> TaskInfo:
        """
        获取任务信息
        
        Args:
            task_id: 任务 ID
        
        Returns:
            TaskInfo 任务信息
        """
        result = self._request("GET", f"/tasks/{task_id}")
        return TaskInfo.from_dict(result.get("data", result))
    
    def get_task_result(self, task_id: str) -> TaskResult:
        """
        获取任务结果
        
        Args:
            task_id: 任务 ID
        
        Returns:
            TaskResult 任务结果
        """
        result = self._request("GET", f"/tasks/{task_id}/result")
        return TaskResult.from_dict(result.get("data", result))
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            是否成功
        """
        result = self._request("POST", f"/tasks/{task_id}/cancel")
        return result.get("success", True)
    
    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """
        列出任务
        
        Args:
            status: 状态过滤
            task_type: 类型过滤
            page: 页码
            page_size: 每页大小
        
        Returns:
            PaginatedResult 分页结果
        """
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if task_type:
            params["task_type"] = task_type
        
        result = self._request("GET", "/tasks", params=params)
        return PaginatedResult.from_dict(result.get("data", result), TaskInfo)
    
    def get_task_logs(
        self,
        task_id: str,
        *,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取任务日志
        
        Args:
            task_id: 任务 ID
            level: 日志级别过滤
            limit: 最大返回条数
        
        Returns:
            日志列表
        """
        params = {"limit": limit}
        if level:
            params["level"] = level
        
        result = self._request("GET", f"/tasks/{task_id}/logs", params=params)
        return result.get("data", {}).get("logs", [])
    
    def stream_task_logs(
        self,
        task_id: str,
        timeout: float = 3600.0,
    ) -> Iterator[Dict[str, Any]]:
        """
        流式获取任务日志 (SSE)
        
        Args:
            task_id: 任务 ID
            timeout: 超时时间
        
        Yields:
            日志条目
        """
        url = self._url(f"/tasks/{task_id}/logs/stream")
        with self._client.stream("GET", url, timeout=timeout) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError:
                        continue
    
    # ===== 结构管理 =====
    
    def upload_structure(
        self,
        file_path: Union[str, Path],
    ) -> StructureInfo:
        """
        上传结构文件
        
        Args:
            file_path: 结构文件路径
        
        Returns:
            StructureInfo 结构信息
        """
        return self._upload_structure(file_path)
    
    def list_structures(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """
        列出上传的结构
        
        Args:
            page: 页码
            page_size: 每页大小
        
        Returns:
            PaginatedResult 分页结果
        """
        params = {"page": page, "page_size": page_size}
        result = self._request("GET", "/structures", params=params)
        return PaginatedResult.from_dict(result.get("data", result), StructureInfo)
    
    def get_structure(self, structure_id: str) -> StructureInfo:
        """
        获取结构信息
        
        Args:
            structure_id: 结构 ID
        
        Returns:
            StructureInfo 结构信息
        """
        result = self._request("GET", f"/structures/{structure_id}")
        return StructureInfo.from_dict(result.get("data", result))
    
    def delete_structure(self, structure_id: str) -> bool:
        """
        删除结构
        
        Args:
            structure_id: 结构 ID
        
        Returns:
            是否成功
        """
        result = self._request("DELETE", f"/structures/{structure_id}")
        return result.get("success", True)
    
    def list_builtin_structures(self) -> List[Dict[str, Any]]:
        """
        列出内置结构
        
        Returns:
            内置结构列表
        """
        result = self._request("GET", "/structures/builtin")
        return result.get("data", {}).get("items", [])
    
    # ===== 模型管理 =====
    
    def list_models(
        self,
        *,
        family: Optional[str] = None,
    ) -> List[ModelInfo]:
        """
        列出可用模型
        
        Args:
            family: 模型系列过滤 (mace, orb, fairchem, etc.)
        
        Returns:
            ModelInfo 列表
        """
        params = {}
        if family:
            params["family"] = family
        
        result = self._request("GET", "/models", params=params)
        models_data = result.get("data", {}).get("models", [])
        return [ModelInfo.from_dict(m) for m in models_data]
    
    def get_model(self, name: str) -> ModelInfo:
        """
        获取模型信息
        
        Args:
            name: 模型名称
        
        Returns:
            ModelInfo 模型信息
        """
        result = self._request("GET", f"/models/{name}")
        return ModelInfo.from_dict(result.get("data", result))
    
    def load_model(
        self,
        name: str,
        gpu_id: Optional[int] = None,
    ) -> ModelInfo:
        """
        预加载模型到 GPU
        
        Args:
            name: 模型名称
            gpu_id: 目标 GPU ID
        
        Returns:
            ModelInfo 模型信息
        """
        data = {}
        if gpu_id is not None:
            data["gpu_id"] = gpu_id
        
        result = self._request("POST", f"/models/{name}/load", json=data)
        return ModelInfo.from_dict(result.get("data", result))
    
    def unload_model(self, name: str) -> bool:
        """
        卸载模型
        
        Args:
            name: 模型名称
        
        Returns:
            是否成功
        """
        result = self._request("POST", f"/models/{name}/unload")
        return result.get("success", True)
    
    # ===== 系统状态 =====
    
    def get_gpu_status(self) -> List[GPUInfo]:
        """
        获取 GPU 状态
        
        Returns:
            GPUInfo 列表
        """
        result = self._request("GET", "/system/gpus")
        gpus_data = result.get("data", {}).get("gpus", [])
        return [GPUInfo.from_dict(g) for g in gpus_data]
    
    def get_queue_status(self) -> QueueInfo:
        """
        获取队列状态
        
        Returns:
            QueueInfo 队列信息
        """
        result = self._request("GET", "/system/queue")
        return QueueInfo.from_dict(result.get("data", result))
    
    def get_system_config(self) -> Dict[str, Any]:
        """
        获取系统配置
        
        Returns:
            系统配置信息
        """
        result = self._request("GET", "/system/config")
        return result.get("data", result)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取系统统计
        
        Returns:
            系统统计信息
        """
        result = self._request("GET", "/system/stats")
        return result.get("data", result)
    
    # ===== 告警 =====
    
    def list_alert_rules(self) -> List[Dict[str, Any]]:
        """
        列出告警规则
        
        Returns:
            告警规则列表
        """
        result = self._request("GET", "/alerts/rules")
        return result.get("data", {}).get("rules", [])
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        获取活跃告警
        
        Returns:
            活跃告警列表
        """
        result = self._request("GET", "/alerts/active")
        return result.get("data", {}).get("alerts", [])
    
    def get_alert_history(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """
        获取告警历史
        
        Args:
            page: 页码
            page_size: 每页大小
        
        Returns:
            PaginatedResult 分页结果
        """
        params = {"page": page, "page_size": page_size}
        result = self._request("GET", "/alerts/history", params=params)
        return PaginatedResult.from_dict(result.get("data", result))
    
    # ===== 生命周期 =====
    
    def close(self) -> None:
        """关闭客户端"""
        self._client.close()
    
    def __enter__(self) -> "MOFSimClient":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()
