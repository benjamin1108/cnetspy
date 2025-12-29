#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
华为云网络服务更新爬虫
完全使用新的数据存储方式，移除冗余的月度汇总逻辑
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


class HuaweiWhatsnewCrawler(BaseCrawler):
    """华为云网络服务What's New更新爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化华为云更新爬虫"""
        # 获取所有子源配置（从原始配置中读取）
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.sub_sources = self._extract_sub_sources()
        
        # 从配置中获取type字段作为source_channel
        # 华为的子源都是documentation类型
        actual_source_type = 'whatsnew'  # documentation -> whatsnew
        if self.sub_sources:
            first_sub = next(iter(self.sub_sources.values()))
            config_type = first_sub.get('type', '')
            if config_type == 'documentation':
                actual_source_type = 'whatsnew'
        
        # 使用从配置获取的type初始化父类
        super().__init__(config, vendor, actual_source_type)
        
        # 获取反爬虫配置
        self.anti_crawler_config = config.get('anti_crawler', {})
        
        logger.info(f"发现 {len(self.sub_sources)} 个华为云网络服务: {list(self.sub_sources.keys())}")
    
    def _extract_sub_sources(self) -> Dict[str, Dict[str, Any]]:
        """提取所有子源配置"""
        sub_sources = {}
        for key, value in self.source_config.items():
            if isinstance(value, dict) and 'url' in value:
                sub_sources[key] = value
        return sub_sources
    
    def _get_identifier_strategy(self) -> str:
        """华为使用content-based策略"""
        return 'content_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        华为 whatsnew: hash(url + date + product + title)
        
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
        爬取华为云网络服务更新
        
        Returns:
            保存的文件路径列表
        """
        if not self.sub_sources:
            logger.error("未找到华为云网络服务配置")
            return []
        
        saved_files = []
        all_updates = []
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        try:
            # 从配置读取并发参数
            max_concurrent = self.anti_crawler_config.get('max_concurrent', 2)
            task_interval_min = self.anti_crawler_config.get('task_interval_min', 1.5)
            task_interval_max = self.anti_crawler_config.get('task_interval_max', 2.5)
            
            # 使用线程池处理多个子源
            max_workers = min(len(self.sub_sources), max_concurrent)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_source = {}
                
                # 慢启动提交任务
                for idx, (source_name, source_config) in enumerate(self.sub_sources.items()):
                    if idx > 0:
                        delay = random.uniform(task_interval_min, task_interval_max)
                        time.sleep(delay)
                    
                    future = executor.submit(
                        self._crawl_single_source, 
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
            
            logger.info(f"总共收集到 {len(all_updates)} 条华为云网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self.save_update(update)
                    if file_path:
                        saved_files.append(file_path)
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个华为云更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取华为云更新时发生错误: {e}")
            return saved_files
    
    def _crawl_single_source(
        self, 
        source_name: str, 
        source_config: Dict[str, Any], 
        force_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        爬取单个源
    
        Args:
            source_name: 源名称
            source_config: 源配置
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
            # 获取页面内容
            html = self._get_page_content(url)
            if not html:
                logger.error(f"获取页面失败: {source_name}")
                return []
            
            # 解析更新条目
            updates = self._parse_updates(html, product_name, url)
            
            # 设置发现总数
            self.set_total_discovered(len(updates))
            
            # 过滤已存在的更新（除非强制模式）
            if not force_mode:
                updates = [u for u in updates if not self.should_skip_update(update=u)[0]]
            
            logger.info(f"{source_name} 新增 {len(updates)} 条")
            return updates
            
        except Exception as e:
            logger.error(f"爬取 {source_name} 时发生错误: {e}")
            return []
    
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        获取页面内容
        使用动态请求头和重试机制规避反爬虫检测
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        # 从配置读取重试参数
        max_retries = self.anti_crawler_config.get('max_retries', 3)
        retry_delay_min = self.anti_crawler_config.get('retry_delay_min', 2)
        retry_delay_max = self.anti_crawler_config.get('retry_delay_max', 5)
        
        for attempt in range(max_retries):
            try:
                # 每次请求使用不同的请求头
                headers = self._build_dynamic_headers(url)
                
                # 重试前随机延迟
                if attempt > 0:
                    delay = random.uniform(retry_delay_min, retry_delay_max)
                    logger.info(f"重试前等待 {delay:.1f} 秒...")
                    time.sleep(delay)
                
                timeout = self.crawler_config.get('timeout', 30)
                response = requests.get(url, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    # 检查是否返回了验证码页面
                    if self._is_captcha_page(response.text):
                        logger.warning(f"检测到验证码页面，尝试重试 ({attempt + 1}/{max_retries}): {url}")
                        continue
                    
                    logger.info(f"获取页面成功: {url}")
                    return response.text
                else:
                    logger.warning(f"请求返回状态码 {response.status_code}: {url}")
                    
            except Exception as e:
                logger.error(f"获取页面失败 (尝试 {attempt + 1}/{max_retries}): {url} - {e}")
        
        logger.error(f"获取页面最终失败: {url}")
        return None
    
    def _build_dynamic_headers(self, url: str) -> Dict[str, str]:
        """
        构建动态请求头，模拟真实浏览器行为
        
        Args:
            url: 请求URL
            
        Returns:
            请求头字典
        """
        # 从配置读取 User-Agent 池
        user_agents = self.anti_crawler_config.get('user_agents', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ])
        
        # 从配置读取 Accept-Language 池
        accept_languages = self.anti_crawler_config.get('accept_languages', [
            'zh-CN,zh;q=0.9,en;q=0.8'
        ])
        
        # 随机选择
        ua = random.choice(user_agents)
        accept_lang = random.choice(accept_languages)
        
        # 基础请求头
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': accept_lang,
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        
        # 动态添加 Referer（从配置读取）
        referers_config = self.anti_crawler_config.get('referers', {})
        huawei_referers = referers_config.get('huawei', [])
        if huawei_referers and random.random() > 0.3:
            headers['Referer'] = random.choice(huawei_referers)
        
        # 随机添加一些可选头
        if random.random() > 0.5:
            headers['DNT'] = '1'
        
        if random.random() > 0.5:
            headers['Sec-Ch-Ua'] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            headers['Sec-Ch-Ua-Mobile'] = '?0'
            headers['Sec-Ch-Ua-Platform'] = random.choice(['"Windows"', '"macOS"', '"Linux"'])
        
        return headers
    
    def _is_captcha_page(self, html: str) -> bool:
        """
        检测页面是否为验证码页面
        
        Args:
            html: 页面HTML
            
        Returns:
            是否为验证码页面
        """
        # 从配置读取验证码检测关键词
        captcha_indicators = self.anti_crawler_config.get('captcha_indicators', [
            '验证码', 'captcha', '人机验证'
        ])
        
        html_lower = html.lower()
        for indicator in captcha_indicators:
            if indicator.lower() in html_lower:
                # 进一步确认（避免误判正常页面中提到验证码的情况）
                if len(html) < 10000 and indicator.lower() in html_lower:
                    return True
        
        return False
    
    def _parse_updates(
        self, 
        html: str, 
        product_name: str, 
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析华为云What's New页面
        
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
            # 查找所有表格
            tables = soup.find_all('table')
            if not tables:
                logger.warning(f"{product_name} 未找到表格结构")
                return []
            
            # 查找时间标题 (h4标签: "2025年10月")
            time_headers = soup.find_all('h4', string=re.compile(r'20[1-2][0-9]年[0-1]?[0-9]月'))
            logger.debug(f"{product_name} 找到 {len(time_headers)} 个时间标题")
            
            # 建立时间标题与表格的映射
            time_map = {}
            for header in time_headers:
                time_match = re.search(r'(20[1-2][0-9])年([0-1]?[0-9])月', header.get_text())
                if not time_match:
                    continue
                
                year = time_match.group(1)
                month = time_match.group(2).zfill(2)
                time_key = f"{year}-{month}"
                
                # 查找该时间标题后的第一个表格
                next_table = self._find_next_table(header)
                if next_table:
                    time_map[next_table] = time_key
                    logger.debug(f"映射: {time_key} -> 表格")
            
            # 解析每个有时间映射的表格
            for table, time_key in time_map.items():
                table_updates = self._parse_table(table, product_name, url, time_key)
                updates.extend(table_updates)
            
            logger.info(f"{product_name} 发现 {len(updates)} 条记录")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {product_name} 页面时出错: {e}")
            return []
    
    def _find_next_table(self, header) -> Optional[Any]:
        """查找时间标题后的第一个表格"""
        current = header
        for _ in range(10):  # 最多查找10个兄弟元素
            current = current.find_next_sibling()
            if not current:
                break
            
            # 直接是表格
            if current.name == 'table':
                return current
            
            # 容器中有表格
            if hasattr(current, 'find') and current.find('table'):
                return current.find('table')
            
            # 遇到下一个时间标题，停止
            if current.name == 'h4' and re.search(r'20[1-2][0-9]年[0-1]?[0-9]月', current.get_text()):
                break
        
        return None
    
    def _parse_table(
        self,
        table,
        product_name: str,
        url: str,
        publish_date: str
    ) -> List[Dict[str, Any]]:
        """
        解析华为云标准表格
        表格结构: 序号 | 功能名称 | 功能描述 | 阶段 | 相关文档
        
        Args:
            table: BeautifulSoup表格元素
            product_name: 产品名称
            url: 页面URL
            publish_date: 发布日期 (YYYY-MM格式)
            
        Returns:
            更新条目列表
        """
        updates = []
        
        try:
            rows = table.find_all('tr')
            if not rows:
                return updates
            
            # 跳过表头，从第二行开始
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                try:
                    # 提取表格数据
                    function_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    function_desc = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    stage = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    
                    # 过滤无效行
                    if not function_name or len(function_name) < 3:
                        continue
                    
                    # 提取相关文档链接
                    doc_links = []
                    if len(cells) > 4:
                        links = cells[4].find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin('https://support.huaweicloud.com', href)
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
                        'title': function_name,
                        'description': function_desc,
                        'publish_date': publish_date,  # YYYY-MM格式
                        'product_name': product_name,
                        'source_url': url,
                        'stage': stage,
                        'doc_links': doc_links
                    }
                    
                    updates.append(update)
                    
                except Exception as e:
                    logger.debug(f"解析表格行时出错: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析表格时出错: {e}")
        
        return updates
    

if __name__ == '__main__':
    """测试爬虫"""
    from src.utils.config.config_loader import get_config
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = get_config()
    crawler = HuaweiWhatsnewCrawler(config, 'huawei', 'whatsnew')
    crawler.run()
