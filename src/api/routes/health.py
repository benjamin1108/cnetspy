#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
健康检查接口
"""

from fastapi import APIRouter, Depends
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..dependencies import get_db
from ..config import settings

router = APIRouter(tags=["健康检查"])


@router.get("/")
async def root():
    """
    API 根路径
    
    返回版本信息和服务状态
    """
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "running",
        "docs": "/docs"
    }


@router.get("/health")
async def health_check(db: UpdateDataLayer = Depends(get_db)):
    """
    健康检查
    
    检查数据库连接状态和基础统计
    """
    try:
        # 测试数据库连接
        stats = db.get_database_stats()
        
        return {
            "status": "healthy",
            "database": {
                "connected": True,
                "path": db.db_path,
                "total_updates": stats.get('total_updates', 0)
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": str(e)
            }
        }
