#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新数据相关的Pydantic模型
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class UpdateBrief(BaseModel):
    """
    更新列表项（简化版）- 用于列表展示
    
    示例:
        {
            "update_id": "aws_blog_20240101_abc123",
            "vendor": "aws",
            "source_channel": "blog",
            "title": "Announcing VPC Lattice...",
            "title_translated": "AWS发布VPC Lattice服务网格",
            "publish_date": "2024-01-01",
            "product_name": "VPC",
            "update_type": "new_feature",
            "tags": ["VPC", "服务网格"],
            "has_analysis": true
        }
    """
    update_id: str
    vendor: str
    source_channel: str
    title: str
    title_translated: Optional[str] = None
    description: Optional[str] = None
    publish_date: date
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    update_type: Optional[str] = None
    tags: List[str] = []
    has_analysis: bool
    
    @field_validator('publish_date', mode='before')
    @classmethod
    def parse_publish_date(cls, v):
        """兼容数据库TEXT类型日期"""
        if isinstance(v, str):
            from datetime import datetime
            return datetime.strptime(v, '%Y-%m-%d').date()
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "update_id": "aws_blog_20240101_abc123",
                "vendor": "aws",
                "source_channel": "blog",
                "title": "Announcing VPC Lattice...",
                "title_translated": "AWS发布VPC Lattice服务网格",
                "description": "VPC Lattice is a new service...",
                "publish_date": "2024-01-01",
                "product_name": "VPC",
                "product_category": "Networking",
                "update_type": "new_feature",
                "tags": ["VPC", "服务网格", "IPv6"],
                "has_analysis": True
            }
        }
    }


class UpdateDetail(UpdateBrief):
    """
    更新详情（完整版）- 用于详情页展示
    
    继承UpdateBrief的所有字段，并添加详细内容
    """
    content: str
    content_summary: Optional[str] = None
    product_subcategory: Optional[str] = None
    source_url: str
    crawl_time: Optional[str] = None
    raw_filepath: Optional[str] = None
    analysis_filepath: Optional[str] = None
    created_at: Optional[str] = None  # ISO 8601 UTC 格式
    updated_at: Optional[str] = None  # ISO 8601 UTC 格式


class UpdateQueryParams(BaseModel):
    """
    查询参数验证
    
    用于GET /api/v1/updates接口的查询参数校验
    """
    vendor: Optional[str] = Field(None, description="厂商过滤（aws/azure/gcp等）")
    source_channel: Optional[str] = Field(None, description="来源类型（blog/whatsnew）")
    update_type: Optional[str] = Field(None, description="更新类型")
    product_name: Optional[str] = Field(None, description="产品名称（模糊匹配）")
    product_category: Optional[str] = Field(None, description="产品分类")
    date_from: Optional[str] = Field(None, description="开始日期（YYYY-MM-DD）")
    date_to: Optional[str] = Field(None, description="结束日期（YYYY-MM-DD）")
    has_analysis: Optional[bool] = Field(None, description="是否已AI分析")
    keyword: Optional[str] = Field(None, description="关键词搜索（标题+内容）")
    tags: Optional[str] = Field(None, description="标签过滤（逗号分隔）")
    sort_by: str = Field("publish_date", description="排序字段")
    order: str = Field("desc", description="排序方向（asc/desc）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
