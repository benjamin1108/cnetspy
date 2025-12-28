#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试内容解析器模块
"""

import pytest
from bs4 import BeautifulSoup

from src.crawlers.common.content_parser import (
    ContentParser,
    DateExtractor,
    content_parser,
    date_extractor
)


@pytest.fixture
def parser():
    """创建 ContentParser 实例"""
    return ContentParser()


class TestContentParser:
    """测试 ContentParser 类"""
    
    def test_init(self, parser):
        """测试初始化"""
        assert parser is not None
        assert parser.html_converter is not None
    
    def test_html_to_markdown_basic(self, parser):
        """测试基本 HTML 转 Markdown"""
        html = "<p>Hello <strong>World</strong></p>"
        result = parser.html_to_markdown(html)
        
        assert "Hello" in result
        assert "**World**" in result or "World" in result
    
    def test_html_to_markdown_with_links(self, parser):
        """测试带链接的 HTML 转换"""
        html = '<p><a href="https://example.com">Link</a></p>'
        result = parser.html_to_markdown(html)
        
        assert "Link" in result
        assert "example.com" in result
    
    def test_html_to_markdown_with_headers(self, parser):
        """测试标题转换"""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        result = parser.html_to_markdown(html)
        
        assert "Title" in result
        assert "Subtitle" in result
    
    def test_clean_markdown_removes_multiple_newlines(self, parser):
        """测试清理多余空行"""
        text = "Line 1\n\n\n\n\nLine 2"
        result = parser.clean_markdown(text)
        
        assert "\n\n\n" not in result
    
    def test_extract_article_content_basic(self, parser):
        """测试文章内容提取"""
        html = """
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>Article content here</p>
            </article>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        result = parser.extract_article_content(soup, "https://example.com")
        
        assert "Article Title" in result
        assert "Article content here" in result
    
    def test_extract_article_content_removes_nav(self, parser):
        """测试移除导航元素"""
        html = """
        <html>
        <body>
            <article>
                <nav>Navigation</nav>
                <p>Real content</p>
                <footer>Footer</footer>
            </article>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        result = parser.extract_article_content(soup, "https://example.com")
        
        assert "Real content" in result
        # nav 和 footer 应该被移除
        assert "Navigation" not in result
    
    def test_extract_article_content_fallback_to_body(self, parser):
        """测试回退到 body 元素"""
        html = """
        <html>
        <body>
            <div>Content in body</div>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        result = parser.extract_article_content(soup, "https://example.com")
        
        assert "Content in body" in result
    
    def test_is_likely_blog_post_true(self, parser):
        """测试博客文章 URL 识别 - 是"""
        assert parser.is_likely_blog_post("https://example.com/blogs/aws/post-title") is True
        assert parser.is_likely_blog_post("https://example.com/blog/my-post") is True
        assert parser.is_likely_blog_post("https://example.com/2024/01/post") is True
        assert parser.is_likely_blog_post("https://example.com/news/announcement") is True
    
    def test_is_likely_blog_post_false(self, parser):
        """测试博客文章 URL 识别 - 否"""
        assert parser.is_likely_blog_post("https://example.com/tag/aws") is False
        assert parser.is_likely_blog_post("https://example.com/category/tech") is False
        assert parser.is_likely_blog_post("https://example.com/author/john") is False
        assert parser.is_likely_blog_post("https://example.com/about/") is False


class TestDateExtractor:
    """测试 DateExtractor 类"""
    
    def test_extract_from_time_tags(self):
        """测试从 time 标签提取日期"""
        html = '<time property="datePublished" datetime="2024-12-28T10:00:00Z">Dec 28, 2024</time>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_time_tags(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_time_tags_text(self):
        """测试从 time 标签文本提取日期"""
        html = '<time>28 Dec 2024</time>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_time_tags(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_meta_tags(self):
        """测试从 meta 标签提取日期"""
        html = '<meta property="article:published_time" content="2024-12-28T10:00:00Z">'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_meta_tags(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_meta_tags_without_time(self):
        """测试从 meta 标签提取纯日期"""
        html = '<meta property="article:published_time" content="2024-12-28">'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_meta_tags(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_selectors(self):
        """测试从选择器提取日期"""
        html = '<div class="date">2024-12-28</div>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_selectors(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_text(self):
        """测试从文本提取日期"""
        html = '<p>Posted on December 28, 2024</p>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_text(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_text_short_month(self):
        """测试从文本提取简写月份日期"""
        html = '<p>Dec 28, 2024</p>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor._extract_from_text(soup)
        assert result == "2024_12_28"
    
    def test_extract_from_url(self):
        """测试从 URL 提取日期"""
        result = DateExtractor._extract_from_url("https://example.com/2024/12/28/post-title")
        assert result == "2024_12_28"
    
    def test_extract_from_url_no_match(self):
        """测试 URL 无日期"""
        result = DateExtractor._extract_from_url("https://example.com/post/title")
        assert result is None
    
    def test_extract_publish_date_full_flow(self):
        """测试完整日期提取流程"""
        html = '<time datetime="2024-12-28">Date</time>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor.extract_publish_date(soup)
        assert result is not None
        assert "_" in result  # 格式应该是 YYYY_MM_DD
    
    def test_extract_publish_date_uses_list_date(self):
        """测试使用列表页日期"""
        html = '<p>No date here</p>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor.extract_publish_date(soup, list_date="2024_12_25")
        assert result == "2024_12_25"
    
    def test_extract_publish_date_uses_url(self):
        """测试使用 URL 日期"""
        html = '<p>No date here</p>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor.extract_publish_date(
            soup, 
            list_date=None,
            url="https://example.com/2024/11/20/post"
        )
        assert result == "2024_11_20"
    
    def test_extract_publish_date_fallback_to_today(self):
        """测试回退到当前日期"""
        html = '<p>No date at all</p>'
        soup = BeautifulSoup(html, 'lxml')
        
        result = DateExtractor.extract_publish_date(soup)
        assert result is not None
        assert "_" in result


class TestGlobalInstances:
    """测试全局实例"""
    
    def test_content_parser_instance(self):
        """测试全局 content_parser 实例"""
        assert content_parser is not None
        assert isinstance(content_parser, ContentParser)
    
    def test_date_extractor_class(self):
        """测试全局 date_extractor 类"""
        # date_extractor 是 DateExtractor 类本身（或实例）
        assert date_extractor is not None
