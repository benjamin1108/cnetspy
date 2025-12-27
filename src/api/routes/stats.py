#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计分析接口
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..dependencies import get_db
from ..schemas.analysis import StatsOverview, TimelineItem, VendorStatsItem
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


@router.get("/timeline", response_model=ApiResponse[List[TimelineItem]])
async def get_stats_timeline(
    granularity: str = Query("day", description="统计粒度: day/week/month/year"),
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    vendor: Optional[str] = Query(None, description="厂商过滤"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    时间线统计
    
    按时间维度统计更新数量，支持：
    - 粒度选择: day(日)/week(周)/month(月)/year(年)
    - 日期范围过滤
    - 厂商过滤
    
    每个时间点返回总数和各厂商分布
    
    用于前端图表展示（折线图/柱状图）
    """
    # 验证粒度参数
    if granularity not in ['day', 'week', 'month', 'year']:
        granularity = 'day'
    
    timeline = db.get_timeline_statistics(
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        vendor=vendor
    )
    
    return ApiResponse(success=True, data=timeline)


@router.get("/vendors", response_model=ApiResponse[List[VendorStatsItem]])
async def get_stats_vendors(
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    include_trend: bool = Query(False, description="是否包含环比趋势数据"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    按厂商统计
    
    返回各厂商的更新统计：
    - vendor: 厂商标识
    - count: 更新总数
    - analyzed: 已分析数
    - trend: 环比趋势（include_trend=true时返回）
    
    用于前端饼图/对比图
    """
    vendor_stats = db.get_vendor_statistics(
        date_from=date_from,
        date_to=date_to,
        include_trend=include_trend
    )
    
    return ApiResponse(success=True, data=vendor_stats)


@router.get("/update-types", response_model=ApiResponse[dict])
async def get_stats_update_types(
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    vendor: Optional[str] = Query(None, description="厂商过滤"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    更新类型统计
    
    返回各更新类型的数量统计，支持：
    - 日期范围过滤
    - 厂商过滤
    
    用于前端柱状图展示
    """
    update_types = db.get_update_type_statistics(
        date_from=date_from,
        date_to=date_to,
        vendor=vendor
    )
    
    return ApiResponse(success=True, data=update_types)


@router.get("/years", response_model=ApiResponse[List[int]])
async def get_available_years(db: UpdateDataLayer = Depends(get_db)):
    """
    获取有数据的年份列表
    
    返回数据库中有记录的年份，降序排列
    用于前端筛选器的年份选项
    """
    years = db.get_available_years()
    return ApiResponse(success=True, data=years)


@router.get("/product-hotness", response_model=ApiResponse[List[dict]])
async def get_product_hotness(
    vendor: Optional[str] = Query(None, description="厂商过滤"),
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    include_trend: bool = Query(False, description="是否包含环比趋势数据"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    产品热度排行榜
    
    返回更新数量最多的产品子类，支持：
    - 厂商过滤
    - 日期范围过滤
    - 返回数量限制
    - 环比趋势（include_trend=true时返回）
    
    用于产品热度排行图表
    """
    stats = db.get_product_subcategory_statistics(
        vendor=vendor,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        include_trend=include_trend
    )
    return ApiResponse(success=True, data=stats)


@router.get("/vendor-type-matrix", response_model=ApiResponse[List[dict]])
async def get_vendor_type_matrix(
    date_from: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    厂商-更新类型统计矩阵
    
    返回每个厂商的更新类型分布，支持：
    - 日期范围过滤
    
    数据结构: [{vendor, total, update_types: {type: count}}]
    用于厂商策略对比图表
    """
    stats = db.get_vendor_update_type_matrix(
        date_from=date_from,
        date_to=date_to
    )
    return ApiResponse(success=True, data=stats)
