#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新数据接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Optional
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..dependencies import get_db
from ..schemas.update import UpdateBrief, UpdateDetail, UpdateQueryParams
from ..schemas.common import ApiResponse, PaginatedResponse
from ..services.update_service import UpdateService

router = APIRouter(prefix="/api/v1", tags=["更新数据"])


@router.get("/updates", response_model=ApiResponse[PaginatedResponse[UpdateBrief]])
async def list_updates(
    vendor: Optional[str] = Query(None, description="厂商过滤（aws/azure/gcp等）"),
    source_channel: Optional[str] = Query(None, description="来源类型（blog/whatsnew）"),
    update_type: Optional[str] = Query(None, description="更新类型"),
    product_name: Optional[str] = Query(None, description="产品名称（模糊匹配）"),
    product_category: Optional[str] = Query(None, description="产品分类"),
    date_from: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    date_to: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    has_analysis: Optional[bool] = Query(None, description="是否已AI分析"),
    keyword: Optional[str] = Query(None, description="关键词搜索（标题+内容）"),
    tags: Optional[str] = Query(None, description="标签过滤（逗号分隔）"),
    sort_by: str = Query("publish_date", description="排序字段"),
    order: str = Query("desc", description="排序方向（asc/desc）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    查询更新列表（分页）
    
    支持多条件过滤和排序：
    - 厂商、来源、更新类型、产品分类
    - 日期范围、是否已分析
    - 关键词搜索、标签过滤
    
    返回分页数据和元信息
    """
    # 构建过滤条件
    filters = {}
    if vendor:
        filters['vendor'] = vendor
    if source_channel:
        filters['source_channel'] = source_channel
    if update_type:
        filters['update_type'] = update_type
    if product_name:
        filters['product_name'] = product_name
    if product_category:
        filters['product_category'] = product_category
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    if has_analysis is not None:
        filters['has_analysis'] = has_analysis
    if keyword:
        filters['keyword'] = keyword
    if tags:
        filters['tags'] = tags
    
    # 调用服务层
    service = UpdateService(db)
    items, pagination = service.get_updates_paginated(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order
    )
    
    # 返回分页响应
    return ApiResponse(
        success=True,
        data=PaginatedResponse(items=items, pagination=pagination)
    )


@router.get("/updates/{update_id}", response_model=ApiResponse[UpdateDetail])
async def get_update_detail(
    update_id: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    获取单条更新详情
    
    返回完整的更新信息，包括：
    - 基础信息（标题、厂商、产品等）
    - 完整内容（Markdown格式）
    - AI分析结果（标题翻译、摘要、分类、标签）
    """
    service = UpdateService(db)
    detail = service.get_update_detail(update_id)
    
    if not detail:
        raise HTTPException(status_code=404, detail=f"更新记录不存在: {update_id}")
    
    return ApiResponse(success=True, data=detail)


@router.get("/updates/{update_id}/raw", response_class=PlainTextResponse)
async def get_update_raw_content(
    update_id: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    获取原始 Markdown 内容
    
    直接返回纯文本格式的Markdown内容，方便：
    - 前端Markdown渲染
    - 内容复制
    - 外部工具处理
    """
    service = UpdateService(db)
    detail = service.get_update_detail(update_id)
    
    if not detail:
        raise HTTPException(status_code=404, detail=f"更新记录不存在: {update_id}")
    
    content = detail.get('content', '')
    if not content:
        raise HTTPException(status_code=404, detail="内容为空")
    
    return PlainTextResponse(content=content, media_type="text/markdown")
