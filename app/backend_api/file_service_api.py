from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import uuid
import json
from datetime import datetime, timedelta
import threading
import time
from pathlib import Path

router = APIRouter(prefix="/api/files", tags=["文件服务"])

class FileService:
    """文件服务类，用于管理生成的报告文件"""
    
    def __init__(self, storage_dir="./reports", cleanup_hours=24):
        """
        初始化文件服务
        
        Args:
            storage_dir (str): 文件存储目录
            cleanup_hours (int): 文件保留时间（小时）
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_hours = cleanup_hours
        self.file_registry = {}  # {file_id: {"path": path, "created_at": timestamp, "original_name": name}}
        
        # 启动清理线程
        self._start_cleanup_thread()
    
    def register_file(self, file_path: str, original_name: str = None) -> str:
        """
        注册一个文件，生成唯一ID
        
        Args:
            file_path (str): 文件路径
            original_name (str): 原始文件名
            
        Returns:
            str: 文件唯一ID
        """
        file_id = str(uuid.uuid4())
        self.file_registry[file_id] = {
            "path": str(file_path),
            "created_at": datetime.now(),
            "original_name": original_name or os.path.basename(file_path)
        }
        return file_id
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            dict: 文件信息
        """
        return self.file_registry.get(file_id)
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """
        获取文件路径
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            str: 文件路径，如果不存在返回None
        """
        file_info = self.file_registry.get(file_id)
        if file_info and os.path.exists(file_info["path"]):
            return file_info["path"]
        return None
    
    def cleanup_expired_files(self):
        """清理过期文件"""
        current_time = datetime.now()
        expired_ids = []
        
        for file_id, file_info in self.file_registry.items():
            if current_time - file_info["created_at"] > timedelta(hours=self.cleanup_hours):
                expired_ids.append(file_id)
                # 删除物理文件
                try:
                    if os.path.exists(file_info["path"]):
                        os.remove(file_info["path"])
                        print(f"已删除过期文件: {file_info['path']}")
                except Exception as e:
                    print(f"删除文件失败: {e}")
        
        # 从注册表中移除
        for file_id in expired_ids:
            del self.file_registry[file_id]
    
    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_worker():
            while True:
                time.sleep(3600)  # 每小时检查一次
                self.cleanup_expired_files()
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

# 全局文件服务实例
file_service = FileService()

# API模型
class RegisterFileRequest(BaseModel):
    file_path: str
    original_name: Optional[str] = None

class FileInfoResponse(BaseModel):
    file_id: str
    original_name: str
    created_at: str
    exists: bool

# API接口
@router.post("/register", response_model=Dict[str, Any])
async def register_file(request: RegisterFileRequest):
    """注册文件并返回下载链接"""
    try:
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=400, detail="文件不存在")
        
        # 注册文件
        file_id = file_service.register_file(request.file_path, request.original_name)
        
        return {
            "success": True,
            "file_id": file_id,
            "download_url": f"/api/files/download/{file_id}",
            "message": "文件注册成功"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """下载文件"""
    try:
        file_info = file_service.get_file_info(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在或已过期")
        
        file_path = file_info["path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 返回文件
        return FileResponse(
            path=file_path,
            filename=file_info["original_name"],
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info/{file_id}", response_model=FileInfoResponse)
async def get_file_info(file_id: str):
    """获取文件信息"""
    try:
        file_info = file_service.get_file_info(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在或已过期")
        
        return FileInfoResponse(
            file_id=file_id,
            original_name=file_info["original_name"],
            created_at=file_info["created_at"].isoformat(),
            exists=os.path.exists(file_info["path"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cleanup")
async def cleanup_files():
    """手动清理过期文件"""
    try:
        file_service.cleanup_expired_files()
        return {"message": "清理完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))