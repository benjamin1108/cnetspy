#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
内容解析器
从HTML中提取文章内容、日期等信息
"""

import logging
import re
import datetime
from typing import Optional, Tuple, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# 尝试导入html2text
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
    logging.warning("html2text库未安装，将使用简单的HTML到文本转换")

logger = logging.getLogger(__name__)


class ContentParser:
    """内容解析器，处理HTML解析和内容提取"""
    
    def __init__(self):
        """初始化解析器"""
        self.html_converter = self._init_html_converter()
    
    def _init_html_converter(self):
        """
        初始化HTML到Markdown转换器
        
        Returns:
            HTML2Text对象或None
        """
        if HTML2TEXT_AVAILABLE:
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = False
            converter.ignore_tables = False
            converter.body_width = 0  # 不限制宽度
            converter.use_automatic_links = True  # 使用自动链接
            converter.emphasis_mark = '*'  # 强调使用星号
            converter.strong_mark = '**'  # 加粗使用双星号
            converter.wrap_links = False  # 不换行链接
            converter.pad_tables = True  # 表格填充
            return converter
        return None
    
    def html_to_markdown(self, html_content: str) -> str:
        """
        将HTML转换为Markdown
        
        Args:
            html_content: HTML内容
            
        Returns:
            Markdown内容
        """
        if self.html_converter:
            markdown_content = self.html_converter.handle(html_content)
        else:
            # 简单的HTML到文本转换
            soup = BeautifulSoup(html_content, 'lxml')
            markdown_content = soup.get_text("\n\n", strip=True)
        
        # 清理Markdown
        markdown_content = self.clean_markdown(markdown_content)
        
        return markdown_content
    
    def clean_markdown(self, markdown_text: str) -> str:
        """
        清理Markdown文本，去除多余内容并美化格式
        
        Args:
            markdown_text: 原始Markdown文本
            
        Returns:
            清理后的Markdown文本
        """
        # 去除连续多个空行
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        # 美化代码块
        markdown_text = re.sub(r'```([^`]+)```', r'\n\n```\1```\n\n', markdown_text)
        
        # 美化图片格式，确保图片前后有空行
        markdown_text = re.sub(r'([^\n])!\[', r'\1\n\n![', markdown_text)
        markdown_text = re.sub(r'\.((?:jpg|jpeg|png|gif|webp|svg))\)([^\n])', r'.\1)\n\n\2', markdown_text)
        
        return markdown_text
    
    def extract_article_content(self, soup: BeautifulSoup, url: str) -> str:
        """
        从文章页面提取文章内容
        
        Args:
            soup: BeautifulSoup对象
            url: 文章URL
            
        Returns:
            Markdown格式的文章内容
        """
        # 尝试定位文章主体内容
        content_selectors = [
            'article', 
            '.entry-content', 
            '.post-content', 
            '.article-content', 
            '.main-content',
            '.blog-post',
            '.content-container',
            'main',
            '#main-content'
        ]
        
        article_elem = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # 选择最长的元素作为文章主体
                article_elem = max(elements, key=lambda x: len(str(x)))
                break
        
        # 如果没有找到文章主体，使用页面主体
        if not article_elem:
            article_elem = soup.find('body')
            
        if not article_elem:
            logger.warning(f"未找到文章主体: {url}")
            return "无法提取文章内容"
        
        # 清理非内容元素
        for elem in article_elem.select('header, footer, sidebar, .sidebar, nav, .navigation, .ad, .ads, .comments, .social-share'):
            elem.decompose()
        
        # 转换为Markdown
        html = str(article_elem)
        if self.html_converter:
            markdown_content = self.html_converter.handle(html)
        else:
            # 简单的HTML到文本转换
            markdown_content = article_elem.get_text("\n\n", strip=True)
        
        # 清理和美化Markdown
        markdown_content = self.clean_markdown(markdown_content)
        
        return markdown_content
    
    def is_likely_blog_post(self, url: str) -> bool:
        """
        判断URL是否可能是博客文章
        
        Args:
            url: 要检查的URL
            
        Returns:
            True如果URL可能是博客文章，否则False
        """
        # 移除协议和域名部分
        parsed = urlparse(url)
        path = parsed.path
        
        # 博客文章URL的常见模式
        blog_patterns = [
            r'/blogs/[^/]+/[^/]+',  # 如 /blogs/networking-and-content-delivery/article-name
            r'/blog/[^/]+',         # 如 /blog/article-name
            r'/post/[^/]+',         # 如 /post/article-name
            r'/\d{4}/\d{2}/[^/]+',  # 如 /2022/01/article-name (日期格式)
            r'/news/[^/]+',         # 如 /news/article-name
            r'/announcements/[^/]+', # 如 /announcements/article-name
        ]
        
        # 检查是否匹配任何博客文章模式
        for pattern in blog_patterns:
            if re.search(pattern, path):
                return True
        
        # 排除明显的非文章页面
        exclude_patterns = [
            r'/tag/', r'/tags/', r'/category/', r'/categories/',
            r'/author/', r'/about/', r'/contact/', r'/feed/',
            r'/archive/', r'/archives/', r'/page/\d+', r'/search/'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, path):
                return False
                
        # 检查是否在URL路径中包含特定关键词
        blog_keywords = ['post', 'article', 'blog', 'news', 'announcement']
        for keyword in blog_keywords:
            if keyword in path.lower():
                return True
                
        # 默认返回False，宁可错过也不要误报
        return False


class DateExtractor:
    """日期提取器"""
    
    DATE_FORMAT = "%Y_%m_%d"
    
    # 日期选择器列表
    DATE_SELECTORS = [
        '.lb-blog-header__date', '.blog-date', '.date', '.published-date', '.post-date',
        '.post-meta time', '.post-meta .date', '.entry-date', '.meta-date',
        'time', '[itemprop="datePublished"]', '.aws-blog-post-date', '.aws-date'
    ]
    
    # 日期格式列表
    DATE_PATTERNS = [
        '%Y-%m-%d', '%Y/%m/%d', '%b %d, %Y', '%B %d, %Y',
        '%d %b %Y', '%d %B %Y', '%m/%d/%Y', '%d-%m-%Y',
        '%Y年%m月%d日', '%Y.%m.%d'
    ]
    
    @classmethod
    def extract_publish_date(
        cls, 
        soup: BeautifulSoup, 
        list_date: Optional[str] = None, 
        url: Optional[str] = None
    ) -> str:
        """
        从文章中提取发布日期
        
        Args:
            soup: BeautifulSoup对象
            list_date: 从列表页获取的日期
            url: 文章URL
            
        Returns:
            发布日期字符串 (YYYY_MM_DD格式)
        """
        # 1. 检查time标签
        date = cls._extract_from_time_tags(soup)
        if date:
            return date
        
        # 2. 检查meta标签
        date = cls._extract_from_meta_tags(soup)
        if date:
            return date
        
        # 3. 检查日期选择器
        date = cls._extract_from_selectors(soup)
        if date:
            return date
        
        # 4. 从文本中搜索日期模式
        date = cls._extract_from_text(soup)
        if date:
            return date
        
        # 5. 使用列表页日期
        if list_date:
            logger.info(f"使用从列表页获取的日期: {list_date}")
            return list_date
        
        # 6. 从URL中提取日期
        if url:
            date = cls._extract_from_url(url)
            if date:
                return date
        
        # 7. 使用当前日期
        logger.warning("未找到发布日期，使用当前日期")
        return datetime.datetime.now().strftime(cls.DATE_FORMAT)
    
    @classmethod
    def _extract_from_time_tags(cls, soup: BeautifulSoup) -> Optional[str]:
        """从time标签提取日期"""
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            # 检查datePublished属性
            if time_elem.get('property') == 'datePublished' and time_elem.get('datetime'):
                datetime_str = time_elem.get('datetime')
                try:
                    date_part = datetime_str.split('T')[0]
                    parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                    return parsed_date.strftime(cls.DATE_FORMAT)
                except (ValueError, IndexError):
                    pass
            
            # 尝试解析标签文本
            date_text = time_elem.get_text().strip()
            if date_text:
                for fmt in ['%d %b %Y', '%B %d, %Y']:
                    try:
                        parsed_date = datetime.datetime.strptime(date_text, fmt)
                        return parsed_date.strftime(cls.DATE_FORMAT)
                    except ValueError:
                        continue
        return None
    
    @classmethod
    def _extract_from_meta_tags(cls, soup: BeautifulSoup) -> Optional[str]:
        """从meta标签提取日期"""
        meta_published = soup.find('meta', property='article:published_time') or soup.find('meta', property='publish_date')
        if meta_published and meta_published.get('content'):
            try:
                content = meta_published.get('content')
                if 'T' in content:
                    date_part = content.split('T')[0]
                    parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                else:
                    parsed_date = datetime.datetime.strptime(content, '%Y-%m-%d')
                return parsed_date.strftime(cls.DATE_FORMAT)
            except (ValueError, IndexError):
                pass
        return None
    
    @classmethod
    def _extract_from_selectors(cls, soup: BeautifulSoup) -> Optional[str]:
        """从日期选择器提取日期"""
        for selector in cls.DATE_SELECTORS:
            date_elements = soup.select(selector)
            for date_elem in date_elements:
                date_str = date_elem.get('datetime') or date_elem.text.strip()
                if date_str:
                    for date_pattern in cls.DATE_PATTERNS:
                        try:
                            parsed_date = datetime.datetime.strptime(date_str, date_pattern)
                            return parsed_date.strftime(cls.DATE_FORMAT)
                        except ValueError:
                            continue
        return None
    
    @classmethod
    def _extract_from_text(cls, soup: BeautifulSoup) -> Optional[str]:
        """从页面文本中搜索日期模式"""
        try:
            text = soup.get_text()
            
            date_patterns = [
                (r'(\d{4}-\d{1,2}-\d{1,2})', '%Y-%m-%d'),
                (r'(\d{4}/\d{1,2}/\d{1,2})', '%Y/%m/%d'),
                (r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', '%B %d, %Y'),
                (r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})', '%b %d, %Y'),
            ]
            
            for pattern, date_fmt in date_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        parsed_date = datetime.datetime.strptime(match.group(1), date_fmt)
                        return parsed_date.strftime(cls.DATE_FORMAT)
                    except ValueError:
                        continue
        except Exception:
            pass
        return None
    
    @classmethod
    def _extract_from_url(cls, url: str) -> Optional[str]:
        """从URL中提取日期"""
        url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
        if url_date_match:
            try:
                year, month, day = url_date_match.groups()
                parsed_date = datetime.datetime(int(year), int(month), int(day))
                return parsed_date.strftime(cls.DATE_FORMAT)
            except (ValueError, TypeError):
                pass
        return None
    
    @classmethod
    def parse_date_string(cls, date_str: Optional[str]) -> Optional[str]:
        """
        解析日期字符串，转换为统一格式 (YYYY_MM_DD)
        
        Args:
            date_str: 日期字符串
            
        Returns:
            格式化的日期字符串或None
        """
        if not date_str:
            return None
            
        # 清理日期字符串
        date_str = date_str.strip()
        
        # 尝试从ISO格式解析
        iso_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        if iso_match:
            return iso_match.group(1).replace('-', '_')
            
        # 尝试解析常见的日期格式
        date_formats = [
            # 月份名称格式
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})',
            r'(\d{1,2}) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,? (\d{4})',
            
            # 数字格式
            r'(\d{1,2})[/\.-](\d{1,2})[/\.-](\d{4})',
            r'(\d{4})[/\.-](\d{1,2})[/\.-](\d{1,2})',
        ]
        
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        for pattern in date_formats:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 2:  # 月份名称格式
                    day, year = groups
                    # 提取月份
                    month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', date_str)
                    if month_match:
                        month = month_map.get(month_match.group(1), '01')
                        day = day.zfill(2)
                        return f"{year}_{month}_{day}"
                elif len(groups) == 3:  # 数字格式
                    if len(groups[0]) == 4:  # YYYY-MM-DD
                        year, month, day = groups
                    else:  # MM/DD/YYYY
                        month, day, year = groups
                    month = month.zfill(2)
                    day = day.zfill(2)
                    return f"{year}_{month}_{day}"
                
        # 如果无法解析，返回None
        return None


# 全局实例
content_parser = ContentParser()
date_extractor = DateExtractor()
