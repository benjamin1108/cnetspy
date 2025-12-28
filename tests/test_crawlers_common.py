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


class TestCrawlReport:
    """测试 CrawlReport 数据类"""
    
    def test_crawl_report_init(self):
        """测试 CrawlReport 初始化"""
        from src.crawlers.common.base_crawler import CrawlReport
        
        report = CrawlReport(vendor='aws', source_type='whatsnew')
        
        assert report.vendor == 'aws'
        assert report.source_type == 'whatsnew'
        assert report.total_discovered == 0
        assert report.new_saved == 0
        assert report.skipped_exists == 0
        assert report.skipped_ai_cleaned == 0
        assert report.failed == 0
        assert report.ai_cleaned_urls == []
    
    def test_add_skipped_ai_cleaned(self):
        """测试添加AI清洗跳过记录"""
        from src.crawlers.common.base_crawler import CrawlReport
        
        report = CrawlReport()
        
        report.add_skipped_ai_cleaned('https://example.com/1', 'Test Title 1')
        report.add_skipped_ai_cleaned('https://example.com/2', 'Test Title 2')
        
        assert report.skipped_ai_cleaned == 2
        assert len(report.ai_cleaned_urls) == 2
        # 存储的是标题截断格式
        assert 'Test Title 1' in report.ai_cleaned_urls[0]
        assert 'Test Title 2' in report.ai_cleaned_urls[1]
    
    def test_add_skipped_ai_cleaned_empty_title(self):
        """测试空标题情况"""
        from src.crawlers.common.base_crawler import CrawlReport
        
        report = CrawlReport()
        report.add_skipped_ai_cleaned('https://example.com/1', '')
        
        assert report.skipped_ai_cleaned == 1
        # 空标题时存储URL
        assert report.ai_cleaned_urls[0] == 'https://example.com/1'
    
    def test_print_report_no_error(self):
        """测试打印报告不报错"""
        from src.crawlers.common.base_crawler import CrawlReport
        
        report = CrawlReport(vendor='aws', source_type='blog')
        report.total_discovered = 10
        report.new_saved = 5
        report.skipped_exists = 3
        report.skipped_ai_cleaned = 2
        
        # 不应报错
        report.print_report()
    
    def test_print_report_with_ai_cleaned_urls(self):
        """测试打印包含AI清洗URL的报告"""
        from src.crawlers.common.base_crawler import CrawlReport
        
        report = CrawlReport(vendor='azure', source_type='whatsnew')
        report.add_skipped_ai_cleaned('https://example.com/1', 'Title 1')
        report.add_skipped_ai_cleaned('https://example.com/2', 'Title 2')
        
        # 不应报错
        report.print_report()


class TestShouldSkipUpdate:
    """测试 should_skip_update 统一去重方法"""
    
    @pytest.fixture
    def mock_crawler(self):
        """创建模拟爬虫实例"""
        from src.crawlers.common.base_crawler import BaseCrawler, CrawlReport
        from typing import List
        
        # Mock 配置
        mock_config = MagicMock()
        mock_config.get.return_value = {}
        
        # 创建 BaseCrawler 子类实例 - 实现所有抽象方法
        class TestCrawler(BaseCrawler):
            def _crawl(self, force_mode=False):
                return []
            
            def _get_identifier_strategy(self) -> str:
                return 'url_based'
            
            def _get_identifier_components(self, update) -> List[str]:
                return [update.get('source_url', '')]
        
        crawler = TestCrawler(mock_config, 'test', 'whatsnew')
        crawler._crawl_report = CrawlReport(vendor='test', source_type='whatsnew')
        
        # Mock data_layer (使用私有属性)
        crawler._data_layer = MagicMock()
        
        return crawler
    
    def test_pattern1_source_url_exists(self, mock_crawler):
        """测试 Pattern 1: 数据库已存在"""
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        should_skip, reason = mock_crawler.should_skip_update(
            source_url='https://example.com/test',
            source_identifier='abc123',
            title='Test Title'
        )
        
        assert should_skip is True
        assert reason == 'exists'
        assert mock_crawler._crawl_report.skipped_exists == 1
    
    def test_pattern1_ai_cleaned(self, mock_crawler):
        """测试 Pattern 1: 已被AI清洗"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = True
        
        should_skip, reason = mock_crawler.should_skip_update(
            source_url='https://example.com/test',
            source_identifier='abc123',
            title='Test Title'
        )
        
        assert should_skip is True
        assert reason == 'ai_cleaned'
        assert mock_crawler._crawl_report.skipped_ai_cleaned == 1
        assert len(mock_crawler._crawl_report.ai_cleaned_urls) == 1
    
    def test_pattern1_new_update(self, mock_crawler):
        """测试 Pattern 1: 新更新不跳过"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        should_skip, reason = mock_crawler.should_skip_update(
            source_url='https://example.com/test',
            source_identifier='abc123',
            title='Test Title'
        )
        
        assert should_skip is False
        assert reason == ''
        assert mock_crawler._crawl_report.skipped_exists == 0
        assert mock_crawler._crawl_report.skipped_ai_cleaned == 0
    
    def test_pattern2_update_dict_exists(self, mock_crawler):
        """测试 Pattern 2: 传入update字典，数据库已存在"""
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        update = {
            'source_url': 'https://example.com/test',
            'source_identifier': 'abc123',
            'title': 'Test Title'
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        assert should_skip is True
        assert reason == 'exists'
    
    def test_pattern2_update_dict_ai_cleaned(self, mock_crawler):
        """测试 Pattern 2: 传入update字典，已被AI清洗"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = True
        
        update = {
            'source_url': 'https://example.com/test',
            'title': 'Test Title'
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        assert should_skip is True
        assert reason == 'ai_cleaned'
    
    def test_pattern2_update_dict_new(self, mock_crawler):
        """测试 Pattern 2: 传入update字典，新更新"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        update = {
            'source_url': 'https://example.com/test',
            'title': 'New Update'
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        assert should_skip is False
        assert reason == ''
    
    def test_empty_source_url_returns_false(self, mock_crawler):
        """测试空source_url返回不跳过"""
        should_skip, reason = mock_crawler.should_skip_update(
            source_url='',
            source_identifier='abc123'
        )
        
        assert should_skip is False
        assert reason == ''
    
    def test_none_source_url_returns_false(self, mock_crawler):
        """测试None source_url返回不跳过"""
        should_skip, reason = mock_crawler.should_skip_update(
            source_url=None,
            source_identifier='abc123'
        )
        
        assert should_skip is False
        assert reason == ''
    
    def test_update_dict_empty_source_url(self, mock_crawler):
        """测试update字典中source_url为空"""
        update = {
            'source_url': '',
            'title': 'Test'
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        assert should_skip is False
        assert reason == ''
    
    def test_update_dict_no_source_url(self, mock_crawler):
        """测试update字典缺少source_url字段"""
        update = {
            'title': 'Test'
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        assert should_skip is False
        assert reason == ''
    
    def test_update_dict_generates_source_identifier(self, mock_crawler):
        """测试update字典模式自动生成source_identifier"""
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        update = {
            'source_url': 'https://example.com/test',
            'title': 'Test'
            # 没有source_identifier，应该自动生成
        }
        
        should_skip, reason = mock_crawler.should_skip_update(update=update)
        
        # 确认check_update_exists被调用了
        mock_crawler._data_layer.check_update_exists.assert_called()
        # 检查传入的source_identifier不为空
        call_args = mock_crawler._data_layer.check_update_exists.call_args
        assert call_args[0][1] != ''  # source_identifier应该被生成
    
    def test_check_order_exists_before_ai_cleaned(self, mock_crawler):
        """测试检查顺序：先检查数据库存在，再检查AI清洗"""
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = True
        
        should_skip, reason = mock_crawler.should_skip_update(
            source_url='https://example.com/test',
            source_identifier='abc123'
        )
        
        # 应该先返回 exists，不应该调用 check_cleaned_by_ai
        assert should_skip is True
        assert reason == 'exists'
        mock_crawler._data_layer.check_cleaned_by_ai.assert_not_called()
    
    def test_multiple_calls_accumulate_stats(self, mock_crawler):
        """测试多次调用累计统计"""
        # 第一次: 已存在
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        mock_crawler.should_skip_update(source_url='https://1.com', source_identifier='1')
        
        # 第二次: AI清洗
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = True
        mock_crawler.should_skip_update(source_url='https://2.com', source_identifier='2')
        
        # 第三次: 新更新
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        mock_crawler.should_skip_update(source_url='https://3.com', source_identifier='3')
        
        assert mock_crawler._crawl_report.skipped_exists == 1
        assert mock_crawler._crawl_report.skipped_ai_cleaned == 1


class TestShouldCrawl:
    """测试 should_crawl 方法"""
    
    @pytest.fixture
    def mock_crawler(self):
        """创建模拟爬虫实例"""
        from src.crawlers.common.base_crawler import BaseCrawler, CrawlReport
        from typing import List
        
        mock_config = MagicMock()
        mock_config.get.return_value = {}
        
        class TestCrawler(BaseCrawler):
            def _crawl(self, force_mode=False):
                return []
            
            def _get_identifier_strategy(self) -> str:
                return 'url_based'
            
            def _get_identifier_components(self, update) -> List[str]:
                return [update.get('source_url', '')]
        
        crawler = TestCrawler(mock_config, 'test', 'blog')
        crawler._crawl_report = CrawlReport(vendor='test', source_type='blog')
        crawler._data_layer = MagicMock()
        
        return crawler
    
    def test_should_crawl_returns_true_for_new(self, mock_crawler):
        """测试新更新返回True"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        result = mock_crawler.should_crawl('https://example.com/new')
        
        assert result is True
    
    def test_should_crawl_returns_false_for_exists(self, mock_crawler):
        """测试已存在返回False"""
        mock_crawler._data_layer.check_update_exists.return_value = True
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = False
        
        result = mock_crawler.should_crawl('https://example.com/exists')
        
        assert result is False
    
    def test_should_crawl_returns_false_for_ai_cleaned(self, mock_crawler):
        """测试AI清洗返回False"""
        mock_crawler._data_layer.check_update_exists.return_value = False
        mock_crawler._data_layer.check_cleaned_by_ai.return_value = True
        
        result = mock_crawler.should_crawl('https://example.com/cleaned', title='Cleaned Title')
        
        assert result is False
        assert mock_crawler._crawl_report.skipped_ai_cleaned == 1


class TestSetTotalDiscovered:
    """测试 set_total_discovered 方法"""
    
    def test_set_total_discovered(self):
        """测试设置发现总数"""
        from src.crawlers.common.base_crawler import BaseCrawler, CrawlReport
        from typing import List
        
        mock_config = MagicMock()
        mock_config.get.return_value = {}
        
        class TestCrawler(BaseCrawler):
            def _crawl(self, force_mode=False):
                return []
            
            def _get_identifier_strategy(self) -> str:
                return 'url_based'
            
            def _get_identifier_components(self, update) -> List[str]:
                return [update.get('source_url', '')]
        
        crawler = TestCrawler(mock_config, 'test', 'whatsnew')
        crawler._crawl_report = CrawlReport()
        
        crawler.set_total_discovered(100)
        
        assert crawler._crawl_report.total_discovered == 100
    
    def test_set_total_discovered_accumulates(self):
        """测试多次设置(不累加，而是覆盖)"""
        from src.crawlers.common.base_crawler import BaseCrawler, CrawlReport
        from typing import List
        
        mock_config = MagicMock()
        mock_config.get.return_value = {}
        
        class TestCrawler(BaseCrawler):
            def _crawl(self, force_mode=False):
                return []
            
            def _get_identifier_strategy(self) -> str:
                return 'url_based'
            
            def _get_identifier_components(self, update) -> List[str]:
                return [update.get('source_url', '')]
        
        crawler = TestCrawler(mock_config, 'test', 'whatsnew')
        crawler._crawl_report = CrawlReport()
        
        crawler.set_total_discovered(50)
        crawler.set_total_discovered(30)
        
        # set_total_discovered 是设置，不是累加
        assert crawler._crawl_report.total_discovered == 30
