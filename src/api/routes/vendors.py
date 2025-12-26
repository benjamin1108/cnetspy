#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
厂商与元数据接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.models.update import UpdateType
from ..dependencies import get_db
from ..schemas.analysis import VendorInfo, ProductInfo, UpdateTypeInfo
from ..schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["元数据"])


# 来源类型标签映射
SOURCE_CHANNEL_LABELS = {
    'whatsnew': 'What\'s New',
    'blog': 'Blog',
}

# 更新类型描述映射
UPDATE_TYPE_LABELS = {
    'new_product': ('新产品发布', '全新产品/服务上线'),
    'new_feature': ('新功能发布', '现有产品新增功能'),
    'enhancement': ('功能增强', '现有功能优化升级'),
    'deprecation': ('功能弃用', '功能下线/弃用通知'),
    'pricing': ('定价调整', '价格变化相关'),
    'region': ('区域扩展', '新区域/可用区上线'),
    'security': ('安全更新', '安全补丁/增强'),
    'fix': ('问题修复', 'Bug修复'),
    'performance': ('性能优化', '性能提升相关'),
    'compliance': ('合规认证', '合规/认证相关'),
    'integration': ('集成能力', '第三方集成/API更新'),
    'other': ('其他', '无法归类的更新'),
}


@router.get("/vendors", response_model=ApiResponse[List[VendorInfo]])
async def list_vendors(db: UpdateDataLayer = Depends(get_db)):
    """
    厂商列表
    
    返回所有支持的云厂商元数据：
    - vendor: 厂商标识 (aws/azure/gcp等)
    - name: 厂商全称
    - total_updates: 更新总数
    - source_channels: 数据来源渠道列表
    
    用于前端下拉选择器
    """
    vendors = db.get_vendors_list()
    
    return ApiResponse(success=True, data=vendors)


@router.get("/vendors/{vendor}/products", response_model=ApiResponse[List[ProductInfo]])
async def list_vendor_products(
    vendor: str,
    db: UpdateDataLayer = Depends(get_db)
):
    """
    厂商产品子类列表
    
    返回指定厂商的产品子类列表：
    - product_subcategory: 产品子类
    - count: 相关更新数量
    
    用于前端产品筛选器
    """
    # 验证厂商是否存在
    vendors = db.get_vendors_list()
    vendor_ids = [v['vendor'] for v in vendors]
    
    if vendor not in vendor_ids:
        raise HTTPException(status_code=404, detail=f"厂商不存在: {vendor}")
    
    products = db.get_vendor_products(vendor)
    
    return ApiResponse(success=True, data=products)


@router.get("/update-types", response_model=ApiResponse[List[UpdateTypeInfo]])
async def list_update_types(db: UpdateDataLayer = Depends(get_db)):
    """
    更新类型枚举
    
    返回所有更新类型及其统计：
    - value: 枚举值
    - label: 中文标签
    - description: 类型描述
    - count: 当前使用该类型的更新数量
    
    用于前端筛选器和表单验证
    """
    # 获取数据库中的类型统计
    type_stats = db.get_update_type_statistics()
    type_count_map = {item['value']: item['count'] for item in type_stats}
    
    # 构建完整的类型列表（包含所有枚举值）
    result = []
    for type_value in UpdateType.values():
        label, description = UPDATE_TYPE_LABELS.get(type_value, (type_value, ''))
        result.append({
            'value': type_value,
            'label': label,
            'description': description,
            'count': type_count_map.get(type_value, 0)
        })
    
    # 按使用数量倒序排列
    result.sort(key=lambda x: x['count'], reverse=True)
    
    return ApiResponse(success=True, data=result)


@router.get("/source-channels", response_model=ApiResponse[List[dict]])
async def list_source_channels(db: UpdateDataLayer = Depends(get_db)):
    """
    来源类型枚举
    
    返回所有来源类型及其统计：
    - value: 枚举值
    - label: 显示标签
    - count: 当前使用该类型的更新数量
    
    用于前端筛选器
    """
    # 从数据库查询所有 source_channel 统计
    channels = db.get_source_channel_statistics()
    
    # 合并 blog 类型：*-blog 都归类为 blog
    blog_count = 0
    whatsnew_count = 0
    
    for item in channels:
        channel = item['value']
        if channel == 'whatsnew':
            whatsnew_count = item['count']
        elif channel.endswith('-blog') or channel == 'blog':
            blog_count += item['count']
    
    # 构建结果（只返回两种）
    result = []
    if whatsnew_count > 0:
        result.append({
            'value': 'whatsnew',
            'label': "What's New",
            'count': whatsnew_count
        })
    if blog_count > 0:
        result.append({
            'value': 'blog',
            'label': 'Blog',
            'count': blog_count
        })
    
    # 按使用数量倒序排列
    result.sort(key=lambda x: x['count'], reverse=True)
    
    return ApiResponse(success=True, data=result)
