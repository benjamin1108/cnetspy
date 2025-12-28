#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试数据模型
"""

import pytest
from datetime import datetime

from src.models.update import (
    SourceChannel,
    UpdateType,
    CrawlerUpdate
)


class TestSourceChannel:
    """测试 SourceChannel 枚举"""
    
    def test_blog_value(self):
        """测试博客类型"""
        assert SourceChannel.BLOG.value == 'blog'
    
    def test_whatsnew_value(self):
        """测试 whatsnew 类型"""
        assert SourceChannel.WHATSNEW.value == 'whatsnew'
    
    def test_is_string_enum(self):
        """测试是字符串枚举"""
        assert isinstance(SourceChannel.BLOG, str)
        assert SourceChannel.BLOG == 'blog'


class TestUpdateType:
    """测试 UpdateType 枚举"""
    
    def test_all_types_exist(self):
        """测试所有类型存在"""
        expected_types = [
            'new_product', 'new_feature', 'enhancement', 'deprecation',
            'pricing', 'region', 'security', 'fix', 'performance',
            'compliance', 'integration', 'other'
        ]
        
        for update_type in expected_types:
            assert update_type in UpdateType.values()
    
    def test_values_method(self):
        """测试 values() 方法"""
        values = UpdateType.values()
        
        assert isinstance(values, list)
        assert len(values) > 0
        assert 'new_feature' in values
    
    def test_is_valid_true(self):
        """测试有效值检查 - 有效"""
        assert UpdateType.is_valid('new_feature') is True
        assert UpdateType.is_valid('enhancement') is True
        assert UpdateType.is_valid('other') is True
    
    def test_is_valid_false(self):
        """测试有效值检查 - 无效"""
        assert UpdateType.is_valid('invalid_type') is False
        assert UpdateType.is_valid('') is False
        assert UpdateType.is_valid('NEW_FEATURE') is False  # 大写无效
    
    def test_is_string_enum(self):
        """测试是字符串枚举"""
        assert isinstance(UpdateType.NEW_FEATURE, str)
        assert UpdateType.NEW_FEATURE == 'new_feature'


class TestCrawlerUpdate:
    """测试 CrawlerUpdate 数据类"""
    
    def test_create_with_required_fields(self):
        """测试使用必填字段创建"""
        update = CrawlerUpdate(
            title="Test Update",
            source_url="https://example.com/update",
            publish_date="2024-12-28",
            source_identifier="abc123456789"
        )
        
        assert update.title == "Test Update"
        assert update.source_url == "https://example.com/update"
        assert update.publish_date == "2024-12-28"
        assert update.source_identifier == "abc123456789"
    
    def test_optional_fields_default(self):
        """测试可选字段默认值"""
        update = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier="abc123"
        )
        
        assert update.description == ''
        assert update.content == ''
        assert update.product_name == ''
        assert update.vendor == ''
        assert update.source_type == ''
        assert update.update_type == ''
        assert update.doc_links == []
        assert update.extra == {}
    
    def test_crawl_time_auto_generated(self):
        """测试爬取时间自动生成"""
        update = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier="abc123"
        )
        
        assert update.crawl_time is not None
        assert 'T' in update.crawl_time  # ISO 格式
    
    def test_to_dict(self):
        """测试转换为字典"""
        update = CrawlerUpdate(
            title="Test Update",
            source_url="https://example.com/update",
            publish_date="2024-12-28",
            source_identifier="abc123",
            vendor="aws",
            content="Test content"
        )
        
        result = update.to_dict()
        
        assert isinstance(result, dict)
        assert result['title'] == "Test Update"
        assert result['source_url'] == "https://example.com/update"
        assert result['vendor'] == "aws"
        assert result['content'] == "Test content"
        assert 'crawl_time' in result
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'title': 'Test Update',
            'source_url': 'https://example.com',
            'publish_date': '2024-12-28',
            'source_identifier': 'abc123',
            'vendor': 'azure',
            'content': 'Some content',
            'doc_links': [{'text': 'Docs', 'url': 'https://docs.example.com'}]
        }
        
        update = CrawlerUpdate.from_dict(data)
        
        assert update.title == 'Test Update'
        assert update.vendor == 'azure'
        assert update.content == 'Some content'
        assert len(update.doc_links) == 1
    
    def test_from_dict_missing_fields(self):
        """测试从不完整字典创建"""
        data = {
            'title': 'Test',
            'source_url': 'https://example.com'
        }
        
        update = CrawlerUpdate.from_dict(data)
        
        assert update.title == 'Test'
        assert update.publish_date == ''
        assert update.source_identifier == ''
    
    def test_is_valid_true(self):
        """测试有效性验证 - 有效"""
        update = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier="abc123"
        )
        
        assert update.is_valid() is True
    
    def test_is_valid_false_missing_title(self):
        """测试有效性验证 - 缺少标题"""
        update = CrawlerUpdate(
            title="",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier="abc123"
        )
        
        assert update.is_valid() is False
    
    def test_is_valid_false_missing_url(self):
        """测试有效性验证 - 缺少 URL"""
        update = CrawlerUpdate(
            title="Test",
            source_url="",
            publish_date="2024-12-28",
            source_identifier="abc123"
        )
        
        assert update.is_valid() is False
    
    def test_is_valid_false_missing_date(self):
        """测试有效性验证 - 缺少日期"""
        update = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="",
            source_identifier="abc123"
        )
        
        assert update.is_valid() is False
    
    def test_is_valid_false_missing_identifier(self):
        """测试有效性验证 - 缺少标识符"""
        update = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier=""
        )
        
        assert update.is_valid() is False
    
    def test_roundtrip_dict_conversion(self):
        """测试字典转换往返"""
        original = CrawlerUpdate(
            title="Test",
            source_url="https://example.com",
            publish_date="2024-12-28",
            source_identifier="abc123",
            vendor="gcp",
            content="Content",
            doc_links=[{"text": "Link", "url": "https://link.com"}],
            extra={"key": "value"}
        )
        
        # 转换为字典再转回来
        data = original.to_dict()
        restored = CrawlerUpdate.from_dict(data)
        
        assert restored.title == original.title
        assert restored.vendor == original.vendor
        assert restored.doc_links == original.doc_links
        assert restored.extra == original.extra
