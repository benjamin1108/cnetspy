#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库基础层 - 连接管理与表初始化

提供数据库连接管理、表结构初始化等基础功能。
"""

import os
import sqlite3
import logging
import threading
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_default_db_path() -> str:
    """
    获取默认数据库路径
    
    Returns:
        数据库文件路径: data/sqlite/updates.db
    """
    # __file__ = src/storage/database/base.py
    # 需要往上走4级才能到项目根目录
    base_dir = os.path.abspath(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    return os.path.join(base_dir, 'data', 'sqlite', 'updates.db')


class DatabaseManager:
    """
    数据库连接管理器（单例模式）
    
    负责：
    - 管理数据库连接
    - 初始化表结构
    - 提供线程安全的连接获取
    """
    
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Optional[str] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path or get_default_db_path()
        self.lock = threading.RLock()
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        self._initialized = True
    
    def _init_database(self):
        """初始化数据库表结构和索引"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ==================== updates 表 ====================
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
                    content_translated TEXT,
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
            
            # updates 索引
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_updates_unique_source 
                ON updates(source_url, source_identifier)
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_vendor ON updates(vendor)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_type ON updates(update_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_publish_date ON updates(publish_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_product_name ON updates(product_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_product_category ON updates(product_category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_priority ON updates(priority)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_source_url ON updates(source_url)')
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
            
            # ==================== analysis_tasks 表 ====================
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
            
            # analysis_tasks 索引
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
            
            # ==================== quality_issues 表（新增）====================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_id TEXT NOT NULL,
                    vendor TEXT,
                    title TEXT,
                    source_url TEXT,
                    issue_type TEXT NOT NULL,
                    auto_action TEXT NOT NULL,
                    batch_id TEXT,
                    detected_at TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    resolved_at TEXT,
                    resolution TEXT
                )
            ''')
            
            # quality_issues 索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_quality_issues_update_id 
                ON quality_issues(update_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_quality_issues_type_status 
                ON quality_issues(issue_type, status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_quality_issues_batch 
                ON quality_issues(batch_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_quality_issues_vendor 
                ON quality_issues(vendor)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_quality_issues_auto_action 
                ON quality_issues(auto_action, status)
            ''')
            
            # ==================== migration_history 表 ====================
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
            
            # migration_history 索引
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
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
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
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（仅用于测试）"""
        with cls._lock:
            cls._instance = None


class BaseRepository:
    """
    Repository 基类
    
    提供数据库访问的基础能力，所有 Repository 继承此类。
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化 Repository
        
        Args:
            db_manager: 数据库管理器实例，如果不提供则使用单例
        """
        self._db_manager = db_manager or DatabaseManager()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    def db_path(self) -> str:
        """数据库路径"""
        return self._db_manager.db_path
    
    @property
    def lock(self) -> threading.RLock:
        """线程锁"""
        return self._db_manager.lock
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        with self._db_manager.get_connection() as conn:
            yield conn
