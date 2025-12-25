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
                    update_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    task_status TEXT NOT NULL,
                    task_result TEXT,
                    error_message TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (update_id) REFERENCES updates(update_id) ON DELETE CASCADE
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
