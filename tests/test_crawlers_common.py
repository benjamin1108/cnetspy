#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试爬虫通用模块
"""

import pytest
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(autouse=True)
def reset_crawler_integration():
    """每个测试前重置 CrawlerIntegration 单例"""
    from src.crawlers.common.sync_decorator import CrawlerIntegration
    CrawlerIntegration._instance = None
    CrawlerIntegration._initialized = False
    yield


@pytest.fixture
def temp_db_path():
    """创建临时数据库"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    yield db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestCrawlerIntegration:
    """测试 CrawlerIntegration 类"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        instance1 = CrawlerIntegration()
        instance2 = CrawlerIntegration()
        
        assert instance1 is instance2
    
    def test_init(self):
        """测试初始化"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        integration = CrawlerIntegration()
        
        assert integration.enabled is True
        assert integration.data_layer is None
    
    def test_disable_enable(self):
        """测试禁用和启用"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        integration = CrawlerIntegration()
        
        integration.disable()
        assert integration.enabled is False
        
        # 启用时可能会尝试初始化数据层
        with patch.object(integration, 'initialize'):
            integration.enable()
            assert integration.enabled is True
    
    def test_create_update_data(self):
        """测试创建更新数据"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        integration = CrawlerIntegration()
        
        metadata = {
            "title": "Test Title",
            "description": "Test Description",
            "content": "Test Content",
            "publish_date": "2024-12-28",
            "source_url": "https://example.com/test",
            "source_identifier": "test-001"
        }
        
        result = integration._create_update_data(
            vendor="aws",
            source_type="blog",
            metadata_entry=metadata,
            url_key="https://example.com/test"
        )
        
        assert result["vendor"] == "aws"
        assert result["source_channel"] == "blog"
        assert result["title"] == "Test Title"
        assert result["content"] == "Test Content"
        assert "update_id" in result
    
    def test_sync_to_database_disabled(self):
        """测试禁用时同步"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        integration = CrawlerIntegration()
        integration.disable()
        
        result = integration.sync_to_database("aws", "blog", "url", {})
        assert result is False
    
    def test_batch_sync_to_database_disabled(self):
        """测试禁用时批量同步"""
        from src.crawlers.common.sync_decorator import CrawlerIntegration
        
        integration = CrawlerIntegration()
        integration.disable()
        
        result = integration.batch_sync_to_database("aws", "blog", {})
        assert result == {'success': 0, 'failed': 0, 'skipped': 0}


class TestSyncDecorator:
    """测试同步装饰器"""
    
    def test_decorator_calls_original_function(self):
        """测试装饰器调用原始函数"""
        from src.crawlers.common.sync_decorator import sync_to_database_decorator
        
        @sync_to_database_decorator
        def original_func(self):
            return "original_result"
        
        mock_self = MagicMock()
        mock_self.vendor = "aws"
        mock_self.source_type = "blog"
        mock_self._pending_sync_updates = {}
        
        result = original_func(mock_self)
        assert result == "original_result"
    
    def test_decorator_handles_exception(self):
        """测试装饰器异常处理"""
        from src.crawlers.common.sync_decorator import sync_to_database_decorator
        
        @sync_to_database_decorator
        def original_func(self):
            return "result"
        
        mock_self = MagicMock()
        mock_self.vendor = "aws"
        mock_self.source_type = "blog"
        mock_self._pending_sync_updates = {"url": {"title": "test"}}
        
        # 即使同步失败，也应该返回原始结果
        result = original_func(mock_self)
        assert result == "result"


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_get_crawler_integration(self):
        """测试获取全局实例"""
        from src.crawlers.common.sync_decorator import get_crawler_integration
        
        integration = get_crawler_integration()
        assert integration is not None
    
    def test_enable_disable_database_sync(self):
        """测试启用/禁用便捷函数"""
        from src.crawlers.common.sync_decorator import (
            enable_database_sync,
            disable_database_sync,
            get_crawler_integration
        )
        
        disable_database_sync()
        assert get_crawler_integration().enabled is False
        
        with patch.object(get_crawler_integration(), 'initialize'):
            enable_database_sync()
            assert get_crawler_integration().enabled is True
    
    def test_sync_crawler_data(self):
        """测试手动同步函数"""
        from src.crawlers.common.sync_decorator import sync_crawler_data, get_crawler_integration
        
        # 禁用以避免实际数据库操作
        get_crawler_integration().disable()
        
        result = sync_crawler_data("aws", "blog", {})
        assert "success" in result
        assert "failed" in result
        assert "skipped" in result


class TestCrawlerManagerImport:
    """测试爬虫管理器导入"""
    
    def test_crawler_manager_import(self):
        """测试 CrawlerManager 可以导入"""
        from src.crawlers.common.crawler_manager import CrawlerManager
        assert CrawlerManager is not None
    
    def test_base_crawler_import(self):
        """测试 BaseCrawler 可以导入"""
        from src.crawlers.common.base_crawler import BaseCrawler
        assert BaseCrawler is not None
        
        # 检查必要的方法存在
        assert hasattr(BaseCrawler, 'run')
        assert hasattr(BaseCrawler, '_crawl')
        assert hasattr(BaseCrawler, 'save_update')


class TestVendorCrawlersImport:
    """测试厂商爬虫导入"""
    
    def test_aws_whatsnew_crawler_import(self):
        """测试 AWS WhatsnewCrawler 导入"""
        from src.crawlers.vendors.aws.whatsnew_crawler import AwsWhatsnewCrawler
        assert AwsWhatsnewCrawler is not None
    
    def test_aws_network_blog_crawler_import(self):
        """测试 AWS NetworkBlogCrawler 导入"""
        from src.crawlers.vendors.aws.network_blog_crawler import AwsNetworkBlogCrawler
        assert AwsNetworkBlogCrawler is not None
    
    def test_azure_crawlers_import(self):
        """测试 Azure 爬虫导入"""
        from src.crawlers.vendors.azure.whatsnew_crawler import AzureWhatsnewCrawler
        from src.crawlers.vendors.azure.network_blog_crawler import AzureNetworkBlogCrawler
        assert AzureWhatsnewCrawler is not None
        assert AzureNetworkBlogCrawler is not None
    
    def test_gcp_crawlers_import(self):
        """测试 GCP 爬虫导入"""
        from src.crawlers.vendors.gcp.whatsnew_crawler import GcpWhatsnewCrawler
        from src.crawlers.vendors.gcp.network_blog_crawler import GcpNetworkBlogCrawler
        assert GcpWhatsnewCrawler is not None
        assert GcpNetworkBlogCrawler is not None
    
    def test_huawei_crawler_import(self):
        """测试 Huawei 爬虫导入"""
        from src.crawlers.vendors.huawei.whatsnew_crawler import HuaweiWhatsnewCrawler
        assert HuaweiWhatsnewCrawler is not None
    
    def test_tencentcloud_crawler_import(self):
        """测试 TencentCloud 爬虫导入"""
        from src.crawlers.vendors.tencentcloud.whatsnew_crawler import TencentcloudWhatsnewCrawler
        assert TencentcloudWhatsnewCrawler is not None
    
    def test_volcengine_crawler_import(self):
        """测试 Volcengine 爬虫导入"""
        from src.crawlers.vendors.volcengine.whatsnew_crawler import VolcengineWhatsnewCrawler
        assert VolcengineWhatsnewCrawler is not None
