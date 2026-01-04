#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import re
import json
import sys
import time
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from lxml import etree

from bs4 import BeautifulSoup
import requests
import markdown
import html2text

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class GcpNetworkBlogCrawler(BaseCrawler):
    """
    GCP网络博客爬虫实现 (API版本)
    
    使用 Google batchexecute API 直接获取结构化数据，支持翻页和精准过滤。
    """
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化GCP博客爬虫"""
        super().__init__(config, vendor, source_type)
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.start_url = self.source_config.get('url')
        
        # API 配置
        self.api_url = "https://cloud.google.com/blog/_/TransformBlogUi/data/batchexecute"
        self.rpc_id = "SQC9mf" # Google Cloud Blog 列表组件 ID
    
    def _get_identifier_strategy(self) -> str:
        """GCP Network Blog使用url-based策略"""
        return 'url_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """GCP Network Blog: hash(source_url)"""
        return [update.get('source_url', '')]
    
    def _crawl(self) -> List[str]:
        """
        爬取GCP博客 (API 翻页模式 - 先收集后处理)
        
        Returns:
            保存的文件路径列表
        """
        saved_files = []
        
        # 获取爬取限制
        article_limit = self.source_config.get('article_limit', 50)
        # 测试模式限制
        if self.source_config.get('test_mode', False):
            article_limit = 1
            
        logger.info(f"开始爬取 GCP Network Blog (Target: {article_limit} 篇)")
        
        # --- Phase 1: 收集所有文章元数据 ---
        all_articles = []
        next_page_token = None
        page_num = 1
        
        logger.info("正在收集文章列表...")
        try:
            while len(all_articles) < article_limit:
                # 获取一页文章
                articles_data, new_token = self._fetch_article_list(next_page_token)
                
                if not articles_data:
                    logger.warning(f"第 {page_num} 页未获取到数据，停止翻页")
                    break
                
                # 添加到总列表
                for art in articles_data:
                    if len(all_articles) >= article_limit:
                        break
                    if art.get('url') and art.get('title'):
                        all_articles.append(art)
                
                logger.info(f"已收集 {len(all_articles)}/{article_limit} 篇 (第 {page_num} 页)")
                
                # 翻页处理
                if not new_token:
                    logger.info("API 返回无更多页面，列表收集完成")
                    break
                    
                next_page_token = new_token
                page_num += 1
                time.sleep(0.5) # API 间隔
                
        except Exception as e:
            logger.error(f"收集文章列表时发生错误: {e}")
            return saved_files # 如果列表都拿不到，直接退出

        # --- Phase 2: 批量去重过滤 ---
        urls_to_crawl = []
        force_mode = self.crawler_config.get('force', False)
        
        logger.info(f"开始过滤 {len(all_articles)} 篇文章...")
        
        for art in all_articles:
            title = art.get('title')
            url = art.get('url')
            
            if force_mode:
                urls_to_crawl.append(art)
                continue
                
            temp_update = {'source_url': url}
            source_identifier = self.generate_source_identifier(temp_update)
            should_skip, reason = self.should_skip_update(
                source_url=url, 
                source_identifier=source_identifier,
                title=title
            )
            
            if should_skip:
                logger.debug(f"跳过({reason}): {title}")
            else:
                urls_to_crawl.append(art)
        
        # 设置发现总数
        self.set_total_discovered(len(all_articles))
        logger.info(f"过滤完成: 发现 {len(all_articles)} 篇，新增 {len(urls_to_crawl)} 篇需要爬取")
        
        # --- Phase 3: 爬取详情页 ---
        if not urls_to_crawl:
            logger.info("没有新文章需要爬取")
            return saved_files
            
        for idx, art in enumerate(urls_to_crawl, 1):
            title = art.get('title')
            url = art.get('url')
            
            logger.info(f"正在爬取 [{idx}/{len(urls_to_crawl)}]: {title}")
            
            try:
                # 爬取详情页
                if self._process_single_article(title, url, saved_files):
                    # 成功后休眠
                    if idx < len(urls_to_crawl):
                        time.sleep(self.interval)
            except Exception as e:
                logger.error(f"处理文章出错: {title} - {e}")
                
        logger.info(f"爬取任务结束，成功保存 {len(saved_files)} 篇文章")
        return saved_files

    def _fetch_article_list(self, page_token: Optional[str]) -> Tuple[List[Dict], Optional[str]]:
        """
        调用 API 获取文章列表
        
        Returns:
            (articles_list, next_page_token)
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # 构造 RPC 参数
        # 参数结构: [tenant, language, ?, ?, limit, page_token, type, tags, ?]
        inner_args = json.dumps([
            "cloudblog", "en", None, None, 10, page_token, "article", ["networking"], [""]
        ])
        envelope = json.dumps([
            [[self.rpc_id, inner_args, None, "generic"]]
        ])
        
        params = {
            "rpcids": self.rpc_id, 
            "source-path": "/blog/products/networking",
            "hl": "en"
        }
        
        data = {"f.req": envelope}
        
        try:
            response = requests.post(self.api_url, headers=headers, params=params, data=data, timeout=30)
            if response.status_code != 200:
                logger.error(f"API 请求失败: {response.status_code}")
                return [], None
                
            # 解析响应 (去除防劫持前缀 )]}' )
            clean_text = response.text.replace(")]}'\n", "").strip()
            if not clean_text:
                return [], None
                
            outer_json = json.loads(clean_text)
            
            # 寻找包含数据的 payload
            payload_string = None
            for item in outer_json:
                if isinstance(item, list) and len(item) > 2 and item[0] == "wrb.fr":
                    payload_string = item[2]
                    break
            
            if not payload_string:
                return [], None
                
            inner_data = json.loads(payload_string)
            if not inner_data or len(inner_data) < 1:
                return [], None
                
            articles_raw = inner_data[0]
            new_token = inner_data[1] if len(inner_data) > 1 else None
            
            parsed_articles = []
            if articles_raw:
                for art in articles_raw:
                    # 数据结构: [category, title, ?, images, ?, ?, ?, url, timestamp, ...]
                    try:
                        parsed_articles.append({
                            'title': art[1],
                            'url': art[7],
                            'timestamp': art[8][0] if len(art) > 8 and art[8] else None
                        })
                    except IndexError:
                        continue
                        
            return parsed_articles, new_token
            
        except Exception as e:
            logger.error(f"解析 API 响应失败: {e}")
            return [], None

    def _process_single_article(self, title: str, url: str, saved_files: List[str]) -> bool:
        """
        处理单篇文章：获取详情、解析、保存
        """
        logger.info(f"正在处理文章: {title}")
        
        try:
            # 获取文章详情页 HTML
            article_html = None
            try:
                # 尝试 requests
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    article_html = response.text
            except Exception as e:
                logger.error(f"获取文章内容失败: {url} - {e}")
            
            if not article_html:
                return False
            
            # 解析内容
            content, pub_date = self._parse_article_content(url, article_html)
            
            # 如果没从页面解析到日期，尝试从 API 数据中找补（暂未传入，可优化）
            # 目前 _parse_article_content 里的提取逻辑已经很强了
            
            # 保存
            update = {
                'source_url': url,
                'title': title,
                'content': content,
                'publish_date': pub_date.replace('_', '-') if pub_date else '',
                'product_name': 'GCP Networking'
            }
            
            if self.save_update(update):
                saved_files.append(url)
                logger.info(f"✓ 文章已保存: {title}")
                return True
                
        except Exception as e:
            logger.error(f"处理文章出错: {title} - {e}")
            
        return False

    # -------------------------------------------------------------------------
    # 下面保留原有的详情页解析辅助方法 (HTML -> Markdown, Date Extraction)
    # -------------------------------------------------------------------------
    
    def _parse_article_content(self, url: str, html: str) -> Tuple[str, Optional[str]]:
        """
        从文章页面解析文章内容和发布日期
        """
        soup = BeautifulSoup(html, 'lxml')
        pub_date = self._extract_article_date_enhanced(soup, html, url)
        article_content = self._extract_article_content(soup)
        return article_content, pub_date
    
    def _extract_article_date_enhanced(self, soup: BeautifulSoup, html: str, url: str = None) -> str:
        """增强版日期提取"""
        date_format = "%Y_%m_%d"
        
        # 1. XPath 提取
        try:
            html_tree = etree.HTML(html)
            if html_tree is not None:
                date_elements = html_tree.xpath('/html/body/c-wiz/div/div/article/section[1]/div/div[3]')
                if date_elements:
                    date_text = ''.join(date_elements[0].itertext()).strip()
                    date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})', date_text)
                    if date_match:
                        month, day, year = date_match.groups()
                        month_dict = {
                            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                        }
                        month_num = month_dict.get(month)
                        if month_num:
                            return datetime.datetime(int(year), month_num, int(day)).strftime(date_format)
        except Exception:
            pass
        
        # 2. 标准提取
        standard_date = self._extract_article_date(soup)
        if standard_date:
            try:
                for date_pattern in ['%Y-%m-%d', '%Y/%m/%d', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y']:
                    try:
                        date_part = standard_date.split('T')[0] if 'T' in standard_date else standard_date
                        return datetime.datetime.strptime(date_part, date_pattern).strftime(date_format)
                    except ValueError:
                        continue
            except Exception:
                pass
        
        # 3. URL 提取
        if url:
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/', url)
            if url_date_match:
                try:
                    year, month = url_date_match.groups()
                    return datetime.datetime(int(year), int(month), 1).strftime(date_format)
                except ValueError:
                    pass
        
        return datetime.datetime.now().strftime(date_format)
    
    def _extract_article_date(self, soup: BeautifulSoup) -> Optional[str]:
        """提取日期辅助方法"""
        time_tag = soup.find('time')
        if time_tag:
            return time_tag.get('datetime') or time_tag.get_text(strip=True)
        
        time_role = soup.select_one('[role="time"]')
        if time_role:
            return time_role.get_text(strip=True)
            
        for meta_name in ['publish_date', 'article:published_time', 'date']:
            meta = soup.find('meta', attrs={'name': meta_name}) or soup.find('meta', attrs={'property': meta_name})
            if meta and meta.get('content'):
                return meta.get('content')
                
        date_patterns = [
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{4}-\d{1,2}-\d{1,2}\b'
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, str(soup))
            if date_match:
                return date_match.group(0)
        return None
    
    def _extract_article_content(self, soup: BeautifulSoup) -> str:
        """提取文章正文并转 Markdown"""
        content_elem = soup.find('article') or soup.select_one('[role="main"]') or soup.find('main')
        
        if not content_elem:
            # 兜底：找段落最多的 div
            divs = soup.find_all('div')
            if divs:
                content_divs = [(div, len(div.find_all('p'))) for div in divs if len(div.find_all('p')) >= 3]
                if content_divs:
                    content_elem = max(content_divs, key=lambda x: x[1])[0]
        
        if not content_elem:
            content_elem = soup.body
            
        if content_elem:
            content_elem = BeautifulSoup(str(content_elem), 'lxml')
            for selector in ['nav', 'header', 'footer', 'aside', '[role="complementary"]', '[role="navigation"]']:
                for el in content_elem.select(selector):
                    el.decompose()
            
            self._fix_images_and_links(content_elem)
            content_html = str(content_elem)
            content_markdown = self.html_converter.handle(content_html)
            return self._clean_markdown(content_markdown)
            
        return "无法提取文章内容。"

    def _fix_images_and_links(self, content_elem: BeautifulSoup) -> None:
        """修复图片和链接"""
        # 图片
        for img in content_elem.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if not src and img.get('srcset'):
                src = img.get('srcset').split(',')[0].strip().split(' ')[0]
            
            if src:
                if not src.startswith(('http', '//')):
                    src = urljoin(self.start_url, src)
                if src.startswith('//'):
                    src = 'https:' + src
                if src.startswith('data:'): continue
                
                alt = img.get('alt', '')
                img.replace_with(BeautifulSoup(f'![{alt}]({src})', 'html.parser'))
        
        # 链接
        for a in content_elem.find_all('a'):
            href = a.get('href', '')
            if href and not href.startswith('#'):
                if not href.startswith(('http', '//')):
                    href = urljoin(self.start_url, href)
                if href.startswith('//'):
                    href = 'https:' + href
                text = a.get_text().strip() or href
                a.replace_with(BeautifulSoup(f'[{text}]({href})', 'html.parser'))

    def _clean_markdown(self, markdown_content: str) -> str:
        """清理 Markdown"""
        # 移除社交分享
        patterns = [
            r'\* \[ \]\(https?://(?:x|twitter|linkedin|facebook)\.com/[^\)]+\)\s*',
            r'#{1,6}\s*Related articles[\s\S]+$',
            r'#{1,6}\s*Share\s*\n[\s\S]*?(?=\n#{1,6}|\Z)',
            r'\*\*\s*Get started with Google Cloud\s*\*\*[\s\S]*?(?=\n#{1,6}|Learn more|\Z)',
            r'\n{3,}' # 多余空行
        ]
        for p in patterns:
            markdown_content = re.sub(p, '', markdown_content, flags=re.IGNORECASE)
            
        return markdown_content.strip()
    
    def _normalize_url(self, href: str) -> str:
        if href.startswith('http'): return href
        return urljoin(self.start_url, href)