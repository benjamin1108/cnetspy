#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GCP网络服务Release Notes爬虫
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


class GcpWhatsnewCrawler(BaseCrawler):
    """GCP网络服务Release Notes爬虫"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """初始化GCP Release Notes爬虫"""
        # 获取所有子源配置
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.sub_sources = self._extract_sub_sources()
        
        # 使用传入的source_type（whatsnew）初始化父类
        super().__init__(config, vendor, source_type)
        
        logger.info(f"发现 {len(self.sub_sources)} 个GCP网络服务: {list(self.sub_sources.keys())}")
    
    def _extract_sub_sources(self) -> Dict[str, Dict[str, Any]]:
        """提取所有子源配置"""
        sub_sources = {}
        for key, value in self.source_config.items():
            if isinstance(value, dict) and 'url' in value:
                sub_sources[key] = value
        return sub_sources
    
    def _crawl(self) -> List[str]:
        """
        爬取GCP网络服务Release Notes
        
        Returns:
            保存的文件路径列表
        """
        if not self.sub_sources:
            logger.error("未找到GCP网络服务配置")
            return []
        
        saved_files = []
        all_updates = []
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        try:
            # 使用全局配置的并发参数
            max_workers_config = self.crawler_config.get('max_workers', 5)
            max_workers = min(len(self.sub_sources), max_workers_config)  # 使用配置的并发数
            logger.info(f"使用 {max_workers} 个线程并行爬取")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_source = {}
                
                # 慢启动提交任务（避免瞬间大量请求）
                for idx, (source_name, source_config) in enumerate(self.sub_sources.items()):
                    if idx > 0:
                        time.sleep(0.2)  # 每个任务间隔0.2秒
                    
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
            
            logger.info(f"总共收集到 {len(all_updates)} 条GCP网络更新")
            
            # 保存每条更新
            for update in all_updates:
                try:
                    success = self._save_update(update)
                    if success:
                        saved_files.append(update.get('source_url', ''))
                except Exception as e:
                    logger.error(f"保存更新失败 [{update.get('title', 'Unknown')}]: {e}")
            
            logger.info(f"成功保存 {len(saved_files)} 个GCP更新文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"爬取GCP更新时发生错误: {e}")
            return saved_files
    
    def _crawl_single_source(
        self, 
        source_name: str, 
        source_config: Dict[str, Any], 
        force_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        爬取单个GCP服务的Release Notes
        
        Args:
            source_name: 服务名称
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
        获取页面内容（GCP Release Notes是服务端渲染）
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9'
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
        解析GCP Release Notes页面
        
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
            # 查找所有release note块
            release_notes = soup.find_all('div', class_='devsite-release-note')
            
            if not release_notes:
                logger.warning(f"{product_name} 未找到release note")
                return []
            
            logger.debug(f"{product_name} 找到 {len(release_notes)} 个release note")
            
            # 解析每个release note
            for note in release_notes:
                try:
                    update = self._parse_release_note(note, product_name, url)
                    if update:
                        updates.append(update)
                except Exception as e:
                    logger.debug(f"解析release note时出错: {e}")
                    continue
            
            logger.info(f"{product_name} 发现 {len(updates)} 条记录")
            return updates
            
        except Exception as e:
            logger.error(f"解析 {product_name} 页面时出错: {e}")
            return []
    
    def _parse_release_note(
        self,
        note,
        product_name: str,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """
        解析单个release note块
        
        Args:
            note: BeautifulSoup release note元素
            product_name: 产品名称
            url: 页面URL
            
        Returns:
            更新条目或None
        """
        try:
            # 提取类型标签（Feature/Changed/Fixed等）
            label = note.find('span', class_='devsite-label')
            update_type = label.get_text(strip=True) if label else 'Update'
            
            logger.debug(f"解析到类型: {update_type} (URL: {url})")
            
            # 复制 note 以避免修改原始 DOM，方便后续处理
            content_div = BeautifulSoup(str(note), 'lxml').find('div', class_='devsite-release-note')
            
            # 移除 label，避免其进入描述
            if content_div.find('span', class_='devsite-label'):
                content_div.find('span', class_='devsite-label').decompose()
            
            # 转换内容为 Markdown
            description = self._html_to_markdown(content_div, url).strip()
            
            # 查找日期（向前查找最近的h2日期标题）
            # 注意：这里需要用原始 note 查找，因为 content_div 是独立的副本
            date_header = note.find_previous('h2', attrs={'data-text': True})
            publish_date = self._parse_date(date_header.get('data-text', '')) if date_header else None
            
            if not publish_date:
                publish_date = datetime.date.today().strftime('%Y-%m-%d')
            
            # 生成格式化的 title: GCP {product_name} {date}
            title = f"GCP {product_name} {publish_date}"
            
            # 提取结构化文档链接（作为元数据保留，但在描述中已内联）
            doc_links = []
            for link in note.find_all('a', href=True):
                href = link.get('href', '')
                if href and not href.startswith('#'):
                    full_url = self._make_absolute_url(url, href)
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
                'update_type': update_type,
                'doc_links': doc_links
            }
            
            # 生成source_identifier
            source_identifier = self.generate_source_identifier(update)
            update['source_identifier'] = source_identifier
            
            return update
            
        except Exception as e:
            logger.debug(f"解析release note块时出错: {e}")
            return None

    def _make_absolute_url(self, base_url: str, href: str) -> str:
        """生成绝对URL"""
        if href.startswith('/'):
            return urljoin('https://cloud.google.com', href)
        elif href.startswith('http'):
            return href
        else:
            return urljoin(base_url, href)

    def _html_to_markdown(self, element, base_url: str) -> str:
        """
        递归将 HTML 元素转换为 Markdown 文本
        保留结构（列表）、链接和基本格式
        """
        if element is None:
            return ""
            
        from bs4 import NavigableString, Tag
        
        # 文本节点直接返回
        if isinstance(element, NavigableString):
            text = str(element)
            # 只有当文本不是纯空白或属于特定内联元素时才保留
            # 这里的处理比较微妙，为了避免单词粘连，我们通常只压缩多余空白
            return re.sub(r'\s+', ' ', text)
            
        if not isinstance(element, Tag):
            return ""

        content = ""
        
        # 处理特定标签
        if element.name == 'a':
            text = "".join([self._html_to_markdown(child, base_url) for child in element.children]).strip()
            href = element.get('href', '')
            if href:
                full_url = self._make_absolute_url(base_url, href)
                return f"[{text}]({full_url})"
            return text
            
        elif element.name == 'ul':
            for child in element.children:
                if isinstance(child, Tag) and child.name == 'li':
                    item_text = self._html_to_markdown(child, base_url).strip()
                    if item_text:
                        content += f"* {item_text}\n"
            return content + "\n" # 列表后加空行
            
        elif element.name == 'ol':
            idx = 1
            for child in element.children:
                if isinstance(child, Tag) and child.name == 'li':
                    item_text = self._html_to_markdown(child, base_url).strip()
                    if item_text:
                        content += f"{idx}. {item_text}\n"
                        idx += 1
            return content + "\n"
            
        elif element.name in ['p', 'div']:
            # div 和 p 视为块级元素
            parts = []
            for child in element.children:
                parts.append(self._html_to_markdown(child, base_url))
            
            text = "".join(parts).strip()
            if text:
                return text + "\n\n"
            return ""
            
        elif element.name == 'code':
            text = element.get_text()
            return f"`{text}`"
            
        elif element.name in ['strong', 'b']:
            text = "".join([self._html_to_markdown(child, base_url) for child in element.children]).strip()
            return f"**{text}**"
            
        elif element.name in ['em', 'i']:
            text = "".join([self._html_to_markdown(child, base_url) for child in element.children]).strip()
            return f"_{text}_"
            
        elif element.name == 'br':
            return "\n"
            
        else:
            # 默认处理：遍历子节点并拼接
            for child in element.children:
                content += self._html_to_markdown(child, base_url)
            return content
    
    def _parse_date(self, date_text: str) -> Optional[str]:
        """
        解析日期文本
        GCP日期格式：November 14, 2025
        
        Args:
            date_text: 日期文本
            
        Returns:
            标准化的日期 (YYYY-MM-DD格式)
        """
        if not date_text:
            return None
        
        try:
            # 解析 "November 14, 2025" 格式
            date_obj = datetime.datetime.strptime(date_text, '%B %d, %Y')
            return date_obj.strftime('%Y-%m-%d')  # 返回完整日期
        except:
            try:
                # 尝试其他格式
                date_obj = datetime.datetime.strptime(date_text, '%b %d, %Y')
                return date_obj.strftime('%Y-%m-%d')  # 返回完整日期
            except:
                return None
    
    def _get_identifier_strategy(self) -> str:
        """GCP使用content-based策略"""
        return 'content_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        GCP whatsnew: hash(url + date + product + type + description_hash)
        确保同一天、同类型但内容不同的更新被视为独立条目
        
        Args:
            update: 更新数据字典
            
        Returns:
            标识符组件列表
        """
        import hashlib
        
        # 计算描述的哈希值作为指纹
        desc = update.get('description', '')
        desc_hash = hashlib.md5(desc.encode('utf-8')).hexdigest()
        
        return [
            update.get('source_url', ''),
            update.get('publish_date', ''),
            update.get('product_name', ''),
            update.get('update_type', ''),
            desc_hash
        ]
    
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
    crawler = GcpWhatsnewCrawler(config, 'gcp', 'whatsnew')
    crawler.run()
