#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Updates 表 Repository - CRUD 操作

提供 updates 表的增删改查基础操作。
"""

import sqlite3
from typing import Dict, List, Any, Optional, Tuple

from src.storage.database.base import BaseRepository


class UpdatesRepository(BaseRepository):
    """Updates 表 CRUD 操作"""
    
    # 必填字段列表
    REQUIRED_FIELDS = ['update_id', 'vendor', 'source_channel', 'source_url', 'title', 'publish_date']
    
    def _validate_update_data(self, update_data: Dict[str, Any]) -> tuple:
        """
        校验 Update 数据
        
        Returns:
            (is_valid, error_message)
        """
        # 必填字段校验
        for field in self.REQUIRED_FIELDS:
            value = update_data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                return False, f"必填字段 {field} 为空"
        
        # URL 格式校验
        source_url = update_data.get('source_url', '')
        if not source_url.startswith(('http://', 'https://')):
            return False, f"source_url 格式无效 - {source_url}"
        
        return True, None
    
    def insert_update(self, update_data: Dict[str, Any]) -> bool:
        """
        插入单条 Update 记录
        
        Args:
            update_data: Update 数据字典
            
        Returns:
            成功返回 True，失败返回 False
        """
        # 数据校验
        is_valid, error_msg = self._validate_update_data(update_data)
        if not is_valid:
            self.logger.error(f"插入失败: {error_msg}")
            return False
        
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO updates (
                            update_id, vendor, source_channel, update_type, source_url, source_identifier,
                            title, title_translated, description, content, content_translated, content_summary, 
                            publish_date, crawl_time, product_name, product_category, product_subcategory, 
                            priority, tags, raw_filepath, analysis_filepath, file_hash, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        update_data.get('update_id'),
                        update_data.get('vendor'),
                        update_data.get('source_channel', 'unknown'),
                        update_data.get('update_type'),
                        update_data.get('source_url'),
                        update_data.get('source_identifier', ''),
                        update_data.get('title'),
                        update_data.get('title_translated'),
                        update_data.get('description'),
                        update_data.get('content'),
                        update_data.get('content_translated'),
                        update_data.get('content_summary'),
                        update_data.get('publish_date'),
                        update_data.get('crawl_time'),
                        update_data.get('product_name'),
                        update_data.get('product_category'),
                        update_data.get('product_subcategory'),
                        update_data.get('priority'),
                        update_data.get('tags'),
                        update_data.get('raw_filepath'),
                        update_data.get('analysis_filepath'),
                        update_data.get('file_hash'),
                        update_data.get('metadata_json')
                    ))
                    
                    conn.commit()
                    self.logger.debug(f"插入 Update 记录: {update_data.get('update_id')}")
                    return True
                    
        except sqlite3.IntegrityError:
            # 唯一性约束冲突，记录已存在
            self.logger.debug(
                f"Update 记录已存在: {update_data.get('source_url')}, "
                f"{update_data.get('source_identifier')}"
            )
            return False
        except Exception as e:
            self.logger.error(f"插入 Update 记录失败: {e}")
            return False
    
    def delete_update(self, update_id: str) -> bool:
        """
        删除单条 Update 记录
        
        Args:
            update_id: 记录 ID
            
        Returns:
            成功返回 True，失败返回 False
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM updates WHERE update_id = ?', (update_id,))
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"删除 Update 记录: {update_id}")
                        return True
                    else:
                        self.logger.warning(f"Update 记录不存在: {update_id}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"删除 Update 记录失败: {e}")
            return False
    
    def batch_insert_updates(
        self, 
        updates_data: List[Dict[str, Any]], 
        force_update: bool = False
    ) -> Tuple[int, int]:
        """
        批量插入 Update 记录
        
        Args:
            updates_data: Update 数据列表
            force_update: 是否强制更新已存在的记录
            
        Returns:
            (成功数量, 失败数量) 元组
        """
        if not updates_data:
            return (0, 0)
        
        success_count = 0
        fail_count = 0
        
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    for update_data in updates_data:
                        try:
                            # 数据校验
                            is_valid, error_msg = self._validate_update_data(update_data)
                            if not is_valid:
                                self.logger.error(f"批量插入跳过: {error_msg}")
                                fail_count += 1
                                continue

                            if (
                                not force_update
                                and update_data.get('source_identifier')
                                and update_data.get('vendor')
                                and update_data.get('source_channel')
                                and self.check_update_exists(
                                    update_data.get('source_url', ''),
                                    update_data.get('source_identifier', ''),
                                    vendor=update_data.get('vendor'),
                                    source_channel=update_data.get('source_channel'),
                                )
                            ):
                                fail_count += 1
                                self.logger.warning(
                                    f"插入跳过(已存在identifier): {update_data.get('vendor')}/"
                                    f"{update_data.get('source_channel')}/{update_data.get('source_identifier')}"
                                )
                                continue
                            
                            self.logger.debug(
                                f"插入数据: update_id={update_data.get('update_id')}, "
                                f"vendor={update_data.get('vendor')}, "
                                f"source_channel={update_data.get('source_channel')}"
                            )
                            
                            # 根据 force_update 决定使用 IGNORE 还是 REPLACE
                            sql_prefix = 'INSERT OR REPLACE' if force_update else 'INSERT OR IGNORE'
                            cursor.execute(f'''
                                {sql_prefix} INTO updates (
                                    update_id, vendor, source_channel, update_type, source_url, source_identifier,
                                    title, title_translated, content, content_translated, content_summary, 
                                    publish_date, crawl_time, product_name, product_category, product_subcategory, 
                                    priority, tags, raw_filepath, analysis_filepath, file_hash, metadata_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                update_data.get('update_id'),
                                update_data.get('vendor'),
                                update_data.get('source_channel', 'unknown'),
                                update_data.get('update_type'),
                                update_data.get('source_url'),
                                update_data.get('source_identifier', ''),
                                update_data.get('title'),
                                update_data.get('title_translated'),
                                update_data.get('content'),
                                update_data.get('content_translated'),
                                update_data.get('content_summary'),
                                update_data.get('publish_date'),
                                update_data.get('crawl_time'),
                                update_data.get('product_name'),
                                update_data.get('product_category'),
                                update_data.get('product_subcategory'),
                                update_data.get('priority'),
                                update_data.get('tags'),
                                update_data.get('raw_filepath'),
                                update_data.get('analysis_filepath'),
                                update_data.get('file_hash'),
                                update_data.get('metadata_json')
                            ))
                            
                            if cursor.rowcount > 0:
                                success_count += 1
                            else:
                                fail_count += 1
                                self.logger.warning(
                                    f"插入失败(rowcount=0): {update_data.get('source_url')}"
                                )
                                
                        except Exception as e:
                            self.logger.error(
                                f"批量插入单条记录失败: {e}, "
                                f"数据: {update_data.get('source_url')}"
                            )
                            fail_count += 1
                    
                    conn.commit()
                    self.logger.debug(f"批量插入: 成功 {success_count}, 失败 {fail_count}")
                    
        except Exception as e:
            self.logger.error(f"批量插入 Update 记录失败: {e}")
            fail_count = len(updates_data)
        
        return (success_count, fail_count)
    
    def check_update_exists(
        self,
        source_url: str,
        source_identifier: str = '',
        vendor: Optional[str] = None,
        source_channel: Optional[str] = None,
    ) -> bool:
        """
        检查 Update 是否存在
        
        Args:
            source_url: 来源 URL
            source_identifier: 来源标识
            
        Returns:
            存在返回 True，不存在返回 False
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if source_identifier and vendor and source_channel:
                    cursor.execute('''
                        SELECT 1 FROM updates
                        WHERE vendor = ? AND source_channel = ? AND source_identifier = ?
                        LIMIT 1
                    ''', (vendor, source_channel, source_identifier))
                else:
                    cursor.execute('''
                        SELECT 1 FROM updates
                        WHERE source_url = ? AND source_identifier = ?
                        LIMIT 1
                    ''', (source_url, source_identifier))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            self.logger.error(f"检查 Update 是否存在失败: {e}")
            return False
    
    def get_update_by_id(self, update_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 update_id 获取 Update 记录
        
        Args:
            update_id: Update ID
            
        Returns:
            Update 数据字典，不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM updates WHERE update_id = ?', (update_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"获取 Update 记录失败: {e}")
            return None

    def find_updates_by_business_key(
        self,
        vendor: str,
        source_channel: str,
        publish_date: str,
        product_name: str,
        title: str,
    ) -> List[Dict[str, Any]]:
        """按业务键查找候选记录。"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT *
                    FROM updates
                    WHERE vendor = ?
                    AND source_channel = ?
                    AND publish_date = ?
                    AND product_name = ?
                    AND title = ?
                    ORDER BY crawl_time DESC, created_at DESC
                    ''',
                    (vendor, source_channel, publish_date, product_name, title),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"按业务键查询 Update 失败: {e}")
            return []

    def update_raw_fields(self, update_id: str, fields: Dict[str, Any]) -> bool:
        """仅更新原始抓取相关字段，保留分析和分类结果。"""
        allowed_fields = {
            'source_identifier',
            'description',
            'content',
            'publish_date',
            'crawl_time',
            'raw_filepath',
            'file_hash',
            'metadata_json',
            'source_url',
            'update_type',
            'product_name',
            'title',
        }
        update_fields = {k: v for k, v in fields.items() if k in allowed_fields}
        if not update_fields:
            self.logger.warning("没有有效的原始字段需要更新")
            return False

        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    set_clauses = [f"{field} = ?" for field in update_fields.keys()]
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values = list(update_fields.values())
                    values.append(update_id)
                    sql = f"UPDATE updates SET {', '.join(set_clauses)} WHERE update_id = ?"
                    cursor.execute(sql, values)
                    conn.commit()
                    if cursor.rowcount > 0:
                        return True
                    self.logger.warning(f"未找到更新记录: {update_id}")
                    return False
        except sqlite3.IntegrityError as e:
            self.logger.warning(f"更新原始字段触发唯一约束: {update_id}, {e}")
            return False
        except Exception as e:
            self.logger.error(f"更新原始字段失败: {e}")
            return False
    
    def count_updates(self, **filters) -> int:
        """
        统计符合条件的 Update 数量（只统计 whatsnew）
        
        Args:
            **filters: 过滤条件 (vendor, update_type, date_from, date_to 等)
            
        Returns:
            记录数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["source_channel = 'whatsnew'"]  # 默认只统计 whatsnew
                params = []
                
                if filters.get('vendor'):
                    where_clauses.append('vendor = ?')
                    params.append(filters['vendor'])
                
                if filters.get('update_type'):
                    where_clauses.append('update_type = ?')
                    params.append(filters['update_type'])
                
                if filters.get('date_from'):
                    where_clauses.append('publish_date >= ?')
                    params.append(filters['date_from'])
                
                if filters.get('date_to'):
                    where_clauses.append('publish_date <= ?')
                    params.append(filters['date_to'])
                
                where_clause = ' AND '.join(where_clauses) if where_clauses else '1=1'
                
                cursor.execute(
                    f'SELECT COUNT(*) as count FROM updates WHERE {where_clause}', 
                    params
                )
                result = cursor.fetchone()
                
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计 Update 数量失败: {e}")
            return 0
    
    def query_updates_paginated(
        self,
        filters: Dict[str, Any],
        limit: int,
        offset: int,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        通用分页查询方法（API 专用）
        
        Args:
            filters: 过滤条件字典，支持：
                - vendor, source_channel, update_type
                - product_name（模糊匹配）, product_category, product_subcategory
                - date_from, date_to
                - has_analysis（bool）
                - keyword（搜索 title + content）
                - tags（逗号分隔，OR 匹配）
            limit: 每页数量
            offset: 偏移量
            sort_by: 排序字段
            order: 排序方向（asc/desc）
            
        Returns:
            更新记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses, params = self._build_filter_clauses(filters)
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # 验证排序字段（防 SQL 注入）
                allowed_sort_fields = ['publish_date', 'crawl_time', 'update_id', 'vendor']
                if sort_by not in allowed_sort_fields:
                    sort_by = 'publish_date'
                
                # 验证排序方向
                order = order.upper()
                if order not in ['ASC', 'DESC']:
                    order = 'DESC'
                
                order_by_clauses = [f"{sort_by} {order}"]
                secondary_sorts = {
                    'publish_date': ['crawl_time DESC', 'created_at DESC', 'update_id ASC'],
                    'crawl_time': ['publish_date DESC', 'created_at DESC', 'update_id ASC'],
                    'vendor': ['publish_date DESC', 'crawl_time DESC', 'update_id ASC'],
                    'update_id': ['publish_date DESC', 'crawl_time DESC'],
                }
                for clause in secondary_sorts.get(sort_by, []):
                    if clause not in order_by_clauses:
                        order_by_clauses.append(clause)

                sql = f"""
                    SELECT * FROM updates
                    WHERE {where_clause}
                    ORDER BY {', '.join(order_by_clauses)}
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"分页查询失败: {e}")
            return []
    
    def count_updates_with_filters(self, **filters) -> int:
        """
        扩展版统计方法（支持所有过滤条件）
        
        Args:
            **filters: 与 query_updates_paginated 相同的过滤条件
            
        Returns:
            符合条件的记录数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses, params = self._build_filter_clauses(filters)
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
                cursor.execute(sql, params)
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计查询失败: {e}")
            return 0
    
    def _build_filter_clauses(self, filters: Dict[str, Any]) -> Tuple[List[str], List[Any]]:
        """
        构建过滤条件子句
        
        Args:
            filters: 过滤条件字典
            
        Returns:
            (where_clauses, params) 元组
        """
        where_clauses = []
        params = []
        
        # vendor 过滤
        if filters.get('vendor'):
            where_clauses.append("vendor = ?")
            params.append(filters['vendor'])
        
        # source_channel 过滤（blog 匹配所有 *-blog）
        if filters.get('source_channel'):
            sc = filters['source_channel']
            if sc == 'blog':
                where_clauses.append("(source_channel LIKE '%blog%')")
            else:
                where_clauses.append("source_channel = ?")
                params.append(sc)
        
        # update_type 过滤
        if filters.get('update_type'):
            where_clauses.append("update_type = ?")
            params.append(filters['update_type'])
        
        # product_name 模糊匹配
        if filters.get('product_name'):
            where_clauses.append("product_name LIKE ?")
            params.append(f"%{filters['product_name']}%")
        
        # product_category 过滤
        if filters.get('product_category'):
            where_clauses.append("product_category = ?")
            params.append(filters['product_category'])
        
        # product_subcategory 过滤
        if filters.get('product_subcategory'):
            where_clauses.append("product_subcategory = ?")
            params.append(filters['product_subcategory'])
        
        # 日期范围
        if filters.get('date_from'):
            where_clauses.append("publish_date >= ?")
            params.append(filters['date_from'])
        
        if filters.get('date_to'):
            where_clauses.append("publish_date <= ?")
            params.append(filters['date_to'])
        
        # has_analysis 过滤（增强判定）
        if filters.get('has_analysis') is not None:
            if filters['has_analysis']:
                where_clauses.append(
                    "title_translated IS NOT NULL "
                    "AND title_translated != '' "
                    "AND LENGTH(TRIM(title_translated)) >= 2 "
                    "AND title_translated NOT IN ('N/A', '暂无', 'None', 'null')"
                )
            else:
                where_clauses.append(
                    "(title_translated IS NULL "
                    "OR title_translated = '' "
                    "OR LENGTH(TRIM(title_translated)) < 2 "
                    "OR title_translated IN ('N/A', '暂无', 'None', 'null'))"
                )

        # exclude_backfill 过滤：仅排除“crawl_time 为今天且 publish_date 早于今天至少 7 天”的临时补全项
        if filters.get('exclude_backfill'):
            where_clauses.append(
                "NOT ("
                "crawl_time IS NOT NULL "
                "AND publish_date IS NOT NULL "
                "AND DATE(datetime(crawl_time)) = DATE('now', 'localtime') "
                "AND (julianday(DATE(datetime(crawl_time))) - julianday(publish_date)) >= 7"
                ")"
            )
        
        # keyword 关键词搜索（中英文标题 + 内容 + 摘要）
        if filters.get('keyword'):
            where_clauses.append(
                "(title LIKE ? OR title_translated LIKE ? OR content LIKE ? "
                "OR content_translated LIKE ? OR content_summary LIKE ?)"
            )
            keyword_param = f"%{filters['keyword']}%"
            params.extend([keyword_param] * 5)
        
        # tags 标签过滤
        if filters.get('tags'):
            tag_list = [t.strip() for t in filters['tags'].split(',')]
            tag_conditions = []
            for tag in tag_list:
                tag_conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
            where_clauses.append(f"({' OR '.join(tag_conditions)})")
        
        return where_clauses, params
