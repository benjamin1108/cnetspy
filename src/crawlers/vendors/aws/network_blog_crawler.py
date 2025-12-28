#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import re
import time
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
import html2text

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

# 保留的博客频道（网络主频道 + 云产品相关频道）
ALLOWED_BLOG_CHANNELS = {
    # 网络主频道
    'networking-and-content-delivery',
    # 云产品相关频道
    'aws',           # AWS主博客，发布产品更新
    'containers',    # 容器
    'compute',       # 计算
    'security',      # 安全
    'storage',       # 存储
    'database',      # 数据库
    'architecture',  # 架构
    'hpc',           # 高性能计算
    'infrastructure-and-automation',  # 基础设施自动化
}


class AwsNetworkBlogCrawler(BaseCrawler):
    """AWS网络博客爬虫实现 - 使用API方式爬取"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化AWS博客爬虫"""
        super().__init__(config, vendor, source_type)
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.start_url = self.source_config.get('url')
        self.api_url = "https://aws.amazon.com/api/dirs/items/search"
        # 获取截止年份配置
        aws_blog_config = config.get('aws_blog', {})
        self.crawl_until_year = aws_blog_config.get('crawl_until_year', 2025)
    
    def _get_identifier_strategy(self) -> str:
        """AWS Network Blog使用url-based策略"""
        return 'url_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """AWS Network Blog: hash(source_url)"""
        return [update.get('source_url', '')]
    
    def _is_networking_blog(self, url: str) -> bool:
        """检查文章URL是否属于允许的博客频道"""
        # 从 URL 提取博客频道: /blogs/xxx/ -> xxx
        if '/blogs/' in url:
            parts = url.split('/blogs/')[1].split('/')
            if parts:
                channel = parts[0]
                return channel in ALLOWED_BLOG_CHANNELS
        return False
    
    def _fetch_blog_items_from_api(self, page: int = 0, size: int = 100) -> Dict[str, Any]:
        """通过API获取博客文章列表（使用官方networking分类tag预过滤）"""
        params = {
            "item.directoryId": "blog-posts",
            "item.locale": "en_US",
            "sort_by": "item.dateCreated",
            "sort_order": "desc",
            "size": size,
            "page": page,
            "tags.id": "blog-posts#category#networking-content-delivery"  # 官方networking分类
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        try:
            resp = requests.get(self.api_url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return {}
    
    def _crawl(self) -> List[str]:
        """
        通过API爬取AWS网络相关博客
        
        Returns:
            保存的文件路径列表
        """
        saved_files = []
        
        try:
            # 获取配置
            test_mode = self.source_config.get('test_mode', False)
            article_limit = 1 if test_mode else self.crawler_config.get('article_limit', 50)
            force_mode = self.crawler_config.get('force', False)
            
            logger.info(f"爬取模式: {'test' if test_mode else 'normal'}, 限制{article_limit}篇, force={force_mode}")
            logger.info(f"截止年份: {self.crawl_until_year}")
            
            # 1. 通过API获取网络相关文章
            network_articles = self._fetch_network_articles(article_limit)
            self.set_total_discovered(len(network_articles))
            
            # 2. 过滤已存在的文章
            if not force_mode:
                network_articles = self._filter_new_articles(network_articles)
            
            # 3. 并行爬取文章内容
            all_updates = self._crawl_articles_parallel(network_articles)
            
            # 4. 保存文章
            saved_files = self._save_updates(all_updates)
            
            logger.info(f"成功保存 {len(saved_files)} 篇博客文章")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取AWS博客过程中发生错误: {e}")
            return saved_files
        finally:
            self._close_driver()
    
    def _fetch_network_articles(self, article_limit: int) -> List[Dict[str, Any]]:
        """通过API获取网络相关文章列表"""
        network_articles = []
        page = 0
        total_scanned = 0
        
        logger.info("开始通过API获取AWS博客数据...")
        
        while len(network_articles) < article_limit:
            data = self._fetch_blog_items_from_api(page=page, size=100)
            items = data.get("items", [])
            
            if not items:
                logger.info("API返回空数据，停止获取")
                break
            
            total_scanned += len(items)
            reached_cutoff = False
            
            for item in items:
                if len(network_articles) >= article_limit:
                    break
                
                # 检查截止年份
                item_data = item.get("item", {})
                date_created = item_data.get('dateCreated', '')
                if date_created:
                    article_year = int(date_created[:4]) if date_created[:4].isdigit() else 9999
                    if article_year < self.crawl_until_year:
                        logger.info(f"达到截止年份 {self.crawl_until_year}")
                        reached_cutoff = True
                        break
                
                # 提取文章信息
                additional = item_data.get("additionalFields", {})
                title = additional.get("title", "")
                url = additional.get("link", "")
                
                if title and url and self._is_networking_blog(url):
                    network_articles.append({
                        'title': title,
                        'url': url,
                        'tags': [t.get('name', '') for t in item.get("tags", [])[:5]],
                        'date': additional.get('displayDate', '')
                    })
            
            if reached_cutoff:
                break
            
            metadata = data.get("metadata", {})
            total_hits = metadata.get("totalHits", 0)
            
            logger.info(f"第{page + 1}页: 扫描{len(items)}篇，找到{len(network_articles)}篇网络相关")
            
            if total_scanned >= total_hits:
                break
            
            page += 1
            time.sleep(0.3)
        
        logger.info(f"总共扫描{total_scanned}篇，找到{len(network_articles)}篇网络相关文章")
        return network_articles
    
    def _filter_new_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已存在的文章"""
        filtered = []
        for article in articles:
            temp_update = {'source_url': article['url']}
            source_identifier = self.generate_source_identifier(temp_update)
            
            should_skip, reason = self.should_skip_update(
                source_url=article['url'],
                source_identifier=source_identifier,
                title=article['title']
            )
            if not should_skip:
                filtered.append(article)
            else:
                logger.debug(f"跳过({reason}): {article['title']}")
        
        logger.info(f"过滤后: {len(filtered)}篇新文章需要爬取")
        return filtered
    
    def _crawl_articles_parallel(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并行爬取文章内容"""
        if not articles:
            return []
        
        all_updates = []
        max_workers = min(10, len(articles))
        logger.info(f"使用 {max_workers} 个线程并行爬取")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_article = {
                executor.submit(self._crawl_single_article, article): article
                for article in articles
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_article):
                article = future_to_article[future]
                completed += 1
                try:
                    update = future.result()
                    if update:
                        all_updates.append(update)
                        logger.info(f"[{completed}/{len(articles)}] 成功: {article['title'][:50]}")
                    else:
                        logger.warning(f"[{completed}/{len(articles)}] 失败: {article['title'][:50]}")
                except Exception as e:
                    logger.error(f"[{completed}/{len(articles)}] 异常 [{article['title'][:30]}]: {e}")
        
        logger.info(f"总共收集到 {len(all_updates)} 篇博客文章")
        return all_updates
    
    def _save_updates(self, updates: List[Dict[str, Any]]) -> List[str]:
        """保存更新列表"""
        saved_files = []
        for update in updates:
            try:
                if self.save_update(update):
                    saved_files.append(update.get('source_url', ''))
            except Exception as e:
                logger.error(f"保存更新失败 [{update.get('title', 'Unknown')[:30]}]: {e}")
        return saved_files
    
    def _crawl_single_article(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        爬取单篇文章内容（用于线程池并行调用）
        
        Args:
            article: 文章信息字典，包含 title, url, tags, date
            
        Returns:
            update字典，失败返回None
        """
        url = article['url']
        title = article['title']
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"获取文章失败: {url} - HTTP {response.status_code}")
                return None
            
            article_html = response.text
            
            # 解析文章内容和发布日期
            content, pub_date = self._parse_article_content(url, article_html)
            
            # 构建 update 字典
            update = {
                'source_url': url,
                'title': title,
                'content': content,
                'publish_date': pub_date.replace('_', '-') if pub_date else '',
                'product_name': 'AWS Networking'
            }
            
            return update
            
        except Exception as e:
            logger.error(f"爬取文章失败: {url} - {e}")
            return None
    
    def _parse_article_content(self, url: str, html: str) -> Tuple[str, Optional[str]]:
        """
        解析文章内容和发布日期
        
        Args:
            url: 文章URL
            html: 文章页面HTML
            
        Returns:
            (Markdown内容, 发布日期)元组，如果找不到日期则日期为None
        """
        soup = BeautifulSoup(html, 'lxml')  # 统一使用lxml解析器
        
        # 提取发布日期
        pub_date = self._extract_publish_date(soup)
        
        # 1. 移除页头、页尾、侧边栏等非内容区域
        self._clean_non_content(soup)
        
        # 2. 尝试更精确地定位文章主体内容
        article = self._locate_article_content(soup, url)
        
        if not article:
            logger.warning(f"未找到文章主体: {url}")
            return "", pub_date
        
        # 3. 处理图片 - 支持懒加载和srcset
        self._process_images(article, url)
        
        # 4. 提取正文内容并转换为Markdown
        article_md = self._html_to_markdown(article)
        
        return article_md, pub_date
    
    def _process_images(self, article: BeautifulSoup, base_url: str) -> None:
        """
        处理文章中的图片 - 支持懒加载和srcset
        
        Args:
            article: 文章内容元素
            base_url: 基础URL用于转换相对路径
        """
        for img in article.find_all('img'):
            # 获取图片URL：优先级 src > data-src > data-lazy-src
            src = img.get('src', '')
            data_src = img.get('data-src', '')
            lazy_src = img.get('data-lazy-src', '')
            srcset = img.get('srcset', '')
            
            # 确定最终图片URL
            img_url = src or data_src or lazy_src
            
            # 如果没有找到，从srcset中提取
            if not img_url and srcset:
                # 优先选择webp格式
                webp_match = re.search(r'(https?://[^\s]+\.webp)', srcset)
                if webp_match:
                    img_url = webp_match.group(1)
                else:
                    # 取srcset中的第一个URL
                    parts = srcset.split(',')
                    if parts:
                        img_url = parts[0].strip().split(' ')[0]
            
            if not img_url:
                continue
            
            # 跳过base64数据URL
            if img_url.startswith('data:'):
                continue
            
            # 将相对路径转为绝对路径
            if not img_url.startswith(('http://', 'https://')):
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                else:
                    img_url = urljoin(base_url, img_url)
            
            # 更新src属性
            img['src'] = img_url
            
            # 清理多余属性，确保html2text正确处理
            for attr in ['srcset', 'sizes', 'data-src', 'data-lazy-src']:
                if img.has_attr(attr):
                    del img[attr]
    
    def _html_to_markdown(self, article: BeautifulSoup) -> str:
        """
        将HTML转换为Markdown，并进行额外的清理
        
        Args:
            article: 包含文章内容的BeautifulSoup对象
            
        Returns:
            清理后的Markdown内容
        """
        # 移除推广链接和无关元素
        for tag in article.find_all(['button', 'input', 'form']):
            tag.decompose()
        
        # 去掉空链接
        for a in article.find_all('a'):
            if not a.get_text(strip=True):
                a.replace_with_children()
        
        # 保留文章主体内容
        article_html = str(article)
        
        # 为线程安全，每次创建新的html2text实例
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.ignore_emphasis = False
        converter.body_width = 0
        article_md = converter.handle(article_html)
        
        # 复用基类的Markdown清理方法
        article_md = self._clean_markdown(article_md)
        
        return article_md
