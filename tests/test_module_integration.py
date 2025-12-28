#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模块导入和集成测试

测试覆盖：
- 所有核心模块可正常导入
- 数据库层门面类完整性
- 爬虫模块可用性
- API模块可用性
"""

import pytest


class TestModuleImports:
    """模块导入测试"""
    
    def test_import_database_modules(self):
        """测试数据库模块导入"""
        from src.storage.database import (
            UpdateDataLayer,
            DatabaseManager,
            BaseRepository,
            UpdatesRepository,
            AnalysisRepository,
            TasksRepository,
            StatsRepository,
            QualityRepository
        )
        
        assert UpdateDataLayer is not None
        assert DatabaseManager is not None
        assert BaseRepository is not None
        assert UpdatesRepository is not None
        assert AnalysisRepository is not None
        assert TasksRepository is not None
        assert StatsRepository is not None
        assert QualityRepository is not None
    
    def test_import_storage_modules(self):
        """测试存储模块导入"""
        from src.storage import UpdateDataLayer
        from src.storage.file_storage import FileStorage
        
        assert UpdateDataLayer is not None
        assert FileStorage is not None
    
    def test_import_analyzer_modules(self):
        """测试分析器模块导入"""
        from src.analyzers import UpdateAnalyzer
        from src.analyzers.analysis_executor import AnalysisExecutor
        from src.analyzers.gemini_client import GeminiClient
        
        assert UpdateAnalyzer is not None
        assert AnalysisExecutor is not None
        assert GeminiClient is not None
    
    def test_import_crawler_modules(self):
        """测试爬虫模块导入"""
        from src.crawlers.common.base_crawler import BaseCrawler
        from src.crawlers.common.crawler_manager import CrawlerManager
        
        assert BaseCrawler is not None
        assert CrawlerManager is not None
    
    def test_import_api_modules(self):
        """测试API模块导入"""
        from src.api.app import app
        from src.api.routes import updates, stats, analysis
        
        assert app is not None
        assert updates is not None
        assert stats is not None
        assert analysis is not None
    
    def test_import_utils(self):
        """测试工具模块导入"""
        from src.utils.config.config_loader import get_config
        from src.utils.logging.colored_logger import setup_colored_logging
        
        assert get_config is not None
        assert setup_colored_logging is not None


class TestDataLayerIntegrity:
    """数据层完整性测试"""
    
    def test_facade_has_all_methods(self, data_layer):
        """测试门面类包含所有方法"""
        # Updates CRUD
        assert hasattr(data_layer, 'insert_update')
        assert hasattr(data_layer, 'delete_update')
        assert hasattr(data_layer, 'batch_insert_updates')
        assert hasattr(data_layer, 'check_update_exists')
        assert hasattr(data_layer, 'get_update_by_id')
        assert hasattr(data_layer, 'count_updates')
        assert hasattr(data_layer, 'query_updates_paginated')
        
        # Analysis
        assert hasattr(data_layer, 'get_unanalyzed_updates')
        assert hasattr(data_layer, 'count_unanalyzed_updates')
        assert hasattr(data_layer, 'update_analysis_fields')
        assert hasattr(data_layer, 'get_analysis_coverage')
        
        # Tasks
        assert hasattr(data_layer, 'create_analysis_task')
        assert hasattr(data_layer, 'update_task_status')
        assert hasattr(data_layer, 'increment_task_progress')
        assert hasattr(data_layer, 'get_task_by_id')
        assert hasattr(data_layer, 'list_tasks_paginated')
        
        # Stats
        assert hasattr(data_layer, 'get_database_stats')
        assert hasattr(data_layer, 'get_vendor_statistics')
        assert hasattr(data_layer, 'get_update_type_statistics')
        assert hasattr(data_layer, 'get_timeline_statistics')
        assert hasattr(data_layer, 'get_vendors_list')
        assert hasattr(data_layer, 'get_vendor_products')
        assert hasattr(data_layer, 'get_available_years')
        
        # Quality
        assert hasattr(data_layer, 'insert_quality_issue')
        assert hasattr(data_layer, 'get_open_issues')
        assert hasattr(data_layer, 'count_open_issues')
        assert hasattr(data_layer, 'get_issue_statistics')
    
    def test_repository_access(self, data_layer):
        """测试可以访问底层 Repository"""
        assert data_layer._updates is not None
        assert data_layer._analysis is not None
        assert data_layer._tasks is not None
        assert data_layer._stats is not None
        assert data_layer._quality is not None
    
    def test_shared_database_manager(self, data_layer):
        """测试所有 Repository 共享同一个数据库管理器"""
        db_manager = data_layer._db_manager
        
        assert data_layer._updates._db_manager is db_manager
        assert data_layer._analysis._db_manager is db_manager
        assert data_layer._tasks._db_manager is db_manager
        assert data_layer._stats._db_manager is db_manager
        assert data_layer._quality._db_manager is db_manager


class TestCrawlerModules:
    """爬虫模块测试"""
    
    def test_crawler_manager_import(self):
        """测试爬虫管理器导入"""
        from src.crawlers.common.crawler_manager import CrawlerManager
        
        # CrawlerManager 需要 config 参数
        assert CrawlerManager is not None
        assert hasattr(CrawlerManager, 'run')
        assert hasattr(CrawlerManager, 'run_crawler')
    
    def test_crawler_manager_instantiation(self):
        """测试爬虫管理器实例化"""
        from src.crawlers.common.crawler_manager import CrawlerManager
        
        # 使用最小配置创建实例
        config = {
            'sources': {
                'aws': {
                    'whatsnew': {'enabled': True}
                }
            },
            'crawler': {'max_workers': 1}
        }
        manager = CrawlerManager(config)
        
        assert manager is not None
        assert manager.sources is not None
    
    def test_base_crawler_interface(self):
        """测试爬虫基类接口"""
        from src.crawlers.common.base_crawler import BaseCrawler
        
        # 验证基类有必要的方法
        assert hasattr(BaseCrawler, 'run')  # 公共入口方法
        assert hasattr(BaseCrawler, '_crawl')  # 内部实现方法
        assert hasattr(BaseCrawler, 'save_update')  # 保存更新
