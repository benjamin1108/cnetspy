#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一业务数据层 - UpdateDataLayer组件

提供数据库连接管理、CRUD操作和查询封装,是统一业务数据层的核心组件。
"""

import os
import sqlite3
import logging
import threading
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class UpdateDataLayer:
    """统一业务数据层管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化UpdateDataLayer
        
        Args:
            db_path: 数据库文件路径,如果为None则使用默认路径
        """
        self.logger = logging.getLogger(__name__)
        
        if db_path is None:
            # 默认路径: data/sqlite/updates.db (项目根目录下)
            # __file__ = src/storage/database/sqlite_layer.py
            # 需要往上走4级才能到项目根目录
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            db_path = os.path.join(base_dir, 'data', 'sqlite', 'updates.db')
        
        self.db_path = db_path
        self.lock = threading.RLock()
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构和索引"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建updates表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS updates (
                    update_id TEXT PRIMARY KEY,
                    vendor TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    update_type TEXT,
                    source_url TEXT NOT NULL,
                    source_identifier TEXT NOT NULL DEFAULT '',
                    title TEXT,
                    title_translated TEXT,
                    description TEXT,
                    content TEXT,
                    content_summary TEXT,
                    publish_date TEXT,
                    crawl_time TEXT,
                    product_name TEXT,
                    product_category TEXT,
                    product_subcategory TEXT,
                    priority TEXT,
                    tags TEXT,
                    raw_filepath TEXT,
                    analysis_filepath TEXT,
                    file_hash TEXT,
                    metadata_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建组合唯一索引(核心去重约束)
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_updates_unique_source 
                ON updates(source_url, source_identifier)
            ''')
            
            # 创建单列索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_vendor ON updates(vendor)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_type ON updates(update_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_publish_date ON updates(publish_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_product_name ON updates(product_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_product_category ON updates(product_category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_priority ON updates(priority)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_source_url ON updates(source_url)')
            
            # 创建组合索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_updates_vendor_date 
                ON updates(vendor, publish_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_updates_type_date 
                ON updates(update_type, publish_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_updates_vendor_product 
                ON updates(vendor, product_name)
            ''')
            
            # 创建analysis_tasks表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_tasks (
                    task_id TEXT PRIMARY KEY,
                    update_id TEXT,
                    task_name TEXT NOT NULL,
                    task_status TEXT NOT NULL,
                    task_result TEXT,
                    error_message TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建analysis_tasks索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_analysis_tasks_update_id 
                ON analysis_tasks(update_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_analysis_tasks_task_name 
                ON analysis_tasks(task_name)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_analysis_tasks_task_status 
                ON analysis_tasks(task_status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_analysis_tasks_update_task 
                ON analysis_tasks(update_id, task_name)
            ''')
            
            # 创建migration_history表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS migration_history (
                    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_type TEXT NOT NULL,
                    source_path TEXT,
                    updates_count INTEGER DEFAULT 0,
                    tasks_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建migration_history索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_migration_history_type 
                ON migration_history(migration_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_migration_history_status 
                ON migration_history(status)
            ''')
            
            conn.commit()
            
            # 配置数据库参数
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
            cursor.execute('PRAGMA cache_size=-64000')  # 64MB缓存
            cursor.execute('PRAGMA temp_store=MEMORY')
            cursor.execute('PRAGMA foreign_keys=ON')
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def insert_update(self, update_data: Dict[str, Any]) -> bool:
        """
        插入单条Update记录
        
        Args:
            update_data: Update数据字典
            
        Returns:
            成功返回True,失败返回False
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO updates (
                            update_id, vendor, source_channel, update_type, source_url, source_identifier,
                            title, title_translated, description, content, content_summary, publish_date, crawl_time,
                            product_name, product_category, product_subcategory, priority, tags,
                            raw_filepath, analysis_filepath, file_hash, metadata_json
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
                        update_data.get('description'),
                        update_data.get('content'),
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
                    self.logger.debug(f"插入Update记录: {update_data.get('update_id')}")
                    return True
                    
        except sqlite3.IntegrityError as e:
            # 唯一性约束冲突,记录已存在
            self.logger.debug(f"Update记录已存在: {update_data.get('source_url')}, {update_data.get('source_identifier')}")
            return False
        except Exception as e:
            self.logger.error(f"插入Update记录失败: {e}")
            return False
    
    def batch_insert_updates(self, updates_data: List[Dict[str, Any]], force_update: bool = False) -> Tuple[int, int]:
        """
        批量插入Update记录
        
        Args:
            updates_data: Update数据列表
            force_update: 是否强制更新已存在的记录
            
        Returns:
            (成功数量, 失败数量)元组
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
                            # 调试日志：输出关键字段
                            self.logger.debug(f"插入数据: update_id={update_data.get('update_id')}, "
                                            f"vendor={update_data.get('vendor')}, "
                                            f"source_channel={update_data.get('source_channel')}, "
                                            f"source_url={update_data.get('source_url')[:50] if update_data.get('source_url') else None}")
                            
                            # 根据 force_update 决定使用 IGNORE 还是 REPLACE
                            sql_prefix = 'INSERT OR REPLACE' if force_update else 'INSERT OR IGNORE'
                            cursor.execute(f'''
                                {sql_prefix} INTO updates (
                                    update_id, vendor, source_channel, update_type, source_url, source_identifier,
                                    title, title_translated, content, content_summary, publish_date, crawl_time,
                                    product_name, product_category, product_subcategory, priority, tags,
                                    raw_filepath, analysis_filepath, file_hash, metadata_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                                self.logger.debug(f"插入成功: {update_data.get('source_url')[:50] if update_data.get('source_url') else None}")
                            else:
                                fail_count += 1
                                self.logger.warning(f"插入失败(rowcount=0): {update_data.get('source_url')}, source_identifier={update_data.get('source_identifier')}")
                                
                        except Exception as e:
                            self.logger.error(f"批量插入单条记录失败: {e}, 数据: {update_data.get('source_url')}")
                            fail_count += 1
                    
                    conn.commit()
                    self.logger.debug(f"批量插入: 成功{success_count}, 失败{fail_count}")
                    
        except Exception as e:
            self.logger.error(f"批量插入Update记录失败: {e}")
            fail_count = len(updates_data)
        
        return (success_count, fail_count)
    
    def check_update_exists(self, source_url: str, source_identifier: str = '') -> bool:
        """
        检查Update是否存在
        
        Args:
            source_url: 来源URL
            source_identifier: 来源标识
            
        Returns:
            存在返回True,不存在返回False
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 1 FROM updates 
                    WHERE source_url = ? AND source_identifier = ?
                    LIMIT 1
                ''', (source_url, source_identifier))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            self.logger.error(f"检查Update是否存在失败: {e}")
            return False
    
    def get_update_by_id(self, update_id: str) -> Optional[Dict[str, Any]]:
        """
        根据update_id获取Update记录
        
        Args:
            update_id: Update ID
            
        Returns:
            Update数据字典,不存在返回None
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
            self.logger.error(f"获取Update记录失败: {e}")
            return None
    
    def count_updates(self, **filters) -> int:
        """
        统计符合条件的Update数量
        
        Args:
            **filters: 过滤条件(vendor, update_type, date_from, date_to等)
            
        Returns:
            记录数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = []
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
                
                cursor.execute(f'SELECT COUNT(*) as count FROM updates WHERE {where_clause}', params)
                result = cursor.fetchone()
                
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计Update数量失败: {e}")
            return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总记录数
                cursor.execute('SELECT COUNT(*) as total FROM updates')
                total_updates = cursor.fetchone()['total']
                
                # 按厂商统计
                cursor.execute('''
                    SELECT vendor, COUNT(*) as count 
                    FROM updates 
                    GROUP BY vendor
                ''')
                vendor_stats = {row['vendor']: row['count'] for row in cursor.fetchall()}
                
                # 按类型统计
                cursor.execute('''
                    SELECT update_type, COUNT(*) as count 
                    FROM updates 
                    GROUP BY update_type
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                type_stats = {row['update_type']: row['count'] for row in cursor.fetchall()}
                
                # 文件大小
                file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    'total_updates': total_updates,
                    'vendor_stats': vendor_stats,
                    'type_stats': type_stats,
                    'file_size_bytes': file_size,
                    'file_size_mb': round(file_size / 1024 / 1024, 2),
                    'db_path': self.db_path
                }
                
        except Exception as e:
            self.logger.error(f"获取数据库统计信息失败: {e}")
            return {
                'total_updates': 0,
                'vendor_stats': {},
                'type_stats': {},
                'file_size_bytes': 0,
                'file_size_mb': 0,
                'db_path': self.db_path
            }
    
    def get_unanalyzed_updates(
        self, 
        limit: Optional[int] = None, 
        vendor: Optional[str] = None,
        include_analyzed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取未分析的更新记录
        
        Args:
            limit: 最大返回数量，None 表示不限制
            vendor: 指定厂商，None 表示所有厂商
            include_analyzed: 是否包含已分析的记录（用于 --force）
            
        Returns:
            未分析的更新记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clauses = [
                    "content IS NOT NULL",
                    "content != ''"
                ]
                
                # 如果不包含已分析的，添加未分析条件
                if not include_analyzed:
                    where_clauses.append("title_translated IS NULL")
                
                params = []
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                # 构建查询 SQL
                sql = f'''
                    SELECT update_id, vendor, source_channel, title, content,
                           product_name, product_category
                    FROM updates
                    WHERE {where_clause}
                    ORDER BY publish_date DESC
                '''
                
                if limit:
                    sql += f" LIMIT {limit}"
                
                cursor.execute(sql, params)
                
                results = [dict(row) for row in cursor.fetchall()]
                record_type = "记录" if include_analyzed else "未分析记录"
                self.logger.debug(f"查询到 {len(results)} 条{record_type}")
                
                return results
                
        except Exception as e:
            self.logger.error(f"获取更新记录失败: {e}")
            return []
    
    def count_unanalyzed_updates(self, vendor: Optional[str] = None, include_analyzed: bool = False) -> int:
        """
        统计未分析的更新记录数量
        
        Args:
            vendor: 指定厂商，None 表示所有厂商
            include_analyzed: 是否包含已分析的记录（用于 --force）
            
        Returns:
            未分析记录数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clauses = [
                    "content IS NOT NULL",
                    "content != ''"
                ]
                
                # 如果不包含已分析的，添加未分析条件
                if not include_analyzed:
                    where_clauses.append("title_translated IS NULL")
                
                params = []
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
                cursor.execute(sql, params)
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计未分析记录失败: {e}")
            return 0
    
    def update_analysis_fields(
        self, 
        update_id: str, 
        fields: Dict[str, Any]
    ) -> bool:
        """
        更新分析字段
            
        Args:
            update_id: 更新记录 ID
            fields: 要更新的字段字典,支持的字段包括：
                   title_translated, content_summary, update_type,
                   product_subcategory, tags
                       
        Returns:
            成功返回 True,失败返回 False
        """
        allowed_fields = {
            'title_translated',
            'content_summary',
            'update_type',
            'product_subcategory',
            'tags',
            'analysis_filepath'
        }
            
        # 过滤非法字段
        update_fields = {k: v for k, v in fields.items() if k in allowed_fields}
            
        if not update_fields:
            self.logger.warning("没有有效的字段需要更新")
            return False
            
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                        
                    # 构建 UPDATE SQL
                    set_clauses = [f"{field} = ?" for field in update_fields.keys()]
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    set_clause = ", ".join(set_clauses)
                        
                    values = list(update_fields.values())
                    values.append(update_id)
                        
                    sql = f"UPDATE updates SET {set_clause} WHERE update_id = ?"
                        
                    cursor.execute(sql, values)
                    conn.commit()
                        
                    if cursor.rowcount > 0:
                        self.logger.debug(f"更新分析字段成功: {update_id}")
                        return True
                    else:
                        self.logger.warning(f"未找到更新记录: {update_id}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"更新分析字段失败: {e}")
            return False
        
    # ==================== API 扩展方法 ====================
        
    def query_updates_paginated(
        self,
        filters: Dict[str, Any],
        limit: int,
        offset: int,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        通用分页查询方法（API专用）
            
        Args:
            filters: 过滤条件字典,支持：
                - vendor, source_channel, update_type
                - product_name（模糊匹配）, product_category
                - date_from, date_to
                - has_analysis（bool）
                - keyword（搜索title+content）
                - tags（逗号分隔,OR匹配）
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
                    
                where_clauses = []
                params = []
                    
                # vendor过滤
                if filters.get('vendor'):
                    where_clauses.append("vendor = ?")
                    params.append(filters['vendor'])
                    
                # source_channel过滤（blog 匹配所有 *-blog）
                if filters.get('source_channel'):
                    sc = filters['source_channel']
                    if sc == 'blog':
                        where_clauses.append("(source_channel LIKE '%blog%')")
                    else:
                        where_clauses.append("source_channel = ?")
                        params.append(sc)
                    
                # update_type过滤
                if filters.get('update_type'):
                    where_clauses.append("update_type = ?")
                    params.append(filters['update_type'])
                    
                # product_name模糊匹配
                if filters.get('product_name'):
                    where_clauses.append("product_name LIKE ?")
                    params.append(f"%{filters['product_name']}%")
                    
                # product_category过滤
                if filters.get('product_category'):
                    where_clauses.append("product_category = ?")
                    params.append(filters['product_category'])
                
                # product_subcategory过滤
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
                    
                # has_analysis过滤（增强判定）
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
                    
                # keyword关键词搜索
                if filters.get('keyword'):
                    where_clauses.append("(title LIKE ? OR content LIKE ?)")
                    keyword_param = f"%{filters['keyword']}%"
                    params.extend([keyword_param, keyword_param])
                    
                # tags标签过滤
                # ⚠️ 性能警告: LIKE查询无法使用索引
                if filters.get('tags'):
                    tag_list = [t.strip() for t in filters['tags'].split(',')]
                    tag_conditions = []
                    for tag in tag_list:
                        tag_conditions.append("tags LIKE ?")
                        # 匹配JSON数组中的字符串值
                        params.append(f'%"{tag}"%')
                    where_clauses.append(f"({' OR '.join(tag_conditions)})")
                    
                # 构建WHERE子句
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                    
                # 验证排序字段（防SQL注入）
                allowed_sort_fields = ['publish_date', 'crawl_time', 'update_id', 'vendor']
                if sort_by not in allowed_sort_fields:
                    sort_by = 'publish_date'
                    
                # 验证排序方向
                order = order.upper()
                if order not in ['ASC', 'DESC']:
                    order = 'DESC'
                    
                # 构建SQL
                sql = f"""
                    SELECT * FROM updates
                    WHERE {where_clause}
                    ORDER BY {sort_by} {order}
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
                    
                where_clauses = []
                params = []
                    
                # 复用 query_updates_paginated 的过滤逻辑
                if filters.get('vendor'):
                    where_clauses.append("vendor = ?")
                    params.append(filters['vendor'])
                    
                # source_channel过滤（blog 匹配所有 *-blog）
                if filters.get('source_channel'):
                    sc = filters['source_channel']
                    if sc == 'blog':
                        where_clauses.append("(source_channel LIKE '%blog%')")
                    else:
                        where_clauses.append("source_channel = ?")
                        params.append(sc)
                    
                if filters.get('update_type'):
                    where_clauses.append("update_type = ?")
                    params.append(filters['update_type'])
                    
                if filters.get('product_name'):
                    where_clauses.append("product_name LIKE ?")
                    params.append(f"%{filters['product_name']}%")
                    
                if filters.get('product_category'):
                    where_clauses.append("product_category = ?")
                    params.append(filters['product_category'])
                
                if filters.get('product_subcategory'):
                    where_clauses.append("product_subcategory = ?")
                    params.append(filters['product_subcategory'])
                    
                if filters.get('date_from'):
                    where_clauses.append("publish_date >= ?")
                    params.append(filters['date_from'])
                    
                if filters.get('date_to'):
                    where_clauses.append("publish_date <= ?")
                    params.append(filters['date_to'])
                    
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
                    
                if filters.get('keyword'):
                    where_clauses.append("(title LIKE ? OR content LIKE ?)")
                    keyword_param = f"%{filters['keyword']}%"
                    params.extend([keyword_param, keyword_param])
                    
                if filters.get('tags'):
                    tag_list = [t.strip() for t in filters['tags'].split(',')]
                    tag_conditions = []
                    for tag in tag_list:
                        tag_conditions.append("tags LIKE ?")
                        params.append(f'%"{tag}"%')
                    where_clauses.append(f"({' OR '.join(tag_conditions)})")
                    
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
                    
                cursor.execute(sql, params)
                result = cursor.fetchone()
                return result['count'] if result else 0
                    
        except Exception as e:
            self.logger.error(f"统计查询失败: {e}")
            return 0
        
    def get_vendor_statistics(
        self, 
        date_from: Optional[str] = None, 
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        按厂商统计
            
        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
                
        Returns:
            厂商统计列表,每项包含 vendor, count, analyzed
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                    
                where_clauses = []
                params = []
                    
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                    
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                    
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                    
                sql = f"""
                    SELECT 
                        vendor,
                        COUNT(*) as count,
                        SUM(CASE 
                            WHEN title_translated IS NOT NULL 
                                AND title_translated != '' 
                                AND LENGTH(TRIM(title_translated)) >= 2
                                AND title_translated NOT IN ('N/A', '暂无', 'None', 'null')
                            THEN 1 
                            ELSE 0 
                        END) as analyzed
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY vendor
                    ORDER BY count DESC
                """
                    
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"厂商统计查询失败: {e}")
            return []
        
    def get_analysis_coverage(self) -> float:
        """
        计算分析覆盖率（增强版）
            
        Returns:
            分析覆盖率（0.0 - 1.0）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                    
                cursor.execute("SELECT COUNT(*) as total FROM updates")
                total = cursor.fetchone()['total']
                    
                if total == 0:
                    return 0.0
                    
                # 增强has_analysis判定,排除无效值
                cursor.execute(
                    "SELECT COUNT(*) as analyzed FROM updates "
                    "WHERE title_translated IS NOT NULL "
                    "AND title_translated != '' "
                    "AND LENGTH(TRIM(title_translated)) >= 2 "
                    "AND title_translated NOT IN ('N/A', '暂无', 'None', 'null')"
                )
                analyzed = cursor.fetchone()['analyzed']
                    
                return round(analyzed / total, 4)
                    
        except Exception as e:
            self.logger.error(f"分析覆盖率计算失败: {e}")
            return 0.0
    
    def get_update_type_statistics(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Dict[str, int]:
        """
        按更新类型统计
        
        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
            vendor: 厂商过滤（可选）
            
        Returns:
            更新类型统计字典, key为类型名, value为数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["update_type IS NOT NULL", "update_type != ''"]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        update_type,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY update_type
                    ORDER BY count DESC
                """
                
                cursor.execute(sql, params)
                result = {}
                for row in cursor.fetchall():
                    result[row['update_type']] = row['count']
                return result
                
        except Exception as e:
            self.logger.error(f"更新类型统计查询失败: {e}")
            return {}
    
    # ==================== 批量任务管理方法 ====================
    
    def create_analysis_task(self, task_data: Dict[str, Any]) -> bool:
        """
        创建批量分析任务记录
        
        Args:
            task_data: 任务数据,包含:
                - task_id: 任务ID
                - task_name: 任务名称
                - task_status: 任务状态
                - vendor: 厂商(可选)
                - total_count: 总数量
                - started_at: 开始时间
                
        Returns:
            成功返回True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO analysis_tasks (
                            task_id, update_id, task_name, task_status,
                            task_result, started_at
                        ) VALUES (?, NULL, ?, ?, ?, ?)
                    ''', (
                        task_data['task_id'],
                        task_data.get('task_name', 'batch_analysis'),
                        task_data.get('task_status', 'queued'),
                        json.dumps({
                            'filters': task_data.get('filters', '{}'),  # 保存过滤条件
                            'vendor': task_data.get('vendor'),
                            'total_count': task_data.get('total_count', 0),
                            'completed_count': 0,
                            'success_count': 0,
                            'fail_count': 0
                        }),
                        task_data.get('started_at')
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"创建任务失败: {e}")
            return False
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        progress: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度信息(可选)
            error: 错误消息(可选)
            
        Returns:
            成功返回True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    update_fields = ['task_status = ?']
                    params = [status]
                    
                    if progress:
                        update_fields.append('task_result = ?')
                        params.append(json.dumps(progress))
                    
                    if error:
                        update_fields.append('error_message = ?')
                        params.append(error)
                    
                    if status in ['completed', 'failed']:
                        update_fields.append('completed_at = ?')
                        params.append(datetime.now().isoformat())
                    
                    params.append(task_id)
                    
                    sql = f"UPDATE analysis_tasks SET {', '.join(update_fields)} WHERE task_id = ?"
                    cursor.execute(sql, params)
                    conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
            return False
    
    def increment_task_progress(
        self, 
        task_id: str, 
        success: bool,
        error_msg: Optional[str] = None
    ) -> bool:
        """
        增加任务进度计数(线程安全)
        
        Args:
            task_id: 任务ID
            success: 是否成功
            error_msg: 错误消息(可选)
            
        Returns:
            成功返回True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 获取当前进度
                    cursor.execute(
                        'SELECT task_result, task_status FROM analysis_tasks WHERE task_id = ?',
                        (task_id,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    
                    result = json.loads(row['task_result'])
                    result['completed_count'] = result.get('completed_count', 0) + 1
                    
                    if success:
                        result['success_count'] = result.get('success_count', 0) + 1
                    else:
                        result['fail_count'] = result.get('fail_count', 0) + 1
                        if error_msg:
                            errors = result.get('errors', [])
                            errors.append(error_msg)
                            result['errors'] = errors[-100:]  # 保留最近100条错误
                    
                    # 判断是否完成
                    if result['completed_count'] >= result['total_count']:
                        status = 'completed'
                        completed_at = datetime.now().isoformat()
                        cursor.execute(
                            'UPDATE analysis_tasks SET task_status = ?, task_result = ?, completed_at = ? WHERE task_id = ?',
                            (status, json.dumps(result), completed_at, task_id)
                        )
                    else:
                        # 更新为running状态
                        current_status = row['task_status']
                        if current_status == 'queued':
                            cursor.execute(
                                'UPDATE analysis_tasks SET task_status = ?, task_result = ? WHERE task_id = ?',
                                ('running', json.dumps(result), task_id)
                            )
                        else:
                            cursor.execute(
                                'UPDATE analysis_tasks SET task_result = ? WHERE task_id = ?',
                                (json.dumps(result), task_id)
                            )
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {e}")
            return False
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        根据task_id获取任务记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务数据字典,不存在返回None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM analysis_tasks WHERE task_id = ?', (task_id,))
                
                row = cursor.fetchone()
                if row:
                    task = dict(row)
                    # 解析task_result JSON
                    if task.get('task_result'):
                        task['task_result'] = json.loads(task['task_result'])
                    return task
                return None
                
        except Exception as e:
            self.logger.error(f"获取任务记录失败: {e}")
            return None
    
    def list_tasks_paginated(
        self, 
        limit: int = 20, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        分页查询任务列表(按创建时间倒序)
        
        Args:
            limit: 每页数量
            offset: 偏移量
            status: 状态过滤（可选：queued/running/completed/failed）
            
        Returns:
            任务列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建SQL
                where_clauses = ["task_name = 'batch_analysis'"]
                params = []
                
                if status:
                    where_clauses.append("status = ?")
                    params.append(status)
                
                where_clause = " AND ".join(where_clauses)
                params.extend([limit, offset])
                
                cursor.execute(f'''
                    SELECT * FROM analysis_tasks
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', params)
                
                tasks = []
                for row in cursor.fetchall():
                    task = dict(row)
                    if task.get('task_result'):
                        task['task_result'] = json.loads(task['task_result'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            self.logger.error(f"查询任务列表失败: {e}")
            return []
    
    # ==================== 统计与元数据方法 ====================
    
    def get_timeline_statistics(
        self,
        granularity: str = "day",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取时间线统计数据
        
        Args:
            granularity: 粒度 (day/week/month)
            date_from: 开始日期
            date_to: 结束日期
            vendor: 厂商过滤
            
        Returns:
            时间线统计列表，每项包含 date, count, vendors
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 根据粒度确定日期格式
                if granularity == "month":
                    date_format = "%Y-%m"
                    date_expr = "strftime('%Y-%m', publish_date)"
                elif granularity == "week":
                    # SQLite 周统计：年-周号
                    date_format = "%Y-W%W"
                    date_expr = "strftime('%Y-W%W', publish_date)"
                else:  # day
                    date_format = "%Y-%m-%d"
                    date_expr = "DATE(publish_date)"
                
                where_clauses = ["publish_date IS NOT NULL"]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                # 按日期和厂商分组
                sql = f"""
                    SELECT 
                        {date_expr} as date,
                        vendor,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY {date_expr}, vendor
                    ORDER BY date DESC
                """
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                # 聚合结果：按日期分组，厂商统计合并
                date_stats = {}
                for row in rows:
                    date = row['date']
                    if date not in date_stats:
                        date_stats[date] = {'date': date, 'count': 0, 'vendors': {}}
                    date_stats[date]['count'] += row['count']
                    date_stats[date]['vendors'][row['vendor']] = row['count']
                
                # 转换为列表并按日期倒序
                result = list(date_stats.values())
                result.sort(key=lambda x: x['date'], reverse=True)
                
                return result
                
        except Exception as e:
            self.logger.error(f"时间线统计查询失败: {e}")
            return []
    
    def get_vendors_list(self) -> List[Dict[str, Any]]:
        """
        获取厂商列表及元数据
        
        Returns:
            厂商列表，每项包含 vendor, name, total_updates, source_channels
        """
        # 厂商名称映射
        vendor_names = {
            'aws': 'Amazon Web Services',
            'azure': 'Microsoft Azure',
            'gcp': 'Google Cloud Platform',
            'huawei': '华为云',
            'tencentcloud': '腾讯云',
            'volcengine': '火山引擎'
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 统计每个厂商的更新数和来源渠道
                sql = """
                    SELECT 
                        vendor,
                        COUNT(*) as total_updates,
                        GROUP_CONCAT(DISTINCT source_channel) as source_channels
                    FROM updates
                    GROUP BY vendor
                    ORDER BY total_updates DESC
                """
                
                cursor.execute(sql)
                results = []
                
                for row in cursor.fetchall():
                    vendor = row['vendor']
                    channels = row['source_channels'].split(',') if row['source_channels'] else []
                    results.append({
                        'vendor': vendor,
                        'name': vendor_names.get(vendor, vendor.title()),
                        'total_updates': row['total_updates'],
                        'source_channels': channels
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"厂商列表查询失败: {e}")
            return []
    
    def get_vendor_products(
        self,
        vendor: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定厂商的产品子类列表
        
        Args:
            vendor: 厂商标识
            
        Returns:
            产品子类列表，每项包含 product_subcategory, count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT 
                        product_subcategory,
                        COUNT(*) as count
                    FROM updates
                    WHERE vendor = ?
                        AND product_subcategory IS NOT NULL
                        AND product_subcategory != ''
                    GROUP BY product_subcategory
                    ORDER BY count DESC
                """
                
                cursor.execute(sql, (vendor,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'product_subcategory': row['product_subcategory'],
                        'count': row['count']
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"厂商产品列表查询失败: {e}")
            return []
    
    def get_available_years(self) -> List[int]:
        """
        获取数据库中有数据的年份列表
        
        Returns:
            年份列表，降序排列
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT DISTINCT strftime('%Y', publish_date) as year
                    FROM updates
                    WHERE publish_date IS NOT NULL
                    ORDER BY year DESC
                """
                
                cursor.execute(sql)
                
                return [int(row['year']) for row in cursor.fetchall() if row['year']]
                
        except Exception as e:
            self.logger.error(f"获取年份列表失败: {e}")
            return []

    def get_source_channel_statistics(self) -> List[Dict[str, Any]]:
        """
        获取来源类型统计
        
        Returns:
            来源类型统计列表，每项包含 value, count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT 
                        source_channel,
                        COUNT(*) as count
                    FROM updates
                    WHERE source_channel IS NOT NULL AND source_channel != ''
                    GROUP BY source_channel
                    ORDER BY count DESC
                """
                
                cursor.execute(sql)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'value': row['source_channel'],
                        'count': row['count']
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"来源类型统计失败: {e}")
            return []
