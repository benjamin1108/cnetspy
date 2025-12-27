#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import re
import sys
import time
import hashlib
import datetime
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests
import markdown
import html2text

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))

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
            article_limit = self.crawler_config.get('article_limit', 50)
            force_mode = self.crawler_config.get('force', False)
            
            if test_mode:
                article_limit = 1
                logger.info("测试模式：限制爬取1篇文章")
            else:
                logger.info(f"爬取模式：限制爬取{article_limit}篇文章")
            
            if force_mode:
                logger.info("强制模式已启用，将重新爬取所有文章")
            
            # 通过API获取文章并过滤网络相关的
            network_articles = []
            page = 0
            total_scanned = 0
            
            logger.info("开始通过API获取AWS博客数据...")
            logger.info(f"截止年份: {self.crawl_until_year}（只爬取{self.crawl_until_year}年及以后的文章）")
            
            reached_cutoff = False  # 是否达到截止年份
            
            while len(network_articles) < article_limit and not reached_cutoff:
                data = self._fetch_blog_items_from_api(page=page, size=100)
                items = data.get("items", [])
                
                if not items:
                    logger.info(f"API返回空数据，停止获取")
                    break
                
                total_scanned += len(items)
                
                # 过滤属于Networking博客频道的文章（用URL路径判断）
                for item in items:
                    if len(network_articles) >= article_limit:
                        break
                    
                    item_data = item.get("item", {})
                    additional = item_data.get("additionalFields", {})
                    
                    # 获取文章发布日期，检查是否达到截止年份
                    date_created = item_data.get('dateCreated', '')
                    if date_created:
                        article_year = int(date_created[:4]) if date_created[:4].isdigit() else 9999
                        if article_year < self.crawl_until_year:
                            logger.info(f"达到截止年份 {self.crawl_until_year}，停止爬取（当前文章: {article_year}年）")
                            reached_cutoff = True
                            break
                    
                    title = additional.get("title", "")
                    url = additional.get("link", "")
                    
                    # 只保留URL路径包含 /blogs/networking-and-content-delivery/ 的文章
                    if title and url and self._is_networking_blog(url):
                        tags = item.get("tags", [])
                        tag_names = [t.get('name', '') for t in tags[:5]]
                        network_articles.append({
                            'title': title,
                            'url': url,
                            'tags': tag_names,
                            'date': additional.get('displayDate', '')
                        })
                
                metadata = data.get("metadata", {})
                total_hits = metadata.get("totalHits", 0)
                
                logger.info(f"第{page + 1}页: 扫描{len(items)}篇，找到{len(network_articles)}篇网络相关文章")
                
                if total_scanned >= total_hits:
                    break
                
                page += 1
                time.sleep(0.3)
            
            logger.info(f"总共扫描{total_scanned}篇文章，找到{len(network_articles)}篇网络相关文章")
            
            # 过滤已存在的文章
            if not force_mode:
                filtered_articles = []
                already_crawled = 0
                
                for article in network_articles:
                    temp_update = {'source_url': article['url']}
                    source_identifier = self.generate_source_identifier(temp_update)
                    
                    if self.check_exists_in_db(article['url'], source_identifier):
                        already_crawled += 1
                        logger.debug(f"跳过已爬取: {article['title']}")
                    else:
                        filtered_articles.append(article)
                
                logger.info(f"过滤后: {len(filtered_articles)}篇新文章需要爬取，{already_crawled}篇已存在")
                network_articles = filtered_articles
            
            # 使用线程池并行爬取每篇文章内容
            all_updates = []
            if network_articles:
                max_workers = min(10, len(network_articles))  # 最多10个并发
                logger.info(f"使用 {max_workers} 个线程并行爬取")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有任务
                    future_to_article = {
                        executor.submit(self._crawl_single_article, article): article
                        for article in network_articles
                    }
                    
                    # 处理完成的任务
                    completed = 0
                    for future in concurrent.futures.as_completed(future_to_article):
                        article = future_to_article[future]
                        completed += 1
                        try:
                            update = future.result()
                            if update:
                                all_updates.append(update)
                                logger.info(f"[{completed}/{len(network_articles)}] 成功: {article['title'][:50]}")
                            else:
                                logger.warning(f"[{completed}/{len(network_articles)}] 失败: {article['title'][:50]}")
                        except Exception as e:
                            logger.error(f"[{completed}/{len(network_articles)}] 异常 [{article['title'][:30]}]: {e}")
            
            logger.info(f"总共收集到 {len(all_updates)} 篇博客文章")
            
            # 保存每篇文章
            for update in all_updates:
                try:
                    success = self.save_update(update)
                    if success:
                        saved_files.append(update.get('source_url', ''))
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')[:30]}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 篇博客文章")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取AWS博客过程中发生错误: {e}")
            return saved_files
        finally:
            self._close_driver()
    
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
        soup = BeautifulSoup(html, 'html.parser')  # 使用更宽容的解析器避免lxml错误
        
        # 提取发布日期
        pub_date = self._extract_publish_date(soup)
        
        # 1. 移除页头、页尾、侧边栏等非内容区域
        self._clean_non_content(soup)
        
        # 2. 尝试更精确地定位文章主体内容
        article = self._locate_article_content(soup, url)
        
        if not article:
            logger.warning(f"未找到文章主体: {url}")
            return "", pub_date
        
        # 3. 处理图片 - 使用原始URL而不是下载到本地
        for img in article.find_all('img'):
            if not img.get('src'):
                continue
            
            # 将相对URL转换为绝对URL
            img_url = urljoin(url, img['src'])
            img['src'] = img_url
            
            # 处理srcset属性，优先选择webp格式
            if img.get('srcset'):
                srcset = img['srcset']
                # 保存srcset值用于调试
                logger.debug(f"Found image with srcset: {srcset}")
                
                # 尝试从srcset中提取webp格式的URL
                webp_match = re.search(r'(https?://[^\s]+\.webp)', srcset)
                if webp_match:
                    webp_url = webp_match.group(1)
                    logger.info(f"选择webp格式图片URL: {webp_url}")
                    img['src'] = webp_url
                    
                # 删除srcset和sizes属性，以防html2text无法正确处理
                if img.has_attr('srcset'):
                    del img['srcset']
                if img.has_attr('sizes'):
                    del img['sizes']
        
        # 4. 提取正文内容并转换为Markdown
        article_md = self._html_to_markdown(article)
        
        return article_md, pub_date
    
    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        从文章中提取发布日期
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            发布日期字符串 (YYYY_MM_DD格式)，如果找不到则返回None
        """
        date_format = "%Y_%m_%d"
        
        # 特别针对AWS博客的日期提取 - 优先检查time标签
        time_elements = soup.find_all('time')
        if time_elements:
            for time_elem in time_elements:
                # 检查具有datePublished属性的time标签
                if time_elem.get('property') == 'datePublished' and time_elem.get('datetime'):
                    datetime_str = time_elem.get('datetime')
                    try:
                        # 处理ISO格式的日期时间 "2025-04-08T17:34:26-07:00"
                        # 从datetime属性中提取日期部分
                        date_part = datetime_str.split('T')[0]
                        parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                        logger.info(f"从time标签的datetime属性解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except (ValueError, IndexError) as e:
                        logger.debug(f"解析time标签的datetime属性失败: {e}")
                
                # 如果没有datetime属性或解析失败，尝试解析标签文本
                date_text = time_elem.get_text().strip()
                if date_text:
                    try:
                        # 尝试解析 "08 APR 2025" 格式
                        parsed_date = datetime.datetime.strptime(date_text, '%d %b %Y')
                        logger.info(f"从time标签的文本内容解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except ValueError:
                        try:
                            # 尝试解析 "April 08, 2025" 格式
                            parsed_date = datetime.datetime.strptime(date_text, '%B %d, %Y')
                            logger.info(f"从time标签的文本内容解析到日期: {parsed_date.strftime(date_format)}")
                            return parsed_date.strftime(date_format)
                        except ValueError:
                            continue

        # 查找元数据中的日期 - AWS博客页面通常在meta标签中也有日期信息
        meta_published = soup.find('meta', property='article:published_time') or soup.find('meta', property='publish_date')
        if meta_published and meta_published.get('content'):
            try:
                content = meta_published.get('content')
                # 处理ISO格式日期
                if 'T' in content:
                    date_part = content.split('T')[0]
                    parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                else:
                    parsed_date = datetime.datetime.strptime(content, '%Y-%m-%d')
                logger.info(f"从meta标签解析到日期: {parsed_date.strftime(date_format)}")
                return parsed_date.strftime(date_format)
            except (ValueError, IndexError) as e:
                logger.debug(f"解析meta标签日期失败: {e}")
        
        # 尝试不同的选择器来定位日期元素
        date_selectors = [
            '.lb-blog-header__date', '.blog-date', '.date', '.published-date', '.post-date',
            '.post-meta time', '.post-meta .date', '.entry-date', '.meta-date',
            'time', '[itemprop="datePublished"]', '.aws-blog-post-date', '.aws-date'
        ]
        
        # 遍历所有可能的选择器
        for selector in date_selectors:
            date_elements = soup.select(selector)
            
            if date_elements:
                for date_elem in date_elements:
                    # 尝试获取datetime属性
                    date_str = date_elem.get('datetime') or date_elem.text.strip()
                    if date_str:
                        try:
                            # 尝试多种日期格式
                            for date_pattern in [
                                '%Y-%m-%d', '%Y/%m/%d', '%b %d, %Y', '%B %d, %Y',
                                '%d %b %Y', '%d %B %Y', '%m/%d/%Y', '%d-%m-%Y',
                                '%Y年%m月%d日', '%Y.%m.%d'
                            ]:
                                try:
                                    # 提取日期字符串
                                    # 如果字符串中包含时间，只保留日期部分
                                    if ' ' in date_str and not any(month in date_str for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'January', 'February', 'March', 'April', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                                        date_str = date_str.split(' ')[0]
                                    
                                    parsed_date = datetime.datetime.strptime(date_str, date_pattern)
                                    logger.info(f"从选择器 {selector} 解析到日期: {parsed_date.strftime(date_format)}")
                                    return parsed_date.strftime(date_format)
                                except ValueError:
                                    continue
                        except Exception as e:
                            logger.debug(f"日期解析错误: {e}")
        
        # 如果通过选择器没找到，尝试在文本中搜索日期模式
        try:
            text = soup.get_text()
            
            # 常见日期格式的正则表达式
            date_patterns = [
                # YYYY-MM-DD
                r'(\d{4}-\d{1,2}-\d{1,2})',
                # YYYY/MM/DD
                r'(\d{4}/\d{1,2}/\d{1,2})',
                # Month DD, YYYY
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',
                # DD Month YYYY
                r'\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
                # MM/DD/YYYY
                r'(\d{1,2}/\d{1,2}/\d{4})',
            ]
            
            for pattern in date_patterns:
                matches = re.search(pattern, text)
                if matches:
                    date_str = matches.group(0)
                    try:
                        # 尝试解析找到的日期
                        if '-' in date_str:
                            parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        elif '/' in date_str:
                            # 尝试两种不同的日期格式（YYYY/MM/DD 或 MM/DD/YYYY）
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%m/%d/%Y')
                        elif ',' in date_str:
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%B %d, %Y')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%b %d, %Y')
                        else:
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%d %B %Y')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%d %b %Y')
                        
                        logger.info(f"从文本内容解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except ValueError:
                        continue
        except Exception as e:
            logger.debug(f"从文本提取日期错误: {e}")
        
        # 如果找不到日期，使用当前日期
        logger.warning("未找到发布日期，使用当前日期")
        return datetime.datetime.now().strftime(date_format)
    
    def _clean_non_content(self, soup: BeautifulSoup) -> None:
        """
        移除页头、页尾、侧边栏等非内容区域
        
        Args:
            soup: BeautifulSoup对象
        """
        # 移除常见的页头元素
        for header in soup.select('header, .header, #header, .top-nav, .aws-header, .navigation, nav, .top-bar, .lb-header'):
            header.decompose()
        
        # 移除常见的页尾元素
        for footer in soup.select('footer, .footer, #footer, .aws-footer, .bottom-bar, .lb-footer'):
            footer.decompose()
        
        # 移除常见的侧边栏元素
        for sidebar in soup.select('.sidebar, #sidebar, .side-nav, .aws-sidebar, .column-right, .column-left, aside'):
            sidebar.decompose()
        
        # 移除常见的广告和推广元素
        for promo in soup.select('.ad, .ads, .advertisement, .promo, .promotion, .banner, .aws-promo, .aws-banner'):
            promo.decompose()
        
        # 移除导航元素
        for nav in soup.select('.breadcrumb, .breadcrumbs, .navigation, .nav, .menu'):
            nav.decompose()
        
        # 移除评论区
        for comments in soup.select('.comments, #comments, .comment-section, .disqus, .discourse'):
            comments.decompose()
        
        # 移除社交媒体分享按钮
        for social in soup.select('.share, .social, .social-media, .social-buttons, .aws-social'):
            social.decompose()
        
        # 移除相关文章推荐
        for related in soup.select('.related, .related-posts, .suggested, .aws-related, .recommended'):
            related.decompose()
        
        # 移除脚本、样式等无关元素
        for tag in soup.find_all(['script', 'style', 'noscript', 'iframe', 'svg']):
            tag.decompose()
    
    def _locate_article_content(self, soup: BeautifulSoup, url: str) -> Optional[BeautifulSoup]:
        """
        更精确地定位文章主体内容
        
        Args:
            soup: BeautifulSoup对象
            url: 文章URL
            
        Returns:
            包含文章主体内容的BeautifulSoup对象，或None
        """
        # 优先级从高到低尝试找到文章主体
        selectors = [
            # 最可能的文章内容选择器
            'article .lb-post-content',
            'article .lb-grid-content',
            '.blog-post-content',
            '.post-content',
            '.article-content',
            '.entry-content',
            '.post-body',
            '.content-body',
            
            # 次优先级选择器
            'main article',
            'main .content',
            'article',
            '.post',
            '#content .post',
            '.blog-content',
            '.lb-grid-container > div > div',  # AWS博客通常使用的容器结构
            
            # 最后的备选选择器
            'main',
            '#content',
            '.content',
            '.container'
        ]
        
        # 尝试所有选择器
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                # 找到内容最长的元素，这通常是正文
                main_element = max(elements, key=lambda x: len(str(x)))
                logger.debug(f"找到文章主体，使用选择器: {selector}")
                return main_element
        
        # 如果还是找不到，尝试一个启发式方法：寻找最长的<div>或<section>
        candidates = []
        for tag in soup.find_all(['div', 'section']):
            # 排除明显不是内容的元素
            if tag.has_attr('class') and any(c in str(tag['class']) for c in ['header', 'footer', 'sidebar', 'menu', 'nav']):
                continue
            
            # 排除太短的内容
            if len(str(tag)) < 1000:  # 文章通常至少有1000个字符
                continue
            
            # 判断是否包含文章特征(段落、标题等)
            if len(tag.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol'])) > 5:
                candidates.append(tag)
        
        if candidates:
            # 找到内容最长的候选元素
            main_element = max(candidates, key=lambda x: len(str(x)))
            logger.debug("使用启发式方法找到文章主体")
            return main_element
        
        # 最后的备选：返回<body>
        body = soup.find('body')
        if body:
            logger.warning(f"未找到具体文章主体，使用<body>: {url}")
            return body
        
        return None
    
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
        
        # 清理Markdown
        article_md = self._clean_markdown(article_md)
        
        return article_md
    
    def _clean_markdown(self, markdown_text: str) -> str:
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
    
    def _create_filename(self, url: str, pub_date: str, ext: str) -> str:
        """
        根据发布日期和URL哈希值创建文件名
        
        Args:
            url: 文章URL
            pub_date: 发布日期（YYYY_MM_DD格式）
            ext: 文件扩展名（如.md）
            
        Returns:
            格式为: YYYY_MM_DD_URLHASH.md 的文件名
        """
        # 生成URL的哈希值（取前8位作为短哈希）
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 组合日期和哈希值
        filename = f"{pub_date}_{url_hash}{ext}"
        
        return filename
    
    def save_to_markdown(self, url: str, title: str, content_and_date: Tuple[str, Optional[str]]) -> str:
        """
        保存内容为Markdown文件，调用基类方法
        
        Args:
            url: 文章URL
            title: 文章标题
            content_and_date: 文章内容和发布日期的元组
            
        Returns:
            保存的文件路径
        """
        return super().save_to_markdown(url, title, content_and_date)

    def _fix_images_and_links(self, content_elem: BeautifulSoup) -> None:
        """
        修复文章中的图片和链接
        
        Args:
            content_elem: 文章内容元素
        """
        # 处理图片
        for img in content_elem.find_all('img'):
            # 获取图片的src属性
            src = img.get('src', '')
            data_src = img.get('data-src', '')
            lazy_src = img.get('data-lazy-src', '')
            srcset = img.get('srcset', '')
            
            # 尝试从各种可能的属性中获取图片链接
            img_url = src or data_src or lazy_src
            
            # 如果没有找到图片链接，尝试从srcset中提取
            if not img_url and srcset:
                parts = srcset.split(',')
                if parts:
                    first_part = parts[0].strip()
                    img_url = first_part.split(' ')[0]
            
            # 如果找到了图片链接
            if img_url:
                # 检查图片链接是否为相对路径
                if not img_url.startswith(('http://', 'https://', '//')):
                    # 将相对路径转为绝对路径
                    img_url = urljoin(self.start_url, img_url)
                    
                # 处理以//开头的链接
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                
                # 如果是数据URL（base64），保留原样
                if img_url.startswith('data:'):
                    continue
                
                # 更新alt属性，如果没有alt，使用空字符串
                alt_text = img.get('alt', '') or ''
                
                # 创建Markdown格式的图片链接
                img_markdown = f'![{alt_text}]({img_url})'
                img.replace_with(BeautifulSoup(img_markdown, 'html.parser'))
        
        # 处理链接
        for a in content_elem.find_all('a'):
            href = a.get('href', '')
            # 如果链接不为空且不是锚点链接
            if href and not href.startswith('#'):
                # 处理相对路径的链接
                if not href.startswith(('http://', 'https://', '//')):
                    href = urljoin(self.start_url, href)
                
                # 处理以//开头的链接
                if href.startswith('//'):
                    href = 'https:' + href
                    
                # 获取链接文本，如果为空，使用链接本身
                link_text = a.get_text().strip() or href
                
                # 检查链接是否指向图片文件
                img_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff', '.ico']
                is_image_link = any(href.lower().endswith(ext) for ext in img_extensions)
                
                if is_image_link:
                    # 将图片链接转换为Markdown图片
                    img_markdown = f'![{link_text}]({href})'
                    a.replace_with(BeautifulSoup(img_markdown, 'html.parser'))
                else:
                    # 将链接转换为Markdown链接
                    a_markdown = f'[{link_text}]({href})'
                    a.replace_with(BeautifulSoup(a_markdown, 'html.parser'))
