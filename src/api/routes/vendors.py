#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
厂商与元数据接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
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
async def list_update_types(
    vendor: Optional[str] = Query(None, description="厂商过滤"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    更新类型枚举
    
    返回所有更新类型及其统计：
    - value: 枚举值
    - label: 中文标签
    - description: 类型描述
    - count: 当前使用该类型的更新数量
    
    用于前端筛选器和表单验证
    """
    # 获取数据库中的类型统计（返回字典 {type: count}）
    type_stats = db.get_update_type_statistics(vendor=vendor)
    
    # 获取统一的标签定义
    type_labels = UpdateType.get_labels()
    
    # 构建完整的类型列表（仅包含 count > 0 的项）
    result = []
    for type_value in UpdateType.values():
        count = type_stats.get(type_value, 0)
        if count > 0:
            label, description = type_labels.get(type_value, (type_value, ''))
            result.append({
                'value': type_value,
                'label': label,
                'description': description,
                'count': count
            })
    
    # 自定义排序逻辑
    # 优先级：核心发布 > 专项优化 > 常规 > 深度内容 > 风险类 > 其他
    sort_order = [
        # 1. 核心发布
        UpdateType.NEW_PRODUCT.value, UpdateType.NEW_FEATURE.value, UpdateType.ENHANCEMENT.value,
        
        # 2. 专项优化
        UpdateType.PERFORMANCE.value, UpdateType.COMPLIANCE.value, UpdateType.INTEGRATION.value,
        
        # 3. 常规更新
        UpdateType.PRICING.value, UpdateType.REGION.value, UpdateType.FIX.value,
        
        # 4. 深度内容
        UpdateType.BEST_PRACTICE.value, UpdateType.CASE_STUDY.value,
        
        # 5. 风险预警 (倒数第二)
        UpdateType.BREAKING_CHANGE.value, UpdateType.KNOWN_ISSUE.value, UpdateType.SECURITY.value, UpdateType.DEPRECATION.value,
        
        # 6. 其他 (最后)
        UpdateType.OTHER.value
    ]
    
    # 创建排序索引映射
    sort_index = {val: idx for idx, val in enumerate(sort_order)}
    
    # 执行排序：先按预定义顺序，未定义的放最后
    result.sort(key=lambda x: sort_index.get(x['value'], 999))
    
    return ApiResponse(success=True, data=result)


@router.get("/tags", response_model=ApiResponse[List[dict]])
async def list_tags(
    vendor: Optional[str] = Query(None, description="厂商过滤"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    标签列表
    
    返回所有标签及其统计：
    - value: 标签名称
    - count: 使用该标签的更新数量
    
    支持按厂商过滤
    """
    tags = db.get_tags_list(vendor=vendor)
    
    return ApiResponse(success=True, data=tags)


@router.get("/product-subcategories", response_model=ApiResponse[List[dict]])
async def list_product_subcategories(
    vendor: str = Query(None, description="厂商过滤"),
    db: UpdateDataLayer = Depends(get_db)
):
    """
    产品子类枚举
    
    返回所有产品子类及其统计：
    - value: 子类名称
    - count: 当前使用该子类的更新数量
    
    支持按厂商过滤
    """
    if vendor:
        # 按厂商过滤
        products = db.get_vendor_products(vendor)
    else:
        # 汇总所有厂商的产品子类
        vendors = db.get_vendors_list()
        subcat_counts = {}
        for v in vendors:
            products = db.get_vendor_products(v['vendor'])
            for p in products:
                subcat = p['product_subcategory']
                subcat_counts[subcat] = subcat_counts.get(subcat, 0) + p['count']
        products = [{'product_subcategory': k, 'count': v} for k, v in subcat_counts.items()]
    
    # 转换为前端需要的格式
    result = [
        {'value': p['product_subcategory'], 'count': p['count']}
        for p in products
    ]
    
    # 按数量倒序
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
