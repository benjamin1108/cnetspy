#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI分析接口
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..dependencies import get_db
from ..schemas.analysis import (
    AnalysisTaskCreate, 
    AnalysisTaskDetail, 
    SingleAnalysisRequest, 
    AnalysisResult
)
from ..schemas.common import ApiResponse, PaginatedResponse
from ..services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1/analysis", tags=["AI分析"])


@router.post("/single/{update_id}", response_model=ApiResponse[AnalysisResult])
async def analyze_single_update(
    update_id: str,
    force: bool = False,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    单条更新AI分析
    
    对指定的更新记录执行AI分析，提取：
    - 标题翻译（title_translated）
    - 内容摘要（content_summary）
    - 更新类型（update_type）
    - 产品子类（product_subcategory）
    - 标签（tags）
    
    参数：
    - force: 是否强制重新分析（默认false，已有分析结果会跳过）
    
    返回：分析结果或已有结果
    """
    service = AnalysisService(db)
    result = service.analyze_single(update_id, force=force)
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', '分析失败'))
    
    return ApiResponse(success=True, data=result)


@router.post("/translate/{update_id}", response_model=ApiResponse)
async def translate_update_content(
    update_id: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    翻译单条更新内容
    
    将指定更新的原文内容翻译为中文，并保存到 content_translated 字段。
    如果已有翻译内容，则跳过。
    
    参数：
    - update_id: 更新记录ID
    
    返回：翻译结果
    """
    service = AnalysisService(db)
    result = service.translate_content(update_id)
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', '翻译失败'))
    
    return ApiResponse(success=True, data=result)


@router.post("/batch", response_model=ApiResponse[AnalysisTaskDetail])
async def create_batch_analysis_task(
    request: AnalysisTaskCreate,
    background_tasks: BackgroundTasks,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    创建批量分析任务
    
    根据过滤条件批量分析多条更新记录，支持：
    - 按厂商、来源、日期等条件过滤
    - 后台异步执行
    - 实时进度跟踪
    
    参数：
    - filters: 过滤条件（同查询接口）
    - batch_size: 每批处理数量（默认50）
    
    返回：任务ID和初始状态
    """
    service = AnalysisService(db)
    
    try:
        # 创建任务
        task_id = service.create_batch_task(
            filters=request.filters,
            batch_size=request.batch_size
        )
        
        # 添加后台任务（异步执行）
        background_tasks.add_task(service.execute_batch_task, task_id)
        
        # 返回任务详情
        task = service.get_task_detail(task_id)
        return ApiResponse(success=True, data=task, message="批量分析任务已创建，后台执行中")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}", response_model=ApiResponse[AnalysisTaskDetail])
async def get_task_status(
    task_id: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    查询任务状态
    
    查询批量分析任务的执行进度和结果：
    - status: queued/running/completed/failed
    - progress: 进度百分比（0.0-1.0）
    - processed_count: 已处理数量
    - success_count/fail_count: 成功/失败数量
    
    返回：任务详情
    """
    service = AnalysisService(db)
    task = service.get_task_detail(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    return ApiResponse(success=True, data=task)


@router.get("/tasks", response_model=ApiResponse[PaginatedResponse[AnalysisTaskDetail]])
async def list_analysis_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    查询任务列表（分页）
    
    查询最近的批量分析任务：
    - 支持按状态过滤（queued/running/completed/failed）
    - 按创建时间倒序排列
    - 分页返回
    
    返回：任务列表和分页元数据
    """
    try:
        service = AnalysisService(db)
        items, pagination = service.list_tasks_paginated(page, page_size, status)
        
        return ApiResponse(
            success=True,
            data=PaginatedResponse(items=items, pagination=pagination)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
