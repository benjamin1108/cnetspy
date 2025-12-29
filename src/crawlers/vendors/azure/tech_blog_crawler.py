#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import re
import time
import json
import hashlib
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from src.crawlers.common.base_crawler import BaseCrawler
from src.crawlers.common.content_parser import DateExtractor

logger = logging.getLogger(__name__)

class AzureTechBlogCrawler(BaseCrawler):
    """Azure技术博客爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化爬虫"""
        super().__init__(config, vendor, source_type)
        
        # 获取源配置
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.start_url = self.source_config.get('url')
        
        # 如果未指定URL，使用默认值
        if not self.start_url:
            self.start_url = "https://techcommunity.microsoft.com/t5/azure-networking-blog/bg-p/AzureNetworkingBlog"
        
        # 初始化代理配置
        self._init_proxy_config()
    
    def _init_proxy_config(self) -> None:
        """初始化代理配置"""
        self.proxy_config = self.source_config.get('proxy', {})
        # 处理字符串形式的布尔值 (从环境变量读取时是字符串)
        enabled_value = self.proxy_config.get('enabled', False)
        if isinstance(enabled_value, str):
            self.use_proxy = enabled_value.lower() == 'true'
        else:
            self.use_proxy = bool(enabled_value)
        
        if self.use_proxy:
            proxy_host = self.proxy_config.get('host', '')
            proxy_port = self.proxy_config.get('port', '')
            proxy_username = self.proxy_config.get('username', '')
            proxy_password = self.proxy_config.get('password', '')
            
            if proxy_host and proxy_port:
                # 构建代理URL (用于requests)
                if proxy_username and proxy_password:
                    self.proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
                else:
                    self.proxy_url = f"http://{proxy_host}:{proxy_port}"
                
                # 构建requests的proxies字典
                self.proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                
                # 保存Playwright代理配置
                self.playwright_proxy = {
                    'server': f"http://{proxy_host}:{proxy_port}"
                }
                if proxy_username and proxy_password:
                    self.playwright_proxy['username'] = proxy_username
                    self.playwright_proxy['password'] = proxy_password
                
                logger.info(f"已启用代理: {proxy_host}:{proxy_port}")
            else:
                self.use_proxy = False
                self.proxy_url = None
                self.proxies = None
                self.playwright_proxy = None
                logger.warning("代理配置不完整，已禁用代理")
        else:
            self.proxy_url = None
            self.proxies = None
            self.playwright_proxy = None
            logger.debug("未启用代理，使用直连")
    
    
    def _get_identifier_strategy(self) -> str:
        """Azure Tech Blog使用url-based策略"""
        return 'url_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """Azure Tech Blog: hash(source_url)"""
        return [update.get('source_url', '')]
    
    def _crawl(self) -> List[str]:
        """爬取Azure技术博客"""
        saved_files = []
        
        try:
            # 获取博客列表页
            logger.info(f"获取Azure技术博客列表页: {self.start_url}")
            
            # TechCommunity站点需要JS渲染且有反爬虫机制，直接使用Playwright
            html = None
            try:
                logger.debug("使用Playwright获取页面内容（绕过反爬虫）")
                html = self._get_with_playwright(self.start_url)
            except Exception as e:
                logger.warning(f"使用Playwright获取页面失败: {e}，将尝试使用备用URL")
                # 尝试备用URL
                try:
                    backup_url = "https://techcommunity.microsoft.com/t5/azure-networking-blog/bg-p/AzureNetworkingBlog"
                    if backup_url != self.start_url:
                        logger.debug(f"尝试使用备用URL: {backup_url}")
                        html = self._get_with_playwright(backup_url)
                except Exception as backup_e:
                    logger.error(f"使用备用URL获取页面失败: {backup_e}")
            
            if not html:
                logger.error(f"获取博客列表页失败: {self.start_url}")
                return []
            
            # 获取所有文章链接
            all_article_info = []
            
            # 解析第一页博客列表
            article_info = self._parse_article_links(html)
            logger.info(f"首页解析到 {len(article_info)} 篇文章链接")
            all_article_info.extend(article_info)
            
            # 禁用分页功能，只处理首页文章
            logger.info("根据要求，仅抓取首页显示的文章，跳过分页操作")
            
            # 如果是测试模式或有文章数量限制，截取所需数量的文章链接
            test_mode = self.source_config.get('test_mode', False)
            # 将默认的文章数量限制从50改为10
            article_limit = self.crawler_config.get('article_limit')
            
            if test_mode:
                logger.info("爬取模式：限制爬取1篇文章")
                all_article_info = all_article_info[:1]
            elif article_limit > 0:
                logger.info(f"爬取模式：限制爬取{article_limit}篇文章")
                all_article_info = all_article_info[:article_limit]
            
            logger.info(f"共有 {len(all_article_info)} 篇文章等待检查")
            
            # 设置发现总数
            self.set_total_discovered(len(all_article_info))
            
            # 检查是否启用强制模式
            force_mode = self.crawler_config.get('force', False)
            
            # 过滤已存在的文章链接
            filtered_article_info = []
            
            for title, url, list_date in all_article_info:
                if force_mode:
                    filtered_article_info.append((title, url, list_date))
                else:
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
                        filtered_article_info.append((title, url, list_date))
            
            if force_mode:
                logger.info(f"强制模式已启用，将重新爬取所有 {len(filtered_article_info)} 篇文章")
            else:
                logger.info(f"过滤后: {len(filtered_article_info)} 篇新文章需要爬取")
            
            # 爬取每篇新文章
            for idx, (title, url, list_date) in enumerate(filtered_article_info, 1):
                logger.info(f"正在爬取第 {idx}/{len(filtered_article_info)} 篇文章: {title}")
                
                try:
                    # 尝试获取文章内容 - 优先使用requests
                    article_html = None
                    try:
                        if self.use_proxy and self.proxies:
                            logger.debug(f"使用requests库获取文章内容(通过代理): {url}")
                        else:
                            logger.debug(f"使用requests库获取文章内容: {url}")
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                        # 如果启用代理，使用代理进行请求
                        if self.use_proxy and self.proxies:
                            response = requests.get(url, headers=headers, timeout=30, proxies=self.proxies)
                        else:
                            response = requests.get(url, headers=headers, timeout=30)
                        if response.status_code == 200:
                            article_html = response.text
                            logger.debug("使用requests库成功获取到文章内容")
                        else:
                            logger.error(f"请求返回非成功状态码: {response.status_code}")
                    except Exception as e:
                        logger.error(f"使用requests库获取文章失败: {e}")
                    
                    # 如果requests失败，才尝试Playwright
                    if not article_html:
                        try:
                            article_html = self._get_with_playwright(url)
                        except Exception as e:
                            logger.warning(f"使用Playwright获取文章失败: {e}")
                    
                    if not article_html:
                        logger.warning(f"获取文章内容失败: {url}")
                        continue
                    
                    # 解析文章内容和日期
                    article_content, pub_date = self._parse_article_content(url, article_html, list_date)
                    
                    # 构建 update 字典并调用 save_update
                    update = {
                        'source_url': url,
                        'title': title,
                        'content': article_content,
                        'publish_date': pub_date.replace('_', '-') if pub_date else '',
                        'product_name': 'Azure Networking'
                    }
                    success = self.save_update(update)
                    if success:
                        saved_files.append(url)
                    logger.info(f"已保存文章: {title}")
                    
                    # 间隔一段时间再爬取下一篇
                    if idx < len(filtered_article_info):
                        time.sleep(self.interval)
                    
                except Exception as e:
                    logger.error(f"爬取文章失败: {url} - {e}")
            
            return saved_files
        except Exception as e:
            logger.error(f"爬取Azure技术博客过程中发生错误: {e}")
            return saved_files
        finally:
            # 关闭WebDriver
            self._close_driver()
            
    def _get_with_playwright(self, url: str, max_retries: int = 3) -> str:
        """
        使用Playwright获取页面内容（带反检测和代理支持）
        
        Args:
            url: 页面URL
            max_retries: 最大重试次数
            
        Returns:
            页面HTML内容
        """
        from playwright.sync_api import sync_playwright
        import time
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 5 * attempt
                    logger.info(f"Playwright 第 {attempt + 1} 次重试，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                
                if self.use_proxy:
                    logger.debug(f"使用Playwright获取页面(通过代理): {url}")
                else:
                    logger.debug(f"使用Playwright获取页面: {url}")
                
                # 每次重试都创建新的 Playwright 上下文
                with sync_playwright() as p:
                    launch_args = {
                        'headless': True,
                        'args': [
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-blink-features=AutomationControlled',
                            '--disable-infobars',
                            '--window-size=1920,1080',
                            '--disable-extensions',
                            '--disable-plugins-discovery',
                            '--start-maximized'
                        ]
                    }
                    
                    if self.use_proxy and self.playwright_proxy:
                        launch_args['proxy'] = self.playwright_proxy
                        logger.debug(f"Playwright代理配置: {self.playwright_proxy.get('server', '')}")
                    
                    browser = p.chromium.launch(**launch_args)
                    try:
                        context = browser.new_context(
                            viewport={'width': 1920, 'height': 1080},
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            locale='en-US',
                            timezone_id='America/New_York',
                            permissions=['geolocation'],
                            java_script_enabled=True,
                            bypass_csp=True,
                            extra_http_headers={
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9',
                                'Accept-Encoding': 'gzip, deflate, br',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Sec-Fetch-Dest': 'document',
                                'Sec-Fetch-Mode': 'navigate',
                                'Sec-Fetch-Site': 'none',
                                'Sec-Fetch-User': '?1',
                                'Cache-Control': 'max-age=0'
                            }
                        )
                        
                        page = context.new_page()
                        
                        page.add_init_script("""
                            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                            window.chrome = { runtime: {} };
                        """)
                        
                        page.goto(url, wait_until='load', timeout=60000)
                        page.wait_for_timeout(3000)
                        
                        page.mouse.move(100, 200)
                        page.wait_for_timeout(500)
                        page.mouse.move(300, 400)
                        
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                        page.wait_for_timeout(1500)
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        page.wait_for_timeout(1500)
                        page.evaluate('window.scrollTo(0, 0)')
                        page.wait_for_timeout(1000)
                        
                        html = page.content()
                        logger.info(f"成功获取页面内容，大小: {len(html)} 字节")
                        
                        if len(html) < 1000:
                            logger.warning(f"页面内容过小({len(html)}字节)，可能被反爬虫拦截")
                        
                        context.close()
                        return html
                    finally:
                        browser.close()
                        
            except Exception as e:
                last_error = e
                logger.warning(f"Playwright 第 {attempt + 1}/{max_retries} 次尝试失败: {e}")
                continue
        
        logger.error(f"Playwright 获取页面内容失败（已重试 {max_retries} 次）: {last_error}")
        import traceback
        logger.error(traceback.format_exc())
        raise last_error
    
    def _parse_article_links(self, html: str) -> List[Tuple[str, str, Optional[str]]]:
        """
        解析HTML，提取文章链接
        
        Args:
            html: 页面HTML内容
            
        Returns:
            提取的文章链接列表，每个元素为 (标题, URL, 日期) 三元组
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            processed_articles = []
        
            # 调试信息
            debug_info = {
                "candidates": [],
                "accepted": [],
                "rejected": [],
                "final_count": 0
            }
            
            logger.info("开始基于DOM结构解析Azure博客文章...")
            
            # 1. 首先尝试通过MessageViewCard类来识别文章卡片 - TechCommunity站点特有的类
            article_cards = soup.select('.MessageViewCard_lia-message__6_xUN, article.styles_lia-g-card__y_snR')
            
            if article_cards:
                logger.info(f"找到 {len(article_cards)} 篇文章卡片(通过MessageViewCard类)")
                debug_info["candidates"].append({
                    "selector": ".MessageViewCard_lia-message__6_xUN, article.styles_lia-g-card__y_snR",
                    "count": len(article_cards),
                    "elements": [{"tag": card.name, "class": str(card.get("class", []))} for card in article_cards[:5]] + (["..."] if len(article_cards) > 5 else [])
                })
            else:
                # 2. 如果没有找到特定类的文章卡片，尝试通过点赞/反馈按钮来识别文章
                logger.info("未找到MessageViewCard类文章卡片，尝试通过点赞/反馈按钮识别文章...")
                
                # 查找所有含有点赞图标或反馈按钮的容器
                like_containers = soup.select('[aria-label*="like"], [aria-label*="赞"], [data-testid*="like"], .KudoButton, .like-button')
                
                # 从点赞按钮向上查找包含文章的父容器
                article_cards = []
                for like_button in like_containers:
                    # 向上查找3层，寻找可能的文章容器
                    parent = like_button.parent
                    for _ in range(3):  # 最多向上查找3层
                        if not parent:
                            break
                            
                        # 检查是否是文章容器
                        if parent.name == 'article' or (parent.get('class') and any(c.lower() in ['card', 'article', 'post', 'message'] for c in parent.get('class'))):
                            if parent not in article_cards:  # 避免重复
                                article_cards.append(parent)
                                break
                                
                        parent = parent.parent
                
                if article_cards:
                    logger.info(f"找到 {len(article_cards)} 篇文章(通过点赞按钮)")
                    debug_info["candidates"].append({
                        "selector": "通过点赞按钮识别",
                        "count": len(article_cards),
                        "elements": [{"tag": card.name, "class": str(card.get("class", []))} for card in article_cards[:5]] + (["..."] if len(article_cards) > 5 else [])
                    })
                else:
                    # 3. 如果通过点赞按钮也找不到，尝试基于文章卡片的通用特征
                    logger.info("未通过点赞按钮找到文章，尝试基于通用文章卡片特征...")
                    
                    # 查找结构化的卡片元素
                    card_candidates = soup.select('article, .card, .article-card, .post-card, .blog-card, .message-card, .entry')
                    
                    # 过滤出真正的文章卡片
                    for card in card_candidates:
                        # 检查是否包含标题和链接
                        has_title = bool(card.select_one('h1, h2, h3, h4, h5, .title, .subject'))
                        has_link = bool(card.select_one('a[href]'))
                        
                        # 检查是否包含其他文章特征元素
                        has_date = bool(card.select_one('time, .date, .meta-date, .timestamp'))
                        has_content = bool(card.select_one('p, .content, .description, .excerpt'))
                        
                        # 如果具备文章特征，添加到文章列表
                        if has_title and has_link and (has_date or has_content):
                            article_cards.append(card)
                    
                    if article_cards:
                        logger.info(f"找到 {len(article_cards)} 篇文章(通过通用文章卡片特征)")
                        debug_info["candidates"].append({
                            "selector": "通过通用文章卡片特征",
                            "count": len(article_cards),
                            "elements": [{"tag": card.name, "class": str(card.get("class", []))} for card in article_cards[:5]] + (["..."] if len(article_cards) > 5 else [])
                        })
            
            # 如果未找到任何文章卡片，尝试解析整个页面
            if not article_cards:
                logger.warning("未找到任何文章卡片，尝试提取页面中的所有链接")
                
                # 提取页面中的所有链接
                all_links = soup.find_all('a', href=True)
                
                # 筛选出可能是文章的链接
                for link in all_links:
                    href = link.get('href', '')
                    # 构建完整URL
                    url = href if href.startswith('http') else urljoin(self.start_url, href)
                    
                    # 只接受Azure网络博客链接
                    if '/blog/azurenetworkingblog/' in url:
                        title = link.get_text(strip=True)
                        title = self._clean_title(title)  # 清理标题，移除"MIN READ"等无关信息
                        if not title:
                            # 尝试从title属性或父元素获取标题
                            title = link.get('title', '') or link.get('aria-label', '')
                            if not title and link.parent:
                                title_elem = link.parent.find(['h1', 'h2', 'h3', 'h4', 'h5'])
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    title = self._clean_title(title)  # 清理标题，移除"MIN READ"等无关信息
                        
                        if title and len(title) > 10 and ' ' in title:
                            # 避免URL重复
                            if url not in [a[1] for a in processed_articles]:
                                processed_articles.append((title, url, None))
                                debug_info["accepted"].append({
                                    "title": title,
                                    "url": url
                                })
                
                logger.debug(f"从所有链接中提取到 {len(processed_articles)} 篇文章")
                debug_info["final_count"] = len(processed_articles)

                return processed_articles
                
            # 处理找到的文章卡片
            item_details = []
            for i, card in enumerate(article_cards):
                item_detail = {
                    "index": i,
                    "tag": card.name,
                    "classes": str(card.get("class", [])),
                    "id": card.get("id", "")
                }
                
                # 添加调试信息：保存卡片的HTML结构
                if i < 2:  # 只保存前两个卡片的结构以避免调试信息过大
                    item_detail["html_structure"] = str(card)[:500] + "..." if len(str(card)) > 500 else str(card)
                
                # 提取标题
                title_elem = card.select_one('h1, h2, h3, h4, h5, .title, .subject, [class*="subject"], [class*="title"], .lia-message-subject, .MessageSubject, [data-testid="card-title"]')
                title = None
                
                # 首先检查是否有带aria-label的链接
                message_links = card.select('a[aria-label][data-testid="MessageLink"]')
                if message_links and message_links[0].get('aria-label'):
                    title = message_links[0].get('aria-label')
                    logger.debug(f"从aria-label中提取到标题: {title}")
                
                # 如果没有从aria-label获取到标题，再尝试使用标题元素
                if not title and title_elem:
                    title = title_elem.get_text(strip=True)
                
                # 如果还是找不到标题，尝试更通用的方法
                if not title:
                    # 尝试其他链接
                    links = card.select('a')
                    for link in links:
                        # 先检查aria-label
                        aria_label = link.get('aria-label')
                        if aria_label and len(aria_label) > 10:
                            title = aria_label
                            logger.debug(f"从链接的aria-label中提取到标题: {title}")
                            break
                        
                        # 再检查链接文本
                        link_text = link.get_text(strip=True)
                        if len(link_text) > 10 and ' ' in link_text:
                            title = link_text
                            logger.debug(f"从链接文本中提取到标题: {title}")
                            break
                
                # 清理标题
                if title:
                    title = self._clean_title(title)
                
                if not title or len(title) < 5:  # 非常短的标题可能是按钮或标签
                    reason = f"标题太短或未找到: {title}"
                    item_detail["status"] = "rejected"
                    item_detail["reason"] = reason
                    debug_info["rejected"].append({
                        "index": i,
                        "title": title if title else "",
                        "reason": reason
                    })
                    item_details.append(item_detail)
                    continue
                
                item_detail["title"] = title
                if title_elem:
                    item_detail["title_elem"] = f"{title_elem.name}.{str(title_elem.get('class', []))}"
                
                # 提取链接
                link_elem = None
                
                # 首先尝试从MessageLink中获取链接
                message_links = card.select('a[data-testid="MessageLink"]')
                if message_links and message_links[0].get('href'):
                    link_elem = message_links[0]
                    logger.debug(f"从MessageLink中提取到链接: {link_elem.get('href')}")
                
                # 如果没有找到MessageLink，再尝试其他方法
                if not link_elem:
                    if title_elem and title_elem.name == 'a':
                        link_elem = title_elem
                    else:
                        # 首先在标题中查找链接
                        if title_elem:
                            link_elem = title_elem.find('a')
                        
                        # 如果标题中没有链接，在卡片中查找主要链接
                        if not link_elem:
                            card_links = card.find_all('a', href=True)
                            for link in card_links:
                                href = link.get('href', '')
                                if href and '/blog/azurenetworkingblog/' in href:
                                    link_elem = link
                                    break
                            
                            # 如果没有找到符合条件的链接，使用第一个链接
                            if not link_elem and card_links:
                                link_elem = card_links[0]
                
                if not link_elem or not link_elem.get('href'):
                    reason = "找不到有效的链接"
                    item_detail["status"] = "rejected"
                    item_detail["reason"] = reason
                    debug_info["rejected"].append({
                        "index": i,
                        "title": title if title else "",
                        "reason": reason
                    })
                    item_details.append(item_detail)
                    continue
                
                href = link_elem.get('href', '')
                # 构建完整URL
                url = href if href.startswith('http') else urljoin(self.start_url, href)
                
                item_detail["href"] = href
                item_detail["url"] = url
                
                # 对于Azure网络博客，特殊处理
                if '/blog/azurenetworkingblog/' not in url:
                    # 只对非/blog/azurenetworkingblog/链接进行额外验证
                    if self._is_tag_or_category_url(url):
                        reason = f"是标签或分类URL: {url}"
                        item_detail["status"] = "rejected"
                        item_detail["reason"] = reason
                        debug_info["rejected"].append({
                            "index": i,
                            "title": title if title else "",
                            "url": url,
                            "reason": reason
                        })
                        item_details.append(item_detail)
                        continue
                
                # 提取日期信息
                date_elem = card.select_one('time, .date, .meta-date, .timestamp, [data-testid="blog-date"]')
                date_str = None
                
                if date_elem:
                    # 首先尝试从datetime属性获取日期
                    if date_elem.get('datetime'):
                        date_str = date_elem.get('datetime')
                    else:
                        date_str = date_elem.get_text(strip=True)
                    
                    # 解析日期字符串
                    date_str = DateExtractor.parse_date_string(date_str)
                item_detail["date"] = date_str
                
                # 确保URL不重复
                if url in [a[1] for a in processed_articles]:
                    reason = f"URL重复: {url}"
                    item_detail["status"] = "rejected"
                    item_detail["reason"] = reason
                    debug_info["rejected"].append({
                        "index": i,
                        "title": title if title else "",
                        "url": url,
                        "reason": reason
                    })
                    item_details.append(item_detail)
                    continue
                
                # 文章通过所有验证
                processed_articles.append((title, url, date_str))
                item_detail["status"] = "accepted"
                debug_info["accepted"].append({
                    "index": i,
                    "title": title if title else "",
                    "url": url,
                    "date": date_str
                })
                logger.debug(f"添加文章: {title} | {url}")
                item_details.append(item_detail)
            
       
            
            logger.info(f"总共解析到 {len(processed_articles)} 篇文章")
            return processed_articles
            
        except Exception as e:
            logger.error(f"解析文章链接出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [] 

    def _clean_title(self, title: str) -> str:
        """清理标题，移除无关内容"""
        if not title:
            return ""
            
        # 移除常见无关内容
        title = re.sub(r'\b\d+\s+MIN READ\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\b\d+\s+minute read\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Posted on.*?by.*', '', title, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除前后空格和多余空格
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
        
    def _is_tag_or_category_url(self, url: str) -> bool:
        """检查URL是否为标签或分类页面"""
        return bool(re.search(r'/(tags?|categor(y|ies)|topics?|archive)/', url))
        

            

    def _parse_article_content(self, url: str, html: str, list_date: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """解析文章内容和日期"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 提取发布日期
            pub_date = self._extract_publish_date(soup)
            
            # 如果未从文章中获取到日期，使用列表页提供的日期
            if not pub_date:
                pub_date = list_date
            
            # 如果仍然没有日期，则使用当前日期
            if not pub_date:
                pub_date = time.strftime("%Y_%m_%d")
            
            # 提取文章内容
            article_content = "无法提取文章内容"
            
            # 尝试找到文章内容
            content_elem = soup.select_one('main article, #main-content, .lia-message-body-content, .lia-message-body, .message-body, .content-body, .post-body')
            
            if content_elem:
                # 清理非内容元素，但保留正文中的图片
                for elem in content_elem.select('header, footer, nav, .navigation, .sidebar, aside, .ad, .ads, .comments, .social-share, .share-buttons, .author-info, .author-avatar, .avatar, .kudo-button, .like-button, .reaction-button, button, form, input, [class*="tag"], [class*="label"], [href*="/tag/"], [href*="/category/"], [href*="/users/"], [class*="meta"], [class*="info"], [class*="profile"], [class*="join"], [class*="follow"], [class*="subscribe"]'):
                    # 检查元素是否包含图片，如果包含则保留
                    if not elem.find_all('img'):
                        elem.decompose()
                
                # 移除脚本和样式
                for elem in content_elem.find_all(['script', 'style', 'noscript']):
                    elem.decompose()
                
                # 移除非必要的图标和头像图片，但保留正文图片
                for img in content_elem.find_all('img'):
                    src = img.get('src', '')
                    alt = img.get('alt', '')
                    # 移除头像、图标、徽标等非必要图片
                    if any(keyword in src.lower() for keyword in ['avatar', 'icon', 'logo', 'profile']) or \
                       any(keyword in alt.lower() for keyword in ['avatar', 'icon', 'rank', 'microsoft']):
                        img.decompose()
                
                # 移除包含作者头像的链接
                for link in content_elem.find_all('a'):
                    href = link.get('href', '')
                    if '/users/' in href or 'avatar' in str(link).lower():
                        link.decompose()
                
                # 移除"Blog Post"文本
                for elem in content_elem.find_all(string=lambda text: text and "Blog Post" in text):
                    parent = elem.parent
                    if parent:
                        if parent.name in ['h2', 'h3', 'p', 'div', 'span']:
                            parent.decompose()
                        else:
                            # 如果父元素不是我们想要移除的，只移除文本本身
                            elem.replace_with('')
                
                # 移除空元素，但保留包含图片的元素
                for elem in content_elem.find_all(['div', 'span', 'p']):
                    if not elem.get_text(strip=True) and not elem.find_all('img'):
                        elem.decompose()
                
                # 将HTML转换为Markdown
                if self.html_converter:
                    article_content = self.html_converter.handle(str(content_elem))
                    # 进一步清理Markdown内容中的非必要文本
                    article_content = re.sub(r'(?i)\d+\s*(MIN|minute)\s*READ', '', article_content)
                    article_content = re.sub(r'(?i)(Posted|Published|Updated)\s+on\s+.*?(by\s+.*?)?(\n|$)', '', article_content)
                    article_content = re.sub(r'(?i)(Joined|Follow|Subscribe|View\s+Profile).*?(\n|$)', '', article_content)
                    article_content = re.sub(r'(?i)(Share\s+to|Comment).*?(\n|$)', '', article_content)
                    article_content = re.sub(r'\n{3,}', '\n\n', article_content)
                    # 清理未完成的图片链接或格式错误，但保留有效的图片链接
                    article_content = re.sub(r'\[ !\[(?:[^\]]*)\](?!\(\S*\))', '', article_content)
                    article_content = re.sub(r'\[ !\](?!\(\S*\))', '', article_content)
                    article_content = re.sub(r'(?:\*|\s)*\[ !\[(?:[^\]]*)\](?!\(\S*\))(?:(?:\*|\s)*|$)', '', article_content)
                    article_content = re.sub(r'(?:\*|\s)*\[ !\](?!\(\S*\))(?:(?:\*|\s)*|$)', '', article_content)
                    # 截断 Version 字段之后的内容
                    version_match = re.search(r'(Version\s+\d+\.\d+)', article_content, re.IGNORECASE)
                    if version_match:
                        version_index = article_content.find(version_match.group(0)) + len(version_match.group(0))
                        article_content = article_content[:version_index]
                else:
                    # 简单的HTML到文本转换
                    article_content = content_elem.get_text("\n\n", strip=True)
            else:
                logger.warning(f"无法找到文章内容元素: {url}")
            
            return article_content, pub_date
        except Exception as e:
            logger.error(f"解析文章内容失败: {url} - {e}")
            return f"解析内容出错: {str(e)}", None
            
    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[str]:
        """从文章页面提取发布日期"""
        # 尝试各种可能的日期选择器
        date_selectors = [
            'time', 
            '[data-testid="blog-date"]',
            '.date', 
            '.meta-date', 
            '.timestamp',
            '.published-date',
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            '.lia-message-posted-on'
        ]
        
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                date_str = None
                if date_elem.name == 'meta':
                    date_str = date_elem.get('content')
                elif date_elem.get('datetime'):
                    date_str = date_elem.get('datetime')
                else:
                    date_str = date_elem.get_text(strip=True)
                
                if date_str:
                    return DateExtractor.parse_date_string(date_str)
        
        # 如果未找到日期元素，尝试在文本中查找日期
        text = soup.get_text()
        date_patterns = [
            r'Posted on\s+(.+?\d{4})',
            r'Published\s+(.+?\d{4})',
            r'Date:\s+(.+?\d{4})',
            r'Updated\s+(.+?\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return DateExtractor.parse_date_string(match.group(1))
        
        return None
    
