#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用响应模型
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List


T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应格式
    
    示例:
        {
            "success": true,
            "data": {...},
            "message": "",
            "error": null
        }
    """
    success: bool = True
    data: Optional[T] = None
    message: str = ""
    error: Optional[str] = None


class PaginationMeta(BaseModel):
    """
    分页元数据
    
    示例:
        {
            "page": 1,
            "page_size": 20,
            "total": 100,
            "total_pages": 5
        }
    """
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    total: int = Field(..., ge=0, description="总记录数")
    total_pages: int = Field(..., ge=0, description="总页数")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应
    
    示例:
        {
            "items": [...],
            "pagination": {...}
        }
    """
    items: List[T]
    pagination: PaginationMeta
