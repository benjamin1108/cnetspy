#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
竞争分析报告接口
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import datetime, timedelta

from src.storage.database.sqlite_layer import UpdateDataLayer
from src.storage.database.reports_repository import ReportRepository
from ..dependencies import get_db
from ..schemas.common import ApiResponse
from ..schemas.report import ReportData, VendorSummary

router = APIRouter(prefix="/api/v1/reports", tags=["竞争分析报告"])


@router.get("/{report_type}", response_model=ApiResponse[ReportData])
async def get_report(
    report_type: str,
    year: Optional[int] = Query(None, description="指定年份"),
    month: Optional[int] = Query(None, ge=1, le=12, description="指定月份（仅月报）"),
    week: Optional[int] = Query(None, ge=1, le=53, description="指定周数（仅周报）"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    获取竞争分析报告

    从数据库读取已生成的报告
    """
    if report_type not in ['weekly', 'monthly']:
        return ApiResponse(success=False, error="Invalid report type. Use 'weekly' or 'monthly'")

    # 默认上一个周期
    if not year or (report_type == 'monthly' and not month) or (report_type == 'weekly' and not week):
        today = datetime.now()
        if report_type == 'monthly':
            first_of_this_month = today.replace(day=1)
            last_month = first_of_this_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
        else:
            # 默认上一周
            last_week = today - timedelta(weeks=1)
            year, week, _ = last_week.isocalendar()

    # 从数据库读取报告
    report_repo = ReportRepository()
    report_data = report_repo.get_report(report_type, year, month=month, week=week)

    if not report_data:
        target_str = f"{year}年{month}月" if report_type == 'monthly' else f"{year}年第{week}周"
        return ApiResponse(
            success=False,
            error=f"{target_str}的报告未生成，请先执行: ./run.sh report --{report_type}"
        )
    
    # 构建厂商统计
    vendor_stats = report_data.get('vendor_stats', {})
    vendor_summaries = [
        VendorSummary(
            vendor=vendor,
            count=stats.get('count', 0),
            analyzed=stats.get('count', 0),
            update_types={}
        )
        for vendor, stats in sorted(vendor_stats.items(), key=lambda x: x[1].get('count', 0), reverse=True)
    ]
    
    # 构建按厂商分组的更新列表，关联查询完整信息
    updates_by_vendor = {}
    all_update_ids = []
    
    for vendor, stats in vendor_stats.items():
        for u in stats.get('updates', []):
            all_update_ids.append(u.get('update_id'))
    
    # 批量查询更新详情
    update_details = {}
    if all_update_ids:
        for uid in all_update_ids:
            detail = db.get_update_by_id(uid)
            if detail:
                update_details[uid] = detail
    
    # 组装完整更新信息
    for vendor, stats in vendor_stats.items():
        enriched_updates = []
        for u in stats.get('updates', []):
            uid = u.get('update_id')
            detail = update_details.get(uid, {})
            enriched_updates.append({
                'update_id': uid,
                'title': u.get('title') or detail.get('title', ''),
                'publish_date': u.get('publish_date') or detail.get('publish_date', ''),
                'update_type': u.get('update_type') or detail.get('update_type', ''),
                'content_summary': detail.get('content_summary', ''),
                'product_subcategory': detail.get('product_subcategory', ''),
                'source_channel': detail.get('source_channel', ''),
            })
        updates_by_vendor[vendor] = enriched_updates
    
    # 构建响应
    report = ReportData(
        report_type=report_type,
        date_from=report_data.get('date_from', ''),
        date_to=report_data.get('date_to', ''),
        generated_at=report_data.get('generated_at'),
        ai_summary=report_data.get('ai_summary'),
        html_filepath=report_data.get('html_filepath'),
        total_count=report_data.get('total_count', 0),
        vendor_summaries=vendor_summaries,
        updates_by_vendor=updates_by_vendor
    )
    
    return ApiResponse(success=True, data=report)


@router.get("/{report_type}/available-months", response_model=ApiResponse[List[dict]])
async def get_available_months(
    report_type: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    获取可用的月份列表

    用于前端月份选择器
    """
    if report_type != 'monthly':
        return ApiResponse(success=True, data=[])

    # 查询已生成的月报
    report_repo = ReportRepository()
    reports = report_repo.get_available_reports('monthly')

    months = []
    for r in reports:
        # 跳过无效数据
        if not r.get('year') or not r.get('month'):
            continue

        months.append({
            'year': r['year'],
            'month': r['month'],
            'label': f"{r['year']}年{r['month']:02d}月"
        })

    return ApiResponse(success=True, data=months)


@router.get("/{report_type}/available-weeks", response_model=ApiResponse[List[dict]])
async def get_available_weeks(
    report_type: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    获取可用的周列表

    用于前端周选择器
    """
    if report_type != 'weekly':
        return ApiResponse(success=True, data=[])

    # 查询已生成的周报
    report_repo = ReportRepository()
    reports = report_repo.get_available_reports('weekly')

    weeks = []
    for r in reports:
        # 跳过无效数据
        if not r.get('year') or not r.get('week'):
            continue

        weeks.append({
            'year': r['year'],
            'week': r['week'],
            'label': f"{r['year']}年第{r['week']:02d}周",
            'date_from': r.get('date_from', ''),
            'date_to': r.get('date_to', '')
        })

    return ApiResponse(success=True, data=weeks)
