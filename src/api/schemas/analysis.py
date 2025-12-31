#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析任务相关的Pydantic模型
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AnalysisTaskCreate(BaseModel):
    """
    创建批量分析任务请求
    
    示例:
        {
            "filters": {
                "vendor": "aws",
                "has_analysis": false,
                "date_from": "2024-01-01"
            },
            "batch_size": 50
        }
    """
    filters: dict = Field(default_factory=dict, description="过滤条件（同查询接口）")
    batch_size: int = Field(50, ge=1, le=100, description="每批处理数量")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "filters": {
                    "vendor": "aws",
                    "has_analysis": False,
                    "date_from": "2024-01-01"
                },
                "batch_size": 50
            }
        }
    }


class AnalysisTaskDetail(BaseModel):
    """
    分析任务详情
    
    示例:
        {
            "task_id": "task_abc123",
            "status": "running",
            "filters": {...},
            "total_count": 100,
            "processed_count": 45,
            "success_count": 43,
            "fail_count": 2,
            "progress": 0.45,
            "created_at": "2024-01-01T10:00:00Z",
            "started_at": "2024-01-01T10:00:05Z",
            "completed_at": null,
            "error_message": null
        }
    """
    task_id: str
    status: str  # queued, running, completed, failed
    filters: dict
    total_count: int = 0
    processed_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    progress: float = Field(0.0, ge=0.0, le=1.0, description="进度百分比")
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class SingleAnalysisRequest(BaseModel):
    """
    单条分析请求（强制重新分析）
    
    示例:
        {"force": true}
    """
    force: bool = Field(False, description="是否强制重新分析（覆盖已有结果）")


class AnalysisResult(BaseModel):
    """
    单条分析结果
    
    示例:
        {
            "update_id": "aws_blog_20240101_abc123",
            "success": true,
            "title_translated": "AWS发布VPC Lattice...",
            "content_summary": "...",
            "update_type": "new_feature",
            "tags": ["VPC", "服务网格"],
            "product_subcategory": "networking",
            "analysis_filepath": "/path/to/file.json",
            "error": null
        }
    """
    update_id: str
    success: bool
    title_translated: Optional[str] = None
    content_summary: Optional[str] = None
    update_type: Optional[str] = None
    tags: List[str] = []
    product_subcategory: Optional[str] = None
    analysis_filepath: Optional[str] = None
    error: Optional[str] = None


class StatsOverview(BaseModel):
    """
    全局统计概览
    
    示例:
        {
            "total_updates": 1234,
            "vendors": {
                "aws": {"total": 500, "analyzed": 450},
                "azure": {"total": 400, "analyzed": 380}
            },
            "update_types": {
                "new_feature": 300,
                "enhancement": 250
            },
            "last_crawl_time": "2024-01-01T10:00:00Z",
            "analysis_coverage": 0.85
        }
    """
    total_updates: int
    vendors: dict  # {vendor: {total, analyzed}}
    update_types: dict  # {type: count}
    last_crawl_time: Optional[str] = None
    last_daily_task_time: Optional[str] = Field(None, description="最近一次每日爬取任务时间")
    analysis_coverage: float = Field(0.0, ge=0.0, le=1.0)


class TimelineItem(BaseModel):
    """
    时间线统计项
    
    示例:
        {
            "date": "2024-01-01",
            "count": 10,
            "vendors": {"aws": 5, "azure": 5}
        }
    """
    date: str
    count: int
    vendors: dict = Field(default_factory=dict)  # {vendor: count}


class TrendData(BaseModel):
    """
    环比趋势数据
    """
    change_percent: float
    direction: str  # 'up' | 'down' | 'flat'
    current_period: int
    previous_period: int


class VendorStatsItem(BaseModel):
    """
    厂商统计项
    
    示例:
        {
            "vendor": "aws",
            "count": 500,
            "analyzed": 450,
            "trend": {...}
        }
    """
    vendor: str
    count: int
    analyzed: int = 0
    trend: Optional[TrendData] = None


class VendorInfo(BaseModel):
    """
    厂商信息
    
    示例:
        {
            "vendor": "aws",
            "name": "Amazon Web Services",
            "total_updates": 500,
            "source_channels": ["blog", "whatsnew"]
        }
    """
    vendor: str
    name: str
    total_updates: int
    source_channels: List[str] = Field(default_factory=list)


class ProductInfo(BaseModel):
    """
    产品子类信息
    
    示例:
        {
            "product_subcategory": "vpc",
            "count": 100
        }
    """
    product_subcategory: str
    count: int


class UpdateTypeInfo(BaseModel):
    """
    更新类型信息
    
    示例:
        {
            "value": "new_feature",
            "label": "新功能发布",
            "description": "现有产品新增功能",
            "count": 300
        }
    """
    value: str
    label: str
    description: str = ""
    count: int = 0
