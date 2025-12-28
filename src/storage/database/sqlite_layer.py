#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一业务数据层 - UpdateDataLayer 门面类

通过组合模式整合所有 Repository，提供统一的 API 接口。
保持向后兼容，所有原有方法仍可正常使用。
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from src.storage.database.base import DatabaseManager, get_default_db_path
from src.storage.database.updates_repository import UpdatesRepository
from src.storage.database.analysis_repository import AnalysisRepository
from src.storage.database.tasks_repository import TasksRepository
from src.storage.database.stats_repository import StatsRepository
from src.storage.database.quality_repository import QualityRepository

logger = logging.getLogger(__name__)


class UpdateDataLayer:
    """
    统一业务数据层管理器（门面类）
    
    通过组合模式整合所有 Repository，提供统一的 API 接口：
    - UpdatesRepository: Updates 表 CRUD 操作
    - AnalysisRepository: 分析相关操作
    - TasksRepository: 批量任务管理
    - StatsRepository: 统计查询
    - QualityRepository: 质量问题追踪（新增）
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 UpdateDataLayer
        
        Args:
            db_path: 数据库文件路径，如果为 None 则使用默认路径
        """
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据库管理器（单例）
        self._db_manager = DatabaseManager(db_path)
        
        # 初始化所有 Repository
        self._updates = UpdatesRepository(self._db_manager)
        self._analysis = AnalysisRepository(self._db_manager)
        self._tasks = TasksRepository(self._db_manager)
        self._stats = StatsRepository(self._db_manager)
        self._quality = QualityRepository(self._db_manager)
    
    # ==================== 属性访问 ====================
    
    @property
    def db_path(self) -> str:
        """数据库路径"""
        return self._db_manager.db_path
    
    @property
    def lock(self):
        """线程锁"""
        return self._db_manager.lock
    
    @property
    def quality(self) -> QualityRepository:
        """质量问题追踪 Repository"""
        return self._quality
    
    # ==================== Updates CRUD ====================
    
    def insert_update(self, update_data: Dict[str, Any]) -> bool:
        """插入单条 Update 记录"""
        return self._updates.insert_update(update_data)
    
    def delete_update(self, update_id: str) -> bool:
        """删除单条 Update 记录"""
        return self._updates.delete_update(update_id)
    
    def batch_insert_updates(
        self, 
        updates_data: List[Dict[str, Any]], 
        force_update: bool = False
    ) -> Tuple[int, int]:
        """批量插入 Update 记录"""
        return self._updates.batch_insert_updates(updates_data, force_update)
    
    def check_update_exists(self, source_url: str, source_identifier: str = '') -> bool:
        """检查 Update 是否存在"""
        return self._updates.check_update_exists(source_url, source_identifier)
    
    def get_update_by_id(self, update_id: str) -> Optional[Dict[str, Any]]:
        """根据 update_id 获取 Update 记录"""
        return self._updates.get_update_by_id(update_id)
    
    def count_updates(self, **filters) -> int:
        """统计符合条件的 Update 数量"""
        return self._updates.count_updates(**filters)
    
    def query_updates_paginated(
        self,
        filters: Dict[str, Any],
        limit: int,
        offset: int,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """通用分页查询方法"""
        return self._updates.query_updates_paginated(filters, limit, offset, sort_by, order)
    
    def count_updates_with_filters(self, **filters) -> int:
        """扩展版统计方法"""
        return self._updates.count_updates_with_filters(**filters)
    
    # ==================== Analysis ====================
    
    def get_unanalyzed_updates(
        self, 
        limit: Optional[int] = None, 
        vendor: Optional[str] = None,
        source_channel: Optional[str] = None,
        include_analyzed: bool = False
    ) -> List[Dict[str, Any]]:
        """获取未分析的更新记录"""
        return self._analysis.get_unanalyzed_updates(limit, vendor, source_channel, include_analyzed)
    
    def count_unanalyzed_updates(
        self, 
        vendor: Optional[str] = None, 
        source_channel: Optional[str] = None,
        include_analyzed: bool = False
    ) -> int:
        """统计未分析的更新记录数量"""
        return self._analysis.count_unanalyzed_updates(vendor, source_channel, include_analyzed)
    
    def update_analysis_fields(
        self, 
        update_id: str, 
        fields: Dict[str, Any]
    ) -> bool:
        """更新分析字段"""
        return self._analysis.update_analysis_fields(update_id, fields)
    
    def get_analysis_coverage(self) -> float:
        """获取分析覆盖率"""
        return self._analysis.get_analysis_coverage()
    
    # ==================== Tasks ====================
    
    def create_analysis_task(self, task_data: Dict[str, Any]) -> bool:
        """创建批量分析任务记录"""
        return self._tasks.create_analysis_task(task_data)
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        progress: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """更新任务状态"""
        return self._tasks.update_task_status(task_id, status, progress, error)
    
    def increment_task_progress(
        self, 
        task_id: str, 
        success: bool,
        error_msg: Optional[str] = None
    ) -> bool:
        """增加任务进度计数"""
        return self._tasks.increment_task_progress(task_id, success, error_msg)
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据 task_id 获取任务记录"""
        return self._tasks.get_task_by_id(task_id)
    
    def list_tasks_paginated(
        self, 
        limit: int = 20, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """分页查询任务列表"""
        return self._tasks.list_tasks_paginated(limit, offset, status)
    
    # ==================== Stats ====================
    
    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        return self._stats.get_database_stats()
    
    def get_vendor_statistics(
        self, 
        date_from: Optional[str] = None, 
        date_to: Optional[str] = None,
        include_trend: bool = False
    ) -> List[Dict[str, Any]]:
        """按厂商统计"""
        return self._stats.get_vendor_statistics(date_from, date_to, include_trend)
    
    def get_update_type_statistics(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Dict[str, int]:
        """按更新类型统计"""
        return self._stats.get_update_type_statistics(date_from, date_to, vendor)
    
    def get_timeline_statistics(
        self,
        granularity: str = "day",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取时间线统计数据"""
        return self._stats.get_timeline_statistics(granularity, date_from, date_to, vendor)
    
    def get_vendors_list(self) -> List[Dict[str, Any]]:
        """获取厂商列表及元数据"""
        return self._stats.get_vendors_list()
    
    def get_vendor_products(self, vendor: str) -> List[Dict[str, Any]]:
        """获取指定厂商的产品子类列表"""
        return self._stats.get_vendor_products(vendor)
    
    def get_available_years(self) -> List[int]:
        """获取数据库中有数据的年份列表"""
        return self._stats.get_available_years()
    
    def get_source_channel_statistics(self) -> List[Dict[str, Any]]:
        """获取来源类型统计"""
        return self._stats.get_source_channel_statistics()
    
    def get_product_subcategory_statistics(
        self,
        vendor: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
        include_trend: bool = False
    ) -> List[Dict[str, Any]]:
        """获取产品子类热度统计"""
        return self._stats.get_product_subcategory_statistics(
            vendor, date_from, date_to, limit, include_trend
        )
    
    def get_vendor_update_type_matrix(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取厂商-更新类型交叉统计矩阵"""
        return self._stats.get_vendor_update_type_matrix(date_from, date_to)
    
    # ==================== Quality（新增）====================
    
    def insert_quality_issue(
        self,
        update_id: str,
        issue_type: str,
        auto_action: str,
        vendor: Optional[str] = None,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> bool:
        """插入质量问题记录"""
        return self._quality.insert_quality_issue(
            update_id, issue_type, auto_action,
            vendor, title, source_url, batch_id
        )
    
    def get_open_issues(
        self,
        issue_type: Optional[str] = None,
        vendor: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取待处理的质量问题"""
        return self._quality.get_open_issues(issue_type, vendor, batch_id, limit, offset)
    
    def count_open_issues(
        self,
        issue_type: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> int:
        """统计待处理的质量问题数量"""
        return self._quality.count_open_issues(issue_type, vendor)
    
    def get_issue_statistics(self) -> Dict[str, Any]:
        """获取质量问题统计"""
        return self._quality.get_issue_statistics()
        
    def check_cleaned_by_ai(
        self,
        source_url: str,
        issue_type: str = 'not_network_related'
    ) -> bool:
        """
        检查某条记录是否已被 AI 清洗过
        
        用于爬虫去重: 如果某条 URL 已被 AI 分析判定为非网络相关并删除,
        则不应再次爬取。
        
        Args:
            source_url: 源链接
            issue_type: 问题类型（默认 'not_network_related'）
            
        Returns:
            如果已被清洗返回 True，否则返回 False
        """
        return self._quality.check_cleaned_by_ai(source_url, issue_type)
        
    def get_cleaned_urls(
        self,
        issue_type: str = 'not_network_related',
        vendor: Optional[str] = None
    ) -> List[str]:
        """
        获取所有被 AI 清洗过的 source_url 列表
        
        用于批量查询优化，避免逐条检查。
        
        Args:
            issue_type: 问题类型
            vendor: 厂商过滤
                
        Returns:
            被清洗的 source_url 列表
        """
        return self._quality.get_cleaned_urls(issue_type, vendor)
    
    # ==================== 兼容性方法 ====================
    
    def _get_connection(self):
        """获取数据库连接（兼容旧代码）"""
        return self._db_manager.get_connection()
