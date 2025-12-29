#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
报告相关数据模型
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class ReportUpdateItem(BaseModel):
    """
    报告中的更新项
    
    用于报告页面展示单条更新
    """
    update_id: str
    vendor: str
    title: str
    title_translated: Optional[str] = None
    content_summary: Optional[str] = None
    publish_date: date
    update_type: Optional[str] = None
    source_channel: str


class VendorSummary(BaseModel):
    """
    厂商统计摘要
    
    用于报告页面的厂商统计卡片
    """
    vendor: str
    count: int
    analyzed: int
    update_types: dict = Field(default_factory=dict)


class ReportData(BaseModel):
    """
    报告数据
    
    包含时间范围、统计和更新列表
    """
    report_type: str = Field(..., description="报告类型: weekly/monthly")
    date_from: str = Field(..., description="开始日期 YYYY-MM-DD")
    date_to: str = Field(..., description="结束日期 YYYY-MM-DD")
    generated_at: Optional[str] = Field(None, description="生成时间")
    
    # AI 摘要
    ai_summary: Optional[str] = Field(None, description="AI 生成的月度趋势摘要")
    
    # 统计数据
    total_count: int = Field(0, description="更新总数")
    vendor_summaries: List[VendorSummary] = Field(default_factory=list)
    
    # 按厂商分组的更新列表
    updates_by_vendor: dict = Field(default_factory=dict, description="按厂商分组的更新: {vendor: [updates]}")
