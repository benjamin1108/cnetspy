#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新数据业务服务

处理更新数据的查询和转换逻辑
"""

import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from src.storage.database.sqlite_layer import UpdateDataLayer
from ..schemas.common import PaginationMeta
from ..utils.time_utils import format_dict_datetimes


class UpdateService:
    """更新数据业务服务"""
    
    def __init__(self, db: UpdateDataLayer):
        """
        初始化服务
        
        Args:
            db: UpdateDataLayer 实例
        """
        self.db = db
    
    def get_updates_paginated(
        self, 
        filters: dict, 
        page: int, 
        page_size: int,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> Tuple[List[Dict], PaginationMeta]:
        """
        分页查询更新列表
        
        Args:
            filters: 过滤条件字典
            page: 页码
            page_size: 每页数量
            sort_by: 排序字段
            order: 排序方向
            
        Returns:
            (更新列表, 分页元数据) 元组
        """
        # 1. 查询总数
        total = self.db.count_updates_with_filters(**filters)
        
        # 2. 计算分页
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        offset = (page - 1) * page_size
        
        # 3. 查询当前页数据
        rows = self.db.query_updates_paginated(
            filters=filters, 
            limit=page_size, 
            offset=offset, 
            sort_by=sort_by, 
            order=order
        )
        
        # 4. 处理数据
        items = [self._process_update_row(row) for row in rows]
        
        # 5. 返回数据 + 分页元数据
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )
        
        return items, pagination
    
    def get_updates_by_filters(
        self,
        filters: dict,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> List[Dict]:
        """
        按条件查询所有更新（不分页）
        
        用于报告等需要获取全部数据的场景
        
        Args:
            filters: 过滤条件字典（date_from, date_to, has_analysis 等）
            sort_by: 排序字段
            order: 排序方向
            
        Returns:
            更新列表
        """
        # 查询所有符合条件的数据（limit 设置足够大）
        rows = self.db.query_updates_paginated(
            filters=filters,
            limit=1000,  # 报告场景不会超过这个数
            offset=0,
            sort_by=sort_by,
            order=order
        )
        
        return [self._process_update_row(row) for row in rows]
    
    def get_update_detail(self, update_id: str) -> Optional[Dict]:
        """
        获取更新详情
        
        Args:
            update_id: 更新ID
            
        Returns:
            更新详情字典，不存在返回None
        """
        row = self.db.get_update_by_id(update_id)
        if not row:
            return None
        
        return self._process_update_row(row, include_content=True)
    
    def _process_update_row(self, row: dict, include_content: bool = False) -> dict:
        """
        处理数据库行，转换为API格式
        
        关键处理：
        1. tags: JSON字符串 -> Python list
        2. has_analysis: 基于 title_translated 字段增强判定
        3. publish_date: TEXT -> date对象
        4. 过滤掉前端不需要的字段
        
        Args:
            row: 数据库行字典
            include_content: 是否包含content字段（详情页需要）
            
        Returns:
            处理后的字典
        """
        result = dict(row)
        
        # 1. 解析tags JSON字符串
        tags_str = result.get('tags')
        if tags_str:
            try:
                result['tags'] = json.loads(tags_str)
                if not isinstance(result['tags'], list):
                    result['tags'] = []
            except (json.JSONDecodeError, TypeError):
                result['tags'] = []
        else:
            result['tags'] = []
        
        # 2. 判定是否已分析（增强验证，排除无效值）
        title_trans = (result.get('title_translated') or '').strip()
        result['has_analysis'] = bool(
            title_trans and 
            len(title_trans) >= 2 and  # 排除单字符无效值
            title_trans not in ['N/A', '暂无', 'None', 'null']  # 排除常见无效值
        )
        
        # 3. 转换日期类型
        if 'publish_date' in result and isinstance(result['publish_date'], str):
            try:
                result['publish_date'] = datetime.strptime(result['publish_date'], '%Y-%m-%d').date()
            except ValueError:
                pass  # 保留原始字符串
        
        # 4. 过滤掉前端不需要的内部字段
        internal_fields = ['source_identifier', 'file_hash', 'metadata_json', 'priority']
        for field in internal_fields:
            result.pop(field, None)
        
        # 5. 如果是列表查询，移除content字段（减少数据传输量）
        if not include_content:
            result.pop('content', None)
            result.pop('content_summary', None)
        
        # 6. 格式化时间字段为 ISO 8601 UTC
        format_dict_datetimes(result, ['crawl_time', 'created_at', 'updated_at'])
        
        return result
