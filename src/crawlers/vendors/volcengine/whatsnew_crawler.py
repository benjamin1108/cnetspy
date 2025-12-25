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
import hashlib
import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))

from src.crawlers.common.base_crawler import BaseCrawler
from src.crawlers.common.sync_decorator import sync_to_database_decorator

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
        使用Playwright进行动态渲染
        
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
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                try:
                    # 串行处理每个子源
                    for idx, (source_name, source_config) in enumerate(self.sub_sources.items()):
                        logger.info(f"处理任务: {source_name} ({idx + 1}/{len(self.sub_sources)})")
                        
                        try:
                            source_updates = self._crawl_single_source(
                                browser,
                                source_name, 
                                source_config, 
                                force_mode
                            )
                            all_updates.extend(source_updates)
                            logger.info(f"完成 {source_name}: {len(source_updates)} 条更新")
                            
                            # 间隔避免请求过快
                            if idx < len(self.sub_sources) - 1:
                                time.sleep(1)
                                
                        except Exception as e:
                            logger.error(f"爬取 {source_name} 失败: {e}")
                    
                finally:
                    browser.close()
            
            logger.info(f"总共收集到 {len(all_updates)} 条火山引擎网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    file_path = self._save_update(update)
                    if file_path:
                        saved_files.append(file_path)
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个火山引擎更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取火山引擎更新时发生错误: {e}")
            return saved_files
    
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
            updates = self._parse_updates(html, source_name, url)
            
            # 过滤已存在的更新（除非强制模式）
            if not force_mode:
                updates = self._filter_existing_updates(updates)
            
            logger.info(f"{source_name} 解析到 {len(updates)} 条新更新")
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
                
                # 等待关键元素
                try:
                    page.wait_for_selector('.ace-line, .volc-doceditor-container, article, table', timeout=10000)
                except:
                    pass
                
                # 额外等待确保内容加载
                page.wait_for_timeout(500)
                
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
        source_name: str, 
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析火山引擎产品动态页面
        
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
                logger.warning(f"{source_name} 未找到表格结构")
                return []
            
            logger.debug(f"{source_name} 找到 {len(tables)} 个表格")
            
            # 解析每个表格
            for table in tables:
                table_updates = self._parse_table(table, source_name, url)
                updates.extend(table_updates)
            
            logger.info(f"{source_name} 解析到 {len(updates)} 条更新")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {source_name} 页面时出错: {e}")
            return []
    
    def _parse_table(
        self,
        table,
        product_name: str,
        url: str
    ) -> List[Dict[str, Any]]:
        """
        解析火山引擎产品动态表格
        表格结构通常为: 发布时间 | 功能模块 | 功能描述 | 相关文档
        
        Args:
            table: BeautifulSoup表格元素
            product_name: 产品名称
            url: 页面URL
            
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
                    # 提取表格数据（火山引擎表格通常是：发布时间、功能模块、功能描述、相关文档）
                    date_text = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    
                    # 第二列可能是功能模块或标题
                    title = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    
                    # 第三列通常是描述
                    description = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    
                    # 过滤无效行
                    if not title or len(title) < 2 or title in ['功能', '功能模块', '功能名称']:
                        continue
                    
                    # 如果第二列是模块名，第三列是标题，调整结构
                    if len(cells) >= 4 and description and len(description) > len(title):
                        # 可能的结构：时间 | 模块 | 标题 | 描述
                        module = title
                        title = description
                        description = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        title = f"{module} - {title}" if module else title
                    
                    # 解析日期
                    publish_date = self._parse_date(date_text)
                    
                    # 提取相关文档链接
                    doc_links = []
                    # 查找最后一列的链接
                    if len(cells) > 2:
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
            year = datetime.date.today().strftime('%Y')
            return f"{year}-{month}"
        
        # 默认使用当前年月
        return datetime.date.today().strftime('%Y-%m')
    
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
            
            # 统一日期格式: YYYY-MM -> YYYY-MM-01
            if len(publish_date) == 7:  # YYYY-MM
                publish_date = f"{publish_date}-01"
            
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
                'content': markdown_content,  # 添加 content 字段
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
        doc_links = update.get('doc_links', [])
        
        lines = [
            f"# {title}",
            "",
            f"**发布时间:** {publish_date}",
            "",
            f"**厂商:** 火山引擎",
            "",
            f"**产品:** {product_name}",
            "",
            f"**类型:** 产品动态",
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
    crawler = VolcengineWhatsnewCrawler(config, 'volcengine', 'whatsnew')
    crawler.run()
