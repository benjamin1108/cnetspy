#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AWS What's New爬虫
完全使用新的数据存储方式，每条更新独立保存
"""

import logging
import os
import re
import sys
import time
import hashlib
import datetime
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
import html2text

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class AwsWhatsnewCrawler(BaseCrawler):
    """AWS What's New爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化AWS What's New爬虫"""
        super().__init__(config, vendor, source_type)
        
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.start_url = self.source_config.get('url')
        self.max_pages = self.crawler_config.get('article_limit')  # 从配置读取
        
        logger.info(f"AWS What's New爬虫初始化完成，最大文章数: {self.max_pages}")
    
    def _parse_api_date(self, timestamp: Any) -> str:
        """
        解析API返回的时间戳
        
        Args:
            timestamp: ISO 8601格式时间字符串（如 2025-11-24T08:00:00Z）
            
        Returns:
            标准化的日期 (YYYY-MM-DD格式)
        """
        try:
            if timestamp:
                # 处理ISO 8601格式的时间字符串
                if isinstance(timestamp, str):
                    # 移除Z后缀并解析
                    timestamp_str = timestamp.replace('Z', '+00:00')
                    dt = datetime.datetime.fromisoformat(timestamp_str)
                    return dt.strftime('%Y-%m-%d')  # 返回完整日期
                # 如果是数字，按Unix时间戳处理
                else:
                    dt = datetime.datetime.fromtimestamp(int(timestamp))
                    return dt.strftime('%Y-%m-%d')  # 返回完整日期
        except Exception as e:
            logger.debug(f"解析时间戳失败: {timestamp}, 错误: {e}")
        
        # 默认当前日期
        return datetime.date.today().strftime('%Y-%m-%d')
    
    def _extract_product_from_tags(self, tags: List[Dict[str, Any]]) -> str:
        """
        从tags中提取产品名称
        
        Args:
            tags: API返回的tags列表
            
        Returns:
            产品名称
        """
        # 找到tagNamespaceId为"whats-new-v2#general-products"的tag
        products = []
        for tag in tags:
            if isinstance(tag, dict):
                namespace_id = tag.get('tagNamespaceId', '')
                if namespace_id == 'whats-new-v2#general-products':
                    # name字段就是产品名，例如"amazon-vpc"
                    product = tag.get('name', '')
                    if product:
                        # 转换为可读格式："amazon-vpc" -> "Amazon VPC"
                        product = product.replace('-', ' ').title()
                        products.append(product)
        
        # 如果有多个产品，用逗号连接
        if products:
            return ', '.join(products[:3])  # 最変3个
        else:
            # 如果没有产品tag，返回通用名称
            return 'AWS Networking & Content Delivery'
        
    def _get_identifier_strategy(self) -> str:
        """AWS使用API-based策略"""
        return 'api_based'
        
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        AWS whatsnew: hash(api_base + url)
            
        Args:
            update: 更新数据字典
                
        Returns:
            [api_base, url]
        """
        api_base = "https://aws.amazon.com/api/dirs/items/search"
        url = update.get('source_url', '')
        return [api_base, url]
    
    def _crawl(self) -> List[str]:
        """
        爬取AWS What's New
        
        Returns:
            保存的文件路径列表
        """
        if not self.start_url:
            logger.error("未配置起始URL")
            return []
        
        saved_files = []
        all_updates = []
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        try:
            # 直接使用API获取公告列表（不需要爬取页面）
            logger.info(f"使用API获取AWS What's New列表")
            
            # 解析公告链接（内部使用API）
            article_links = self._parse_article_links(None)
            logger.info(f"解析到 {len(article_links)} 篇公告链接")
            
            # 限制爬取数量
            article_links = article_links[:self.max_pages]
            logger.info(f"限制爬取 {len(article_links)} 篇公告")
            
            # 过滤已存在的更新（检查数据库）
            articles_to_crawl = []
            for title, url, publish_date, product_name, content in article_links:
                # 生成临时update字典用于identifier生成
                temp_update = {'source_url': url}
                source_identifier = self.generate_source_identifier(temp_update)
                
                # 检查数据库是否已存在
                if not force_mode and self.check_exists_in_db(url, source_identifier):
                    logger.debug(f"跳过已存在: {title}")
                else:
                    articles_to_crawl.append((title, url, publish_date, product_name, content))
            
            logger.info(f"需要爬取 {len(articles_to_crawl)} 篇新公告，跳过 {len(article_links) - len(articles_to_crawl)} 篇已存在公告")
            
            # 使用线程池并行爬取
            if articles_to_crawl:
                max_workers = min(10, len(articles_to_crawl))  # 最多10个并发
                logger.info(f"使用 {max_workers} 个线程并行爬取")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有任务
                    future_to_article = {
                        executor.submit(self._crawl_article, title, url, publish_date, product_name, content): (title, url)
                        for title, url, publish_date, product_name, content in articles_to_crawl
                    }
                    
                    # 处理完成的任务
                    completed = 0
                    for future in concurrent.futures.as_completed(future_to_article):
                        title, url = future_to_article[future]
                        completed += 1
                        try:
                            update = future.result()
                            if update:
                                all_updates.append(update)
                                logger.info(f"[{completed}/{len(articles_to_crawl)}] 成功: {title}")
                            else:
                                logger.warning(f"[{completed}/{len(articles_to_crawl)}] 失败: {title}")
                        except Exception as e:
                            logger.error(f"[{completed}/{len(articles_to_crawl)}] 异常 [{title}]: {e}")
            
            logger.info(f"总共收集到 {len(all_updates)} 条AWS更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    success = self._save_update(update)
                    if success:
                        saved_files.append(update.get('source_url', ''))
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个AWS更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取AWS What's New时发生错误: {e}")
            return saved_files
        finally:
            self._close_driver()
    
    def _parse_article_links(self, html: str) -> List[Tuple[str, str, str, str, str]]:
        """
        通过AWS API获取What's New公告列表
        
        Args:
            html: 未使用（保持接口一致）
            
        Returns:
            (title, url, publish_date, product_name, content)元组列表
        """
        articles = []
        
        try:
            # 使用AWS What's New API端点
            api_url = "https://aws.amazon.com/api/dirs/items/search"
            params = {
                "item.directoryId": "whats-new-v2",
                "sort_by": "item.additionalFields.postDateTime",
                "sort_order": "desc",
                "size": "100",
                "item.locale": "en_US",
                # 网络产品过滤：具体产品 tag + 大类 tag（networking/networking-and-content-delivery）
                # 大类 tag 会带来一些边缘案例，AI 分析时会判断 subcategory 为空，后续通过 check --clean-empty 清理
                "tags.id": "whats-new-v2#general-products#amazon-vpc|whats-new-v2#general-products#aws-direct-connect|whats-new-v2#general-products#amazon-route-53|whats-new-v2#general-products#elastic-load-balancing|whats-new-v2#general-products#amazon-cloudfront|whats-new-v2#general-products#amazon-api-gateway|whats-new-v2#marketing-marchitecture#networking|whats-new-v2#marketing-marchitecture#networking-and-content-delivery|whats-new-v2#general-products#aws-global-accelerator|whats-new-v2#general-products#aws-transit-gateway|whats-new-v2#general-products#aws-vpn|whats-new-v2#general-products#aws-site-to-site|whats-new-v2#general-products#aws-client-vpn|whats-new-v2#general-products#aws-app-mesh|whats-new-v2#general-products#aws-privatelink|whats-new-v2#general-products#aws-network-firewall|whats-new-v2#general-products#amazon-vpc-lattice"
            }
            
            page = 0
            total_items = 0
            
            while True:
                params["page"] = str(page)
                logger.debug(f"请求AWS What's New API，第 {page} 页")
                
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    response = requests.get(api_url, params=params, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("items"):
                            page_items = data["items"]
                            
                            for item in page_items:
                                item_data = item.get("item", {})
                                additional_fields = item_data.get("additionalFields", {})
                                # tags在外层，不在item.item里
                                tags = item.get("tags", [])
                                
                                headline = additional_fields.get("headline", "")
                                url_path = additional_fields.get("headlineUrl", "")
                                post_date_time = additional_fields.get("postDateTime", "")
                                # API返回的完整HTML内容
                                post_body = additional_fields.get("postBody", "")
                                
                                # 从tags中提取产品名称
                                product_name = self._extract_product_from_tags(tags)
                                
                                if headline and url_path:
                                    # 确保URL完整
                                    if not url_path.startswith("http"):
                                        if not url_path.startswith("/"):
                                            url_path = "/" + url_path
                                        full_url = f"https://aws.amazon.com{url_path}"
                                    else:
                                        full_url = url_path
                                    
                                    # 解析日期 (postDateTime格式: 1732060800 Unix时间戳)
                                    publish_date = self._parse_api_date(post_date_time)
                                    
                                    articles.append((headline, full_url, publish_date, product_name, post_body))
                            
                            total_items += len(page_items)
                            logger.debug(f"从API第 {page} 页获取到 {len(page_items)} 篇公告，累计 {total_items} 篇")
                            
                            # 检查是否还有更多数据或达到限制
                            if len(page_items) < int(params["size"]) or total_items >= self.max_pages:
                                logger.info(f"API数据获取完成，共 {total_items} 篇公告")
                                break
                            
                            page += 1
                        else:
                            logger.warning(f"API第 {page} 页响应中没有找到公告项")
                            break
                    else:
                        logger.error(f"API请求失败，状态码: {response.status_code}")
                        break
                        
                except Exception as e:
                    logger.error(f"API请求异常: {e}")
                    break
            
            logger.info(f"通过API获取到 {len(articles)} 条公告")
            return articles[:self.max_pages]
            
        except Exception as e:
            logger.error(f"API爬取出错: {e}")
            return []
    
    def _crawl_article(self, title: str, url: str, publish_date: str, product_name: str, html_content: str) -> Optional[Dict[str, Any]]:
        """
        处理单篇公告（使用API返回的内容）
        
        Args:
            title: 公告标题
            url: 公告URL
            publish_date: 发布日期（从API获取）
            product_name: 产品名称（从tags提取）
            html_content: HTML内容（从API获取）
            
        Returns:
            更新条目字典
        """
        try:
            # 直接使用API返回的HTML内容，不需要再爬取页面
            if not html_content:
                logger.warning(f"API返回的内容为空: {url}")
                return None
            
            # 解析HTML内容
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 提取纯文本内容
            content = self._extract_content(soup)
            
            # 生成 source_identifier（API base URL + URL path hash）
            api_base = "https://aws.amazon.com/api/dirs/items/search"
            identifier_content = f"{api_base}|{url}"
            source_identifier = hashlib.md5(identifier_content.encode('utf-8')).hexdigest()[:12]
            
            # 构建更新条目
            update = {
                'title': title,
                'description': content[:500] if content else '',  # 前500字符作为描述
                'content': content,
                'publish_date': publish_date,  # 使用从API获取的日期
                'source_url': url,
                'source_identifier': source_identifier,
                'product_name': product_name  # 使用从tags提取的产品名
            }
            
            return update
            
        except Exception as e:
            logger.error(f"爬取公告详情失败 [{title}]: {e}")
            return None
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取公告内容
        
        API返回的postBody本身就是内容，直接转换为Markdown
        """
        try:
            # 移除不需要的元素
            for unwanted in soup.find_all(['script', 'style']):
                unwanted.decompose()
            
            # 转换为Markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            
            content = h.handle(str(soup))
            return content.strip()
        except Exception as e:
            logger.debug(f"提取内容失败: {e}")
        
        return soup.get_text(strip=True) if soup else ""
    
    def _save_update(self, update: Dict[str, Any]) -> bool:
        """
        保存单条更新（使用基类方法）
        
        Args:
            update: 更新条目
            
        Returns:
            是否成功
        """
        try:
            # 直接调用基类的 save_update 方法，基类会统一生成元数据头
            success = self.save_update(update)
            
            if success:
                logger.debug(f"保存更新: {update.get('title', '')}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存更新失败: {e}")
            return False


if __name__ == '__main__':
    """测试爬虫"""
    from src.utils.config.config_loader import get_config
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = get_config()
    crawler = AwsWhatsnewCrawler(config, 'aws', 'whatsnew')
    crawler.run()
