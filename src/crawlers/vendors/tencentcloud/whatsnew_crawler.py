#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
腾讯云网络服务产品动态爬虫
完全使用新的数据存储方式，每条更新独立保存
"""

import logging
import os
import re
import sys
import time
import datetime
import concurrent.futures
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class TencentcloudWhatsnewCrawler(BaseCrawler):
    """腾讯云网络服务产品动态爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化腾讯云产品动态爬虫"""
        # 获取所有子源配置（从原始配置中读取）
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.sub_sources = self._extract_sub_sources()
        
        # 从配置中获取type字段作为source_channel
        # 腾讯云的子源都是documentation类型
        actual_source_type = 'whatsnew'  # documentation -> whatsnew
        if self.sub_sources:
            first_sub = next(iter(self.sub_sources.values()))
            config_type = first_sub.get('type', '')
            if config_type == 'documentation':
                actual_source_type = 'whatsnew'
        
        # 使用从配置获取的type初始化父类
        super().__init__(config, vendor, actual_source_type)
        
        logger.info(f"发现 {len(self.sub_sources)} 个腾讯云网络服务: {list(self.sub_sources.keys())}")
    
    def _extract_sub_sources(self) -> Dict[str, Dict[str, Any]]:
        """提取所有子源配置"""
        sub_sources = {}
        for key, value in self.source_config.items():
            if isinstance(value, dict) and 'url' in value:
                sub_sources[key] = value
        return sub_sources
    
    def _get_identifier_strategy(self) -> str:
        """腾讯云使用content-based策略"""
        return 'content_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        腾讯云 whatsnew: hash(url + date + product + title)
        
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
        爬取腾讯云网络服务产品动态
        
        Returns:
            保存的文件路径列表
        """
        if not self.sub_sources:
            logger.error("未找到腾讯云网络服务配置")
            return []
        
        saved_files = []
        all_updates = []
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        try:
            # 使用全局配置的并发参数
            max_workers_config = self.crawler_config.get('max_workers', 5)
            max_workers = min(len(self.sub_sources), max_workers_config)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_source = {}
                
                # 慢启动提交任务
                for idx, (source_name, source_config) in enumerate(self.sub_sources.items()):
                    if idx > 0:
                        time.sleep(0.5)  # 避免过快请求
                    
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
            
            logger.info(f"总共收集到 {len(all_updates)} 条腾讯云网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self.save_update(update)
                    if file_path:
                        saved_files.append(file_path)
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个腾讯云更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取腾讯云更新时发生错误: {e}")
            return saved_files
    
    def _crawl_single_source(
        self, 
        source_name: str, 
        source_config: Dict[str, Any], 
        force_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        爬取单个腾讯云服务的更新
        
        Args:
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
                logger.info(f"获取页面成功: {url}")
                return response.text
            else:
                logger.warning(f"请求返回状态码 {response.status_code}: {url}")
                
        except Exception as e:
            logger.error(f"获取页面失败: {url} - {e}")
        
        return None

    def _parse_updates(
        self, 
        html: str, 
        product_name: str, 
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析腾讯云产品动态页面
        
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
            # 腾讯云文档页面主内容区域
            content_area = soup.select_one('#docArticleContent')
            if not content_area:
                content_area = soup.select_one('.J-articleContent')
            if not content_area:
                content_area = soup.find('body')
            
            if not content_area:
                logger.warning(f"{product_name} 未找到内容区域")
                return []

            # 建立年份与表格的映射（优化：按顺序遍历元素，使年份标题作用于后续所有表格）
            table_date_map = {}
            current_year = datetime.date.today().strftime('%Y')
            active_year = current_year
            active_month = "01"
            
            # 查找所有直接子元素中的标题和表格
            for child in content_area.find_all(['h2', 'h3', 'table'], recursive=True):
                if child.name in ['h2', 'h3']:
                    header_text = child.get_text(strip=True).replace('\u200b', '').replace('\ufeff', '')
                    # 1. 优先尝试匹配 年+月
                    ym_match = re.search(r'(20[1-2][0-9])\s*年\s*([0-1]?[0-9])\s*月', header_text)
                    if ym_match:
                        active_year = ym_match.group(1)
                        active_month = ym_match.group(2).zfill(2)
                        logger.info(f"解析到标题日期: {active_year}-{active_month}")
                    else:
                        # 2. 只有年份
                        y_match = re.search(r'(20[1-2][0-9])\s*年', header_text)
                        if y_match:
                            active_year = y_match.group(1)
                            active_month = "01" # 只有年时重置月
                            logger.info(f"解析到标题年份: {active_year}")
                elif child.name == 'table':
                    table_date_map[id(child)] = (active_year, active_month)
            
            # 获取所有表格并解析
            tables = content_area.find_all('table')
            if not tables:
                logger.warning(f"{product_name} 未找到表格结构")
                return []
            
            for table in tables:
                year, month = table_date_map.get(id(table), (current_year, "01"))
                table_updates = self._parse_table(table, product_name, url, year, month)
                updates.extend(table_updates)
            
            logger.info(f"{product_name} 发现 {len(updates)} 条记录")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {product_name} 页面时出错: {e}")
            return []
    
    def _parse_table(
        self,
        table,
        product_name: str,
        url: str,
        year: str,
        month: str = "01"
    ) -> List[Dict[str, Any]]:
        """
        解析腾讯云产品动态表格
        """
        updates = []
        
        try:
            rows = table.find_all('tr')
            if not rows:
                return updates
            
            # 识别列索引
            header_row = rows[0]
            header_cells = [c.get_text(strip=True) for c in header_row.find_all(['td', 'th'])]
            
            title_idx = 0
            desc_idx = 1
            date_idx = 2
            
            for i, text in enumerate(header_cells):
                if any(k in text for k in ['动态名称', '功能', '更新类型']):
                    title_idx = i
                elif '描述' in text or '内容' in text:
                    desc_idx = i
                elif '时间' in text or '日期' in text:
                    date_idx = i

            # 从第二行开始解析
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) <= max(title_idx, desc_idx):
                    continue
                
                try:
                    title = cells[title_idx].get_text(strip=True)
                    description = cells[desc_idx].get_text(strip=True)
                    date_text = cells[date_idx].get_text(strip=True) if len(cells) > date_idx else ""
                    
                    if not title or title in ['动态名称', '功能', '更新类型', '功能模块']:
                        continue
                    
                    # 解析日期
                    publish_date = self._parse_date(date_text, year, month)
                    
                    # 提取链接
                    doc_links = []
                    for cell in cells[max(date_idx, desc_idx):]:
                        links = cell.find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            if href:
                                full_url = urljoin(url, href) if not href.startswith('http') else href
                                link_text = link.get_text(strip=True)
                                if link_text:
                                    doc_links.append({'text': link_text, 'url': full_url})
                    
                    # 组装完整内容（描述 + 相关文档）
                    content_parts = []
                    if description:
                        content_parts.append(description)
                    
                    if doc_links:
                        content_parts.append("\n\n## 相关文档")
                        for link in doc_links:
                            content_parts.append(f"- [{link.get('text', '')}]({link.get('url', '')})")
                    
                    content = "\n".join(content_parts)

                    updates.append({
                        'title': title,
                        'description': description,
                        'content': content,
                        'publish_date': publish_date,
                        'product_name': product_name,
                        'source_url': url,
                        'doc_links': doc_links
                    })
                except Exception as e:
                    logger.debug(f"解析行失败: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析表格时出错: {e}")
        
        return updates
    
    def _parse_date(self, date_text: str, default_year: str, default_month: str = "01") -> str:
        """
        解析日期文本：提取数字模式
        """
        # 只保留数字和关键分隔符
        clean_text = "".join(re.findall(r'[0-9年\-月/]+', date_text))
        
        # 1. 尝试提取所有数字序列
        numbers = re.findall(r'[0-9]+', clean_text)

        if len(numbers) >= 3:
            # 可能是 [2025, 12, 15]
            year = numbers[0]
            month = numbers[1]
            day = numbers[2]
            if len(year) == 4 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        if len(numbers) >= 2:
            # 可能是 [2025, 12]
            year = numbers[0]
            month = numbers[1]
            if len(year) == 4 and 1 <= int(month) <= 12:
                return f"{year}-{month.zfill(2)}"
        
        if len(numbers) == 1:
            val = numbers[0]
            if len(val) == 4: # 只有年份
                return f"{val}-{default_month}"
            if 1 <= int(val) <= 12: # 只有月份
                return f"{default_year}-{val.zfill(2)}"

        # 最终兜底：使用标题解析出的年-月
        return f"{default_year}-{default_month}"
    

if __name__ == '__main__':
    """测试爬虫"""
    from src.utils.config.config_loader import get_config
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = get_config()
    crawler = TencentcloudWhatsnewCrawler(config, 'tencentcloud', 'whatsnew')
    crawler.run()
