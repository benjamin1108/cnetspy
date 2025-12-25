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
import hashlib
import datetime
import concurrent.futures
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))

from src.crawlers.common.base_crawler import BaseCrawler
from src.crawlers.common.sync_decorator import sync_to_database_decorator

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
        actual_source_type = 'docs'  # documentation -> docs
        if self.sub_sources:
            first_sub = next(iter(self.sub_sources.values()))
            config_type = first_sub.get('type', '')
            if config_type == 'documentation':
                actual_source_type = 'docs'
        
        # 使用从配置获取的type初始化父类
        super().__init__(config, vendor, actual_source_type)
        
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
            
            logger.info(f"总共收集到 {len(all_updates)} 条华为云网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self._save_update(update)
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
            updates = self._parse_updates(html, source_name, url)
            
            # 过滤已存在的更新（除非强制模式）
            if not force_mode:
                updates = self._filter_existing_updates(updates)
            
            logger.info(f"{source_name} 解析到 {len(updates)} 条新更新")
            return updates
            
        except Exception as e:
            logger.error(f"爬取 {source_name} 时发生错误: {e}")
            return []
    
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        获取页面内容
        华为云反爬虫检测：使用简单UA避免被识别为爬虫
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html',
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
        source_name: str, 
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析华为云What's New页面
        
        Args:
            html: 页面HTML
            source_name: 服务名称
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
                logger.warning(f"{source_name} 未找到表格结构")
                return []
            
            # 查找时间标题 (h4标签: "2025年10月")
            time_headers = soup.find_all('h4', string=re.compile(r'20[1-2][0-9]年[0-1]?[0-9]月'))
            logger.debug(f"{source_name} 找到 {len(time_headers)} 个时间标题")
            
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
                table_updates = self._parse_table(table, source_name, url, time_key)
                updates.extend(table_updates)
            
            logger.info(f"{source_name} 解析到 {len(updates)} 条更新")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {source_name} 页面时出错: {e}")
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
    
    def _filter_existing_updates(self, updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已存在的更新（检查数据库）"""
        filtered = []
        for update in updates:
            # 生成source_identifier（使用基类方法）
            source_identifier = self.generate_source_identifier(update)
            source_url = update.get('source_url', '')
            
            # 检查数据库是否已存在
            if self.check_exists_in_db(source_url=source_url, source_identifier=source_identifier):
                logger.debug(f"跳过已存在: {update['title'][:30]}...")
                continue
            
            filtered.append(update)
        
        return filtered
    
    def _generate_update_id(self, update: Dict[str, Any]) -> str:
        """
        生成更新的唯一ID
        
        格式：hash(source_url + date + product + title)[:12]
        """
        components = [
            update.get('source_url', ''),
            update.get('publish_date', ''),
            update.get('product_name', ''),
            update.get('title', '').strip()
        ]
        content = '|'.join(components)
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    
    def _save_update(self, update: Dict[str, Any]) -> Optional[str]:
        """
        保存单条更新为Markdown文件
        
        Args:
            update: 更新条目
            
        Returns:
            保存的文件路径
        """
        try:
            # 生成文件名: YYYY-MM_hash.md
            update_id = self._generate_update_id(update)
            publish_date = update.get('publish_date', datetime.date.today().strftime('%Y-%m'))
            filename = f"{publish_date}_{update_id}.md"
            filepath = os.path.join(self.output_dir, filename)
            
            # 生成Markdown内容
            markdown_content = self._generate_markdown(update)
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 收集待同步数据（用于批量同步到数据库）
            sync_entry = {
                'title': update.get('title', ''),
                'publish_date': publish_date,
                'product_name': update.get('product_name', ''),
                'source_url': update.get('source_url', ''),
                'source_identifier': update_id,
                'filepath': filepath,
                'crawl_time': datetime.datetime.now().isoformat(),
                'file_hash': hashlib.md5(markdown_content.encode('utf-8')).hexdigest()
            }
            self._pending_sync_updates[update_id] = sync_entry
            
            logger.debug(f"保存更新: {update['title']}")
            return filepath
            
        except Exception as e:
            logger.error(f"保存更新失败: {e}")
            return None
    
    def _generate_markdown(self, update: Dict[str, Any]) -> str:
        """生成Markdown格式内容"""
        title = update.get('title', '无标题')
        publish_date = update.get('publish_date', '')
        product_name = update.get('product_name', '')
        source_url = update.get('source_url', '')
        description = update.get('description', '')
        stage = update.get('stage', '')
        doc_links = update.get('doc_links', [])
        
        lines = [
            f"# {title}",
            "",
            f"**发布时间:** {publish_date}",
            "",
            f"**厂商:** 华为云",
            "",
            f"**产品:** {product_name}",
            "",
            f"**类型:** 产品更新",
            "",
            f"**原始链接:** {source_url}",
            "",
            "---",
            ""
        ]
        
        if description:
            lines.extend([
                "## 功能描述",
                "",
                description,
                ""
            ])
        
        if stage:
            lines.extend([
                "## 发布阶段",
                "",
                stage,
                ""
            ])
        
        if doc_links:
            lines.extend([
                "## 相关文档",
                ""
            ])
            for doc_link in doc_links:
                lines.append(f"- [{doc_link['text']}]({doc_link['url']})")
            lines.append("")
        
        return "\n".join(lines)


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
