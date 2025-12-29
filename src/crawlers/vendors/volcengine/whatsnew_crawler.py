#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
火山引擎网络服务产品动态爬虫
完全使用新的数据存储方式，每条更新独立保存
"""

import logging
import os
import re
import sys
import time
import datetime
import random
import concurrent.futures
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class VolcengineWhatsnewCrawler(BaseCrawler):
    """火山引擎网络服务产品动态爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化火山引擎产品动态爬虫"""
        # 获取所有子源配置
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.sub_sources = self._extract_sub_sources()
        
        # 从配置中获取type字段作为source_channel
        # 火山引擎的子源都是documentation类型
        actual_source_type = 'whatsnew'  # documentation -> whatsnew
        if self.sub_sources:
            first_sub = next(iter(self.sub_sources.values()))
            config_type = first_sub.get('type', '')
            if config_type == 'documentation':
                actual_source_type = 'whatsnew'
        
        # 使用从配置获取的type初始化父类
        super().__init__(config, vendor, actual_source_type)
        
        logger.info(f"发现 {len(self.sub_sources)} 个火山引擎网络服务: {list(self.sub_sources.keys())}")
    
    def _extract_sub_sources(self) -> Dict[str, Dict[str, Any]]:
        """提取所有子源配置"""
        sub_sources = {}
        for key, value in self.source_config.items():
            if isinstance(value, dict) and 'url' in value:
                sub_sources[key] = value
        return sub_sources
    
    def _get_identifier_strategy(self) -> str:
        """火山引擎使用content-based策略"""
        return 'content_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        火山引擎 whatsnew: hash(url + date + product + title)
        
        Args:
            update: 更新数据字典
            
        Returns:
            [url, date, product, title]
        """
        return [
            update.get('source_url', ''),
            update.get('publish_date', ''),
            update.get('product_name', ''),
            update.get('title', '').strip()
        ]
    
    def _crawl(self) -> List[str]:
        """
        爬取火山引擎网络服务产品动态
        使用Playwright进行动态渲染，并发处理多个子源
        
        Returns:
            保存的文件路径列表
        """
        if not self.sub_sources:
            logger.error("未找到火山引擎网络服务配置")
            return []
        
        saved_files = []
        all_updates = []
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        # 并发配置（内存受限时降低并发数）
        max_concurrent = 2  # 最大并发数（火山引擎页面较重，不宜过高）
        task_interval_min = 0.3
        task_interval_max = 0.8
        
        try:
            # 使用线程池并发处理
            # 注：Playwright sync_api 不支持多线程共享 browser
            # 每个线程需要创建独立的 playwright 实例
            max_workers = min(len(self.sub_sources), max_concurrent)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_source = {}
                
                # 慢启动提交任务
                for idx, (source_name, source_config) in enumerate(self.sub_sources.items()):
                    if idx > 0:
                        delay = random.uniform(task_interval_min, task_interval_max)
                        time.sleep(delay)
                    
                    future = executor.submit(
                        self._crawl_single_source_with_own_browser,  # 使用独立 browser 的方法
                        source_name,
                        source_config,
                        force_mode
                    )
                    future_to_source[future] = source_name
                    logger.info(f"提交任务: {source_name} ({idx + 1}/{len(self.sub_sources)})")
                
                # 收集所有更新
                for future in concurrent.futures.as_completed(future_to_source):
                    source_name = future_to_source[future]
                    try:
                        source_updates = future.result(timeout=120)
                        all_updates.extend(source_updates)
                        logger.info(f"✓ {source_name} 完成")
                    except Exception as e:
                        logger.error(f"爬取 {source_name} 失败: {e}")
            
            logger.info(f"总共收集到 {len(all_updates)} 条火山引擎网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self.save_update(update)
                    if file_path:
                        saved_files.append(file_path)
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个火山引擎更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取火山引擎更新时发生错误: {e}")
            return saved_files
    
    def _crawl_single_source_with_own_browser(
        self,
        source_name: str,
        source_config: Dict[str, Any],
        force_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        在独立的 Playwright 实例中爬取单个源
        
        Playwright sync_api 不支持多线程共享 browser，
        每个线程必须创建自己的 playwright 和 browser 实例
        """
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                try:
                    return self._crawl_single_source(browser, source_name, source_config, force_mode)
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"创建 Playwright 实例失败 [{source_name}]: {e}")
            return []
    
    def _crawl_single_source(
        self,
        browser,
        source_name: str, 
        source_config: Dict[str, Any], 
        force_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        爬取单个火山引擎服务的更新
        
        Args:
            browser: Playwright browser实例
            product_name: 产品名称
            source_config: 服务配置
            force_mode: 是否强制模式
            
        Returns:
            更新条目列表
        """
        url = source_config.get('url')
        if not url:
            logger.warning(f"源 {source_name} 没有配置URL")
            return []
        
        # 从配置获取product字段
        product_name = source_config.get('product', source_name)
        
        logger.info(f"正在爬取 {source_name} (product: {product_name}): {url}")
        
        try:
            # 先尝试requests（部分页面是服务端渲染）
            html = self._get_page_content_requests(url)
            
            # 如果requests失败或内容不完整，使用Playwright
            if not html or not self._is_content_complete(html):
                html = self._get_page_content_playwright(browser, url)
            
            if not html:
                logger.error(f"获取页面失败: {source_name}")
                return []
            
            # 解析更新条目
            updates = self._parse_updates(html, product_name, url)
            
            # 线程安全地累加发现数
            self.set_total_discovered(len(updates))
            
            # 过滤已存在的更新（除非强制模式）
            if not force_mode:
                updates = [u for u in updates if not self.should_skip_update(update=u)[0]]
            
            logger.info(f"{source_name} 新增 {len(updates)} 条")
            return updates
            
        except Exception as e:
            logger.error(f"爬取 {source_name} 时发生错误: {e}")
            return []
    
    def _get_page_content_requests(self, url: str) -> Optional[str]:
        """
        使用requests获取页面内容
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'zh-CN,zh;q=0.9'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.debug(f"requests获取页面成功: {url}")
                return response.text
            else:
                logger.debug(f"requests返回状态码 {response.status_code}: {url}")
                
        except Exception as e:
            logger.debug(f"requests获取页面失败: {url} - {e}")
        
        return None
    
    def _get_page_content_playwright(self, browser, url: str) -> Optional[str]:
        """
        使用Playwright获取页面内容
        
        Args:
            browser: Playwright browser实例
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        try:
            context = browser.new_context()
            try:
                page = context.new_page()
                page.set_default_timeout(30000)
                
                # 导航到页面
                page.goto(url, wait_until='domcontentloaded')
                
                # 专门等待 table 加载（增加等待时间应对内存紧张）
                try:
                    page.wait_for_selector('table', timeout=15000)
                except:
                    # table 未加载，尝试等待其他关键元素
                    try:
                        page.wait_for_selector('.ace-line, .volc-doceditor-container, article', timeout=3000)
                    except:
                        pass
                
                # 额外等待确保内容加载
                page.wait_for_timeout(300)
                
                html = page.content()
                logger.info(f"Playwright获取页面成功: {url}")
                return html
                
            finally:
                context.close()
                
        except Exception as e:
            logger.error(f"Playwright获取页面失败: {url} - {e}")
        
        return None
    
    def _is_content_complete(self, html: str) -> bool:
        """检查HTML内容是否完整（包含表格或关键元素）"""
        if not html:
            return False
        return any(keyword in html for keyword in ['.ace-line', 'ace-table', '<table', 'article'])
    
    def _parse_updates(
        self, 
        html: str, 
        product_name: str, 
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析火山引擎产品动态页面
        
        页面结构：
        - 日期在 SPAN 元素中（如 "2025年11月"），位于表格上方
        - 每个表格属于其上方最近的日期
        - 表格列：序号 | 功能（标题）| 功能描述 | 阶段 | 文档
        
        Args:
            html: 页面HTML
            product_name: 产品名称
            url: 页面URL
            
        Returns:
            更新条目列表
        """
        soup = BeautifulSoup(html, 'lxml')
        updates = []
        
        try:
            # 1. 查找所有日期元素（匹配 "2024年01月" 格式）
            date_pattern = re.compile(r'20\d{2}年\d{1,2}月')
            date_elements = []
            for span in soup.find_all('span'):
                text = span.get_text(strip=True).replace('\u200b', '')
                if date_pattern.match(text):
                    date_elements.append({'element': span, 'date_text': text})
            
            logger.debug(f"{product_name} 找到 {len(date_elements)} 个日期元素")
            
            # 2. 查找所有表格
            tables = soup.find_all('table')
            
            if not tables:
                logger.warning(f"{product_name} 未找到表格结构")
                return []
            
            logger.debug(f"{product_name} 找到 {len(tables)} 个表格")
            
            # 3. 建立日期-表格映射
            # 遍历 DOM 树，为每个表格找到其前面最近的日期
            table_date_map = self._build_table_date_map(soup, date_elements, tables)
            
            # 4. 解析每个表格
            for idx, table in enumerate(tables):
                date_text = table_date_map.get(idx, '')
                table_updates = self._parse_table(table, product_name, url, date_text)
                updates.extend(table_updates)
            
            logger.info(f"{product_name} 发现 {len(updates)} 条记录")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {product_name} 页面时出错: {e}")
            return []
    
    def _build_table_date_map(
        self,
        soup,
        date_elements: List[Dict],
        tables: List
    ) -> Dict[int, str]:
        """
        建立表格索引到日期的映射
        
        逻辑：按 DOM 顺序遍历，记录当前日期，遇到表格时分配当前日期
        
        Args:
            soup: BeautifulSoup对象
            date_elements: 日期元素列表
            tables: 表格列表
            
        Returns:
            {表格索引: 日期文本}
        """
        table_date_map = {}
        
        # 获取所有元素的DOM顺序
        all_elements = soup.find_all(['span', 'table'])
        
        current_date = ''
        date_pattern = re.compile(r'20\d{2}年\d{1,2}月')
        table_index = 0
        
        for elem in all_elements:
            if elem.name == 'span':
                text = elem.get_text(strip=True).replace('\u200b', '')
                if date_pattern.match(text):
                    current_date = text
                    logger.debug(f"发现日期: {current_date}")
            elif elem.name == 'table':
                if table_index < len(tables) and elem == tables[table_index]:
                    table_date_map[table_index] = current_date
                    logger.debug(f"表格{table_index+1} 对应日期: {current_date}")
                    table_index += 1
        
        return table_date_map
    
    def _parse_table(
        self,
        table,
        product_name: str,
        url: str,
        date_text: str = ''
    ) -> List[Dict[str, Any]]:
        """
        解析火山引擎产品动态表格
        
        表格结构：序号 | 功能（标题）| 功能描述 | 阶段 | 文档
        日期从表格上方的 SPAN 元素获取，通过 date_text 参数传入
        
        Args:
            table: BeautifulSoup表格元素
            product_name: 产品名称
            url: 页面URL
            date_text: 日期文本（如 "2024年12月"）
            
        Returns:
            更新条目列表
        """
        updates = []
        
        # 解析日期（从传入的日期文本）
        publish_date = self._parse_date(date_text) if date_text else datetime.date.today().strftime('%Y-%m-01')
        
        try:
            rows = table.find_all('tr')
            if not rows:
                return updates
            
            # 跳过表头，从第二行开始
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:  # 至少需要：序号、功能、描述
                    continue
                
                try:
                    # 列0: 序号（跳过）
                    # 列1: 功能（标题）
                    title = cells[1].get_text(strip=True).replace('\u200b', '') if len(cells) > 1 else ""
                    
                    # 列2: 功能描述
                    description = cells[2].get_text(strip=True).replace('\u200b', '') if len(cells) > 2 else ""
                    
                    # 过滤无效行（标题为空或是表头）
                    if not title or len(title) < 2 or title in ['功能', '功能模块', '功能名称']:
                        continue
                    
                    # 提取相关文档链接（最后一列）
                    doc_links = []
                    if len(cells) > 3:
                        last_cell = cells[-1]
                        links = last_cell.find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin('https://www.volcengine.com', href)
                                elif href.startswith('http'):
                                    full_url = href
                                else:
                                    full_url = urljoin(url, href)
                                
                                doc_links.append({
                                    'text': link.get_text(strip=True),
                                    'url': full_url
                                })
                    
                    # 构建更新条目
                    update = {
                        'title': title,
                        'description': description,
                        'publish_date': publish_date,
                        'product_name': product_name,
                        'source_url': url,
                        'doc_links': doc_links
                    }
                    
                    updates.append(update)
                    logger.debug(f"解析到: [{publish_date}] {title[:30]}...")
                    
                except Exception as e:
                    logger.debug(f"解析表格行时出错: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析表格时出错: {e}")
        
        return updates
    
    def _parse_date(self, date_text: str) -> str:
        """
        解析日期文本
        火山引擎日期格式：2024-10-17、2024年10月
        
        Args:
            date_text: 日期文本
            
        Returns:
            标准化的日期 (YYYY-MM-DD格式)
        """
        # 清理文本
        date_text = date_text.strip().replace('\u200b', '').replace('\ufeff', '')
        
        logger.debug(f"解析日期文本: '{date_text}'")
        
        # 尝试匹配 YYYY-MM-DD 格式
        match = re.search(r'(20[1-2][0-9])[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])', date_text)
        if match:
            year_part = match.group(1)
            month_part = match.group(2).zfill(2)
            day_part = match.group(3).zfill(2)
            result = f"{year_part}-{month_part}-{day_part}"
            logger.debug(f"匹配 YYYY-MM-DD: {result}")
            return result
        
        # 尝试匹配 YYYY年MM月DD日 格式
        match = re.search(r'(20[1-2][0-9])年(0?[1-9]|1[0-2])月(0?[1-9]|[12][0-9]|3[01])日?', date_text)
        if match:
            year_part = match.group(1)
            month_part = match.group(2).zfill(2)
            day_part = match.group(3).zfill(2)
            result = f"{year_part}-{month_part}-{day_part}"
            logger.debug(f"匹配 YYYY年MM月DD日: {result}")
            return result
        
        # 尝试匹配 YYYY-MM 或 YYYY年MM月 格式
        match = re.search(r'(20[1-2][0-9])[年/-](0?[1-9]|1[0-2])', date_text)
        if match:
            year_part = match.group(1)
            month_part = match.group(2).zfill(2)
            result = f"{year_part}-{month_part}-01"  # 缺失日补为01
            logger.debug(f"匹配 YYYY-MM: {result}")
            return result
        
        # 默认使用当前日期
        result = datetime.date.today().strftime('%Y-%m-01')
        logger.warning(f"日期解析失败，使用默认日期: '{date_text}' -> {result}")
        return result
    

if __name__ == '__main__':
    """测试爬虫"""
    from src.utils.config.config_loader import get_config
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = get_config()
    crawler = VolcengineWhatsnewCrawler(config, 'volcengine', 'whatsnew')
    crawler.run()
