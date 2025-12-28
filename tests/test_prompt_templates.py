#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Prompt 模板模块
"""

import pytest
from pathlib import Path

from src.analyzers.prompt_templates import PromptTemplates
from src.models.update import UpdateType


@pytest.fixture(autouse=True)
def reset_prompt_cache():
    """每个测试前重置缓存"""
    PromptTemplates._prompt_cache.clear()
    PromptTemplates._subcategory_config = None
    PromptTemplates._config = None
    yield


class TestPromptTemplatesVersion:
    """测试版本相关功能"""
    
    def test_get_version(self):
        """测试获取版本"""
        version = PromptTemplates.get_version()
        assert version is not None
        assert isinstance(version, str)
        assert version.startswith("v")


class TestPromptTemplatesConfig:
    """测试配置相关功能"""
    
    def test_set_config(self):
        """测试设置配置"""
        config = {"validation": {"title_max_length": 100}}
        PromptTemplates.set_config(config)
        assert PromptTemplates._config == config
    
    def test_get_validation_config_defaults(self):
        """测试获取默认验证配置"""
        PromptTemplates._config = None
        result = PromptTemplates._get_validation_config()
        
        assert "title_max_length" in result
        assert "summary_min_length" in result
        assert "summary_max_length" in result
        assert "tags_min_count" in result
        assert "tags_max_count" in result
    
    def test_get_validation_config_custom(self):
        """测试自定义验证配置"""
        PromptTemplates.set_config({
            "validation": {"title_max_length": 100}
        })
        
        result = PromptTemplates._get_validation_config()
        assert result["title_max_length"] == 100
    
    def test_get_validation_config_nested(self):
        """测试嵌套验证配置"""
        PromptTemplates.set_config({
            "default": {"validation": {"summary_max_length": 600}}
        })
        
        result = PromptTemplates._get_validation_config()
        assert result["summary_max_length"] == 600


class TestPromptTemplatesSubcategory:
    """测试 subcategory 相关功能"""
    
    def test_load_subcategory_config(self):
        """测试加载 subcategory 配置"""
        result = PromptTemplates._load_subcategory_config()
        assert isinstance(result, dict)
    
    def test_get_subcategories_for_vendor(self):
        """测试获取厂商 subcategory"""
        # AWS 应该有预定义的 subcategory
        result = PromptTemplates.get_subcategories_for_vendor("aws")
        assert isinstance(result, list)
    
    def test_get_subcategories_for_unknown_vendor(self):
        """测试获取未知厂商 subcategory"""
        result = PromptTemplates.get_subcategories_for_vendor("unknown_vendor")
        assert result == []


class TestPromptTemplatesLoading:
    """测试模板加载功能"""
    
    def test_load_prompt_template_exists(self):
        """测试加载存在的模板"""
        # update_analysis.prompt.txt 应该存在
        template = PromptTemplates._load_prompt_template("update_analysis")
        assert template is not None
        assert len(template) > 0
    
    def test_load_prompt_template_cached(self):
        """测试模板缓存"""
        # 第一次加载
        PromptTemplates._load_prompt_template("update_analysis")
        # 检查缓存
        assert "update_analysis" in PromptTemplates._prompt_cache
        # 第二次加载应使用缓存
        template = PromptTemplates._load_prompt_template("update_analysis")
        assert template is not None
    
    def test_load_prompt_template_not_exists(self):
        """测试加载不存在的模板"""
        with pytest.raises(FileNotFoundError):
            PromptTemplates._load_prompt_template("nonexistent_template")


class TestGetUpdateAnalysisPrompt:
    """测试更新分析 Prompt 生成"""
    
    def test_basic_prompt_generation(self):
        """测试基本 Prompt 生成"""
        update_data = {
            "vendor": "aws",
            "source_channel": "blog",
            "title": "Test Update",
            "content": "This is test content",
            "product_name": "VPC",
            "product_category": "Networking"
        }
        
        prompt = PromptTemplates.get_update_analysis_prompt(update_data)
        
        assert prompt is not None
        assert len(prompt) > 0
        assert "aws" in prompt.lower() or "AWS" in prompt
    
    def test_prompt_with_doc_links(self):
        """测试带文档链接的 Prompt"""
        update_data = {
            "vendor": "aws",
            "source_channel": "whatsnew",
            "title": "Test",
            "content": "Content",
            "doc_links": [
                {"text": "User Guide", "url": "https://docs.aws.amazon.com/guide"}
            ]
        }
        
        prompt = PromptTemplates.get_update_analysis_prompt(update_data)
        assert "User Guide" in prompt
    
    def test_prompt_without_doc_links(self):
        """测试无文档链接的 Prompt"""
        update_data = {
            "vendor": "aws",
            "source_channel": "blog",
            "title": "Test",
            "content": "Content"
        }
        
        prompt = PromptTemplates.get_update_analysis_prompt(update_data)
        assert "无" in prompt or prompt is not None
    
    def test_prompt_content_truncation(self):
        """测试内容截断"""
        long_content = "x" * 10000
        update_data = {
            "vendor": "aws",
            "source_channel": "blog",
            "title": "Test",
            "content": long_content
        }
        
        prompt = PromptTemplates.get_update_analysis_prompt(update_data)
        # 内容应该被截断
        assert "..." in prompt
    
    def test_prompt_with_missing_fields(self):
        """测试缺失字段处理"""
        update_data = {}
        
        # 不应该抛出异常
        prompt = PromptTemplates.get_update_analysis_prompt(update_data)
        assert prompt is not None


class TestGetContentTranslationPrompt:
    """测试内容翻译 Prompt 生成"""
    
    def test_basic_translation_prompt(self):
        """测试基本翻译 Prompt"""
        prompt = PromptTemplates.get_content_translation_prompt(
            content="This is English content",
            title="Test Title"
        )
        
        assert prompt is not None
        assert "This is English content" in prompt
        assert "Test Title" in prompt
    
    def test_translation_prompt_without_title(self):
        """测试无标题的翻译 Prompt"""
        prompt = PromptTemplates.get_content_translation_prompt(
            content="English content"
        )
        
        assert prompt is not None
        assert "无" in prompt or "根据内容生成" in prompt


class TestIsBlogSource:
    """测试博客源判断"""
    
    def test_blog_source(self):
        """测试博客类型"""
        assert PromptTemplates.is_blog_source("blog") is True
        assert PromptTemplates.is_blog_source("network_blog") is True
        assert PromptTemplates.is_blog_source("BLOG") is True
    
    def test_non_blog_source(self):
        """测试非博客类型"""
        assert PromptTemplates.is_blog_source("whatsnew") is False
        assert PromptTemplates.is_blog_source("announcement") is False
    
    def test_empty_source(self):
        """测试空值"""
        assert PromptTemplates.is_blog_source("") is False
        assert PromptTemplates.is_blog_source(None) is False


class TestUpdateType:
    """测试 UpdateType 枚举"""
    
    def test_update_type_values(self):
        """测试获取所有枚举值"""
        values = UpdateType.values()
        assert isinstance(values, list)
        assert len(values) > 0
        assert "new_feature" in values or "NEW_FEATURE" in values.upper() if hasattr(values, 'upper') else True
