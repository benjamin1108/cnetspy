#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计分析接口
"""

from fastapi import APIRouter, Depends
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..dependencies import get_db
from ..schemas.analysis import StatsOverview
from ..schemas.common import ApiResponse
from ..services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1/stats", tags=["统计分析"])


@router.get("/overview", response_model=ApiResponse[StatsOverview])
async def get_stats_overview(db: UpdateDataLayer = Depends(get_db)):
    """
    全局统计概览
    
    返回系统整体统计数据：
    - total_updates: 更新总数
    - vendors: 各厂商统计（总数、已分析数）
    - update_types: 更新类型分布
    - last_crawl_time: 最后爬取时间
    - analysis_coverage: 分析覆盖率（0.0-1.0）
    
    用于仪表盘首页展示
    """
    service = AnalysisService(db)
    stats = service.get_stats_overview()
    
    return ApiResponse(success=True, data=stats)
