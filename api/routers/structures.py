"""
结构文件管理 API 路由

参考文档: docs/engineering_requirements.md 3.3 节
"""
from fastapi import APIRouter, Query, Path, UploadFile, File, HTTPException
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import structlog

from api.schemas.structure import (
    StructureInfo,
    StructureListResponse,
    StructureUploadResponse,
)
from api.schemas.response import APIResponse, PaginationInfo
from core.services.structure_service import (
    get_structure_service,
    StructureValidationError,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("", response_model=APIResponse[StructureUploadResponse])
async def upload_structure(
    file: UploadFile = File(..., description="结构文件 (.cif, .xyz)"),
):
    """
    上传结构文件
    
    支持格式:
    - CIF: 晶体学信息文件
    - XYZ: 原子坐标文件
    - POSCAR/VASP: VASP 格式
    - PDB: 蛋白质数据库格式
    
    文件将使用 ASE 解析验证
    """
    try:
        service = get_structure_service()
        
        # 读取文件内容
        content = await file.read()
        
        # 上传并解析
        info = service.upload(
            file_content=content,
            filename=file.filename or "structure.cif",
            source="api_upload",
        )
        
        response = StructureUploadResponse(
            id=UUID(info.id),
            name=info.name,
            format=info.format.value,
            n_atoms=info.n_atoms,
            formula=info.formula,
            checksum=info.file_hash,
        )
        
        return APIResponse(
            success=True,
            code=200,
            message=f"Structure uploaded: {info.name}",
            data=response,
        )
        
    except StructureValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("structure_upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get("", response_model=APIResponse[StructureListResponse])
async def list_structures(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取已上传的结构文件列表"""
    service = get_structure_service()
    all_structures = service.list_all()
    
    # 分页
    total = len(all_structures)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = all_structures[start:end]
    
    # 转换为响应格式
    items = []
    for info in page_items:
        items.append(StructureInfo(
            id=UUID(info.id),
            name=info.name,
            original_name=info.name,
            format=info.format.value,
            file_size=info.file_size,
            n_atoms=info.n_atoms,
            formula=info.formula,
            is_builtin=False,
            created_at=datetime.fromtimestamp(info.uploaded_at),
        ))
    
    pagination = PaginationInfo(
        total_items=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
    )
    
    return APIResponse(
        success=True,
        code=200,
        message="获取结构列表成功",
        data=StructureListResponse(items=items, pagination=pagination),
    )


@router.get("/builtin", response_model=APIResponse[StructureListResponse])
async def list_builtin_structures():
    """获取内置测试结构列表"""
    # TODO: 从 mof_benchmark/analysis/dft_data 加载内置结构
    return APIResponse(
        success=True,
        code=200,
        message="Built-in structures not yet implemented",
        data=StructureListResponse(items=[], pagination=None),
    )


@router.get("/{structure_id}", response_model=APIResponse[StructureInfo])
async def get_structure(structure_id: str = Path(..., description="结构 ID")):
    """获取结构详情"""
    service = get_structure_service()
    info = service.get(structure_id)
    
    if not info:
        raise HTTPException(status_code=404, detail=f"Structure not found: {structure_id}")
    
    structure_info = StructureInfo(
        id=UUID(info.id),
        name=info.name,
        original_name=info.name,
        format=info.format.value,
        file_size=info.file_size,
        n_atoms=info.n_atoms,
        formula=info.formula,
        is_builtin=False,
        created_at=datetime.fromtimestamp(info.uploaded_at),
    )
    
    return APIResponse(success=True, code=200, message="获取结构详情成功", data=structure_info)


@router.get("/{structure_id}/validate")
async def validate_structure(structure_id: str = Path(..., description="结构 ID")):
    """验证结构"""
    service = get_structure_service()
    is_valid, errors = service.validate(structure_id)
    
    return APIResponse(
        success=True,
        code=200,
        message="结构验证完成",
        data={
            "is_valid": is_valid,
            "errors": errors,
        },
    )


@router.get("/{structure_id}/details")
async def get_structure_details(structure_id: str = Path(..., description="结构 ID")):
    """获取结构完整详情（包括晶胞参数）"""
    service = get_structure_service()
    info = service.get(structure_id)
    
    if not info:
        raise HTTPException(status_code=404, detail=f"Structure not found: {structure_id}")
    
    return APIResponse(success=True, code=200, message="获取结构完整详情成功", data=info.to_dict())


@router.delete("/{structure_id}", response_model=APIResponse)
async def delete_structure(structure_id: str = Path(..., description="结构 ID")):
    """删除结构文件"""
    service = get_structure_service()
    success = service.delete(structure_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Structure not found: {structure_id}")
    
    return APIResponse(success=True, code=200, message="Structure deleted")
