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

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))

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
            # 使用线程池处理多个子源
            max_workers = min(len(self.sub_sources), 5)  # 最多5个并发
            
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
                        logger.info(f"完成 {source_name}: {len(source_updates)} 条更新")
                    except Exception as e:
                        logger.error(f"爬取 {source_name} 失败: {e}")
            
            logger.info(f"总共收集到 {len(all_updates)} 条腾讯云网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self._save_update(update)
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
            
            logger.info(f"{source_name} 解析到 {len(updates)} 条新更新")
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
            
            # 查找所有表格
            tables = content_area.find_all('table') if content_area else soup.find_all('table')
            
            if not tables:
                logger.warning(f"{product_name} 未找到表格结构")
                return []
            
            logger.debug(f"{product_name} 找到 {len(tables)} 个表格")
            
            # 查找年份标题 (h2标签: "2024年")
            year_headers = content_area.find_all(['h2', 'h3']) if content_area else []
            
            # 建立年份与表格的映射
            table_year_map = {}
            current_year = datetime.date.today().strftime('%Y')
            
            for header in year_headers:
                header_text = header.get_text(strip=True).replace('\u200b', '').replace('\ufeff', '')
                year_match = re.search(r'(20[1-2][0-9])年', header_text)
                if year_match:
                    year = year_match.group(1)
                    # 查找该年份标题后的第一个表格
                    next_table = header.find_next('table')
                    if next_table:
                        table_year_map[id(next_table)] = year
                        logger.debug(f"映射: {year}年 -> 表格")
            
            # 解析每个表格
            for table in tables:
                year = table_year_map.get(id(table), current_year)
                table_updates = self._parse_table(table, product_name, url, year)
                updates.extend(table_updates)
            
            logger.info(f"{product_name} 解析到 {len(updates)} 条更新")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {product_name} 页面时出错: {e}")
            return []
    
    def _parse_table(
        self,
        table,
        product_name: str,
        url: str,
        year: str
    ) -> List[Dict[str, Any]]:
        """
        解析腾讯云产品动态表格
        表格结构通常为: 动态名称 | 动态描述 | 发布时间 | 相关文档
        
        Args:
            table: BeautifulSoup表格元素
            product_name: 产品名称
            url: 页面URL
            year: 年份
            
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
                if len(cells) < 2:
                    continue
                
                try:
                    # 提取表格数据（腾讯云表格通常是：动态名称、动态描述、发布时间、相关文档）
                    title = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    
                    # 过滤无效行
                    if not title or len(title) < 2 or title in ['动态名称', '功能']:
                        continue
                    
                    # 解析日期
                    publish_date = self._parse_date(date_text, year)
                    
                    # 提取相关文档链接
                    doc_links = []
                    if len(cells) > 3:
                        links = cells[3].find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin('https://cloud.tencent.com', href)
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
                    
                except Exception as e:
                    logger.debug(f"解析表格行时出错: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析表格时出错: {e}")
        
        return updates
    
    def _parse_date(self, date_text: str, year: str) -> str:
        """
        解析日期文本
        腾讯云日期格式：2024-10-17、2024年10月
        
        Args:
            date_text: 日期文本
            year: 年份
            
        Returns:
            标准化的日期 (YYYY-MM格式)
        """
        # 清理文本
        date_text = date_text.strip().replace('\u200b', '').replace('\ufeff', '')
        
        # 尝试匹配 YYYY-MM-DD 格式
        match = re.search(r'(20[1-2][0-9])[年-](0?[1-9]|1[0-2])', date_text)
        if match:
            year_part = match.group(1)
            month_part = match.group(2).zfill(2)
            return f"{year_part}-{month_part}"
        
        # 尝试匹配 MM月 格式
        match = re.search(r'(0?[1-9]|1[0-2])月', date_text)
        if match:
            month = match.group(1).zfill(2)
            return f"{year}-{month}"
        
        # 默认使用当前年月
        return datetime.date.today().strftime('%Y-%m')
    
    def _save_update(self, update: Dict[str, Any]) -> Optional[str]:
        """
        保存单条更新（使用基类方法）
        
        Args:
            update: 更新条目
            
        Returns:
            是否成功
        """
        try:
            # 直接调用基类的 save_update 方法，基类会统一处理 doc_links 等字段
            success = self.save_update(update)
            
            if success:
                logger.debug(f"保存更新: {update['title']}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存更新失败: {e}")
            return None


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
