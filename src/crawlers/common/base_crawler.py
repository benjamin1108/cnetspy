#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import time
import json
import platform
import re
import hashlib
import datetime
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from src.crawlers.common.sync_decorator import sync_to_database_decorator
from src.crawlers.common.content_parser import ContentParser, DateExtractor, content_parser, date_extractor
from src.storage.file_storage import FileStorage, MarkdownGenerator

import requests
from bs4 import BeautifulSoup

# 尝试导入html2text
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CrawlReport:
    """爬取报告数据结构"""
    vendor: str = ''
    source_type: str = ''
    total_discovered: int = 0         # 总发现数
    new_saved: int = 0                # 新增保存数
    skipped_exists: int = 0           # 跳过（已存在）
    skipped_ai_cleaned: int = 0       # 跳过（AI清洗过）
    failed: int = 0                   # 失败数
    ai_cleaned_urls: List[str] = field(default_factory=list)  # 被AI清洗的URL列表
    
    def add_skipped_ai_cleaned(self, url: str, title: str = '') -> None:
        """记录被 AI 清洗的 URL"""
        self.skipped_ai_cleaned += 1
        self.ai_cleaned_urls.append(f"{title[:50]}..." if title else url)
    
    def print_report(self) -> None:
        """打印爬取报告"""
        logger.info("=" * 60)
        logger.info(f"📊 爬取报告: {self.vendor.upper()} - {self.source_type}")
        logger.info("=" * 60)
        logger.info(f"  🔍 发现总数: {self.total_discovered}")
        logger.info(f"  ✅ 新增保存: {self.new_saved}")
        logger.info(f"  ⏭️  跳过(已存在): {self.skipped_exists}")
        logger.info(f"  🧹 跳过(AI清洗): {self.skipped_ai_cleaned}")
        if self.failed > 0:
            logger.info(f"  ❌ 失败数: {self.failed}")
        logger.info("-" * 60)
        
        # 如果有被AI清洗的记录，打印详细列表
        if self.ai_cleaned_urls:
            logger.info("🧹 被AI清洗的记录（非网络相关）:")
            for i, url_or_title in enumerate(self.ai_cleaned_urls[:10], 1):
                logger.info(f"    {i}. {url_or_title}")
            if len(self.ai_cleaned_urls) > 10:
                logger.info(f"    ... 和其他 {len(self.ai_cleaned_urls) - 10} 条")
        
        logger.info("=" * 60)

class BaseCrawler(ABC):
    """爬虫基类，提供基础爬虫功能"""
    
    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        """
        初始化爬虫
        
        Args:
            config: 配置信息
            vendor: 厂商名称（如aws, azure等）
            source_type: 源类型（如blog, docs等）
        """
        self.config = config
        self.vendor = vendor
        self.source_type = source_type
        self.crawler_config = config.get('crawler', {})
        self.timeout = self.crawler_config.get('timeout', 30)
        self.retry = self.crawler_config.get('retry', 3)
        self.interval = self.crawler_config.get('interval', 2)
        self.headers = self.crawler_config.get('headers', {})
        
        # 创建每个爬虫实例的线程锁
        self.lock = threading.RLock()
        
        # 创建保存目录，使用相对于项目根目录的路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.output_dir = os.path.join(base_dir, 'data', 'raw', vendor, source_type)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化HTML到Markdown转换器
        self.html_converter = self._init_html_converter()
        
        # 初始化新组件
        self._content_parser = content_parser
        self._date_extractor = date_extractor
        self._file_storage = FileStorage(base_dir, vendor, source_type)
        
        # 初始化待同步的数据列表（用于批量同步到数据库）
        self._pending_sync_updates = {}
        
        # 分批入库阈值，每累积这么多条就入库一次
        self._batch_sync_size = 50
        
        # 初始化数据库层（延迟加载）
        self._data_layer = None
        
        # 初始化爬取报告
        self._crawl_report = CrawlReport(vendor=vendor, source_type=source_type)
    
    @property
    def data_layer(self):
        """延迟初始化数据库层"""
        if self._data_layer is None:
            from src.storage.database.sqlite_layer import UpdateDataLayer
            self._data_layer = UpdateDataLayer()
        return self._data_layer
    
    @abstractmethod
    def _get_identifier_strategy(self) -> str:
        """
        获取identifier生成策略
        
        Returns:
            'api_based': 使用API base URL + 资源ID（AWS/Azure）
            'content_based': 使用URL + date + product + title（GCP/华为/腾讯云/火山引擎）
        """
        pass
    
    @abstractmethod
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        获取用于生成identifier的组件
        
        Args:
            update: 更新数据字典
            
        Returns:
            组件列表，用于hash生成
        """
        pass
    
    def generate_source_identifier(self, update: Dict[str, Any]) -> str:
        """
        统一的source_identifier生成方法
        
        Args:
            update: 更新数据字典
            
        Returns:
            12位小写十六进制hash字符串
        """
        components = self._get_identifier_components(update)
        content = '|'.join(str(c) for c in components)
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    
    def should_skip_update(
        self,
        update: Dict[str, Any] = None,
        source_url: str = None,
        source_identifier: str = None,
        title: str = ''
    ) -> Tuple[bool, str]:
        """
        统一去重检查 - 支持两种调用方式
        
        检查顺序:
        1. 检查数据库是否已存在
        2. 检查是否已被 AI 清洗（非网络相关已删除）
        
        调用方式:
        1. should_skip_update(source_url=url, source_identifier=id, title=title)
        2. should_skip_update(update=update_dict)
        
        Args:
            update: 完整的更新字典（Pattern 2 爬虫使用）
            source_url: 源URL（Pattern 1 爬虫使用）
            source_identifier: 源标识符（Pattern 1 爬虫使用）
            title: 标题（用于日志）
            
        Returns:
            (should_skip, reason) 元组
            - should_skip: 是否应跳过
            - reason: 'exists' | 'ai_cleaned' | ''
        """
        # 如果传了 update 字典，从中提取参数
        if update is not None:
            source_url = update.get('source_url', '')
            source_identifier = update.get('source_identifier') or self.generate_source_identifier(update)
            title = update.get('title', '')
        
        # 参数校验
        if not source_url:
            return False, ''
        
        # 1. 检查数据库是否已存在
        if self.data_layer.check_update_exists(source_url, source_identifier or ''):
            self._crawl_report.skipped_exists += 1
            return True, 'exists'
        
        # 2. 检查是否被AI清洗过
        if self.data_layer.check_cleaned_by_ai(source_url):
            self._crawl_report.add_skipped_ai_cleaned(source_url, title)
            return True, 'ai_cleaned'
        
        return False, ''
    
    def save_update(self, update: Dict[str, Any]) -> bool:
        """
        保存更新数据（入库 + 保存文件）
        
        Args:
            update: 更新数据字典，必须包含：
                - source_url: 源URL
                - source_identifier: 源标识符（如果没有会自动生成）
                - publish_date: 发布日期
                - title: 标题
                - content: 内容（如果没有，会用 description 填充）
                可选字段：
                - description: 描述
                - product_name: 产品名称
                
        Returns:
            是否成功
        """
        try:
            # 确保有 source_identifier
            if not update.get('source_identifier'):
                update['source_identifier'] = self.generate_source_identifier(update)
            
            source_identifier = update['source_identifier']
            
            # 统一日期格式: YYYY-MM -> YYYY-MM-01
            publish_date = update.get('publish_date', '')
            if publish_date and len(publish_date) == 7:  # YYYY-MM 格式
                publish_date = f"{publish_date}-01"
                update['publish_date'] = publish_date
            
            # 获取 content（不自动用 description 填充，让 _export_to_file 统一处理）
            content = update.get('content', '')
            
            # 保存原始文件
            filepath = self._export_to_file(update, content)
            
            # sync_entry 的 content 字段：优先用 content，否则用 description
            sync_content = content or update.get('description', '')
            
            # 创建同步条目
            sync_entry = {
                'title': update.get('title', ''),
                'publish_date': update.get('publish_date', ''),
                'source_url': update.get('source_url', ''),
                'source_identifier': source_identifier,
                'content': sync_content,
                'description': update.get('description', ''),
                'product_name': update.get('product_name', ''),
                'crawl_time': datetime.datetime.now().isoformat(),
                'file_hash': hashlib.md5(sync_content.encode('utf-8')).hexdigest(),
                'vendor': self.vendor,
                'source_type': self.source_type,
                'filepath': filepath  # 添加文件路径
            }
            
            # 收集待同步数据
            self._pending_sync_updates[source_identifier] = sync_entry
            
            # 达到阈值时自动入库
            if len(self._pending_sync_updates) >= self._batch_sync_size:
                logger.info(f"已累积 {len(self._pending_sync_updates)} 条，执行分批入库...")
                self.batch_sync_to_database()  # 装饰器会清空 _pending_sync_updates
            
            logger.debug(f"已收集更新: {update.get('title', '')[:30]}...")
            return True
            
        except Exception as e:
            logger.error(f"保存更新失败: {e}")
            return False
    
    def save_update_file(self, update: Dict[str, Any], markdown_content: str) -> Optional[str]:
        """
        [已废弃] 统一的文件保存方法，请使用 save_update() 代替
        
        保留此方法仅为向后兼容，内部调用 save_update()
        """
        # 将 markdown_content 作为 content
        update['content'] = markdown_content
        
        # 调用新方法
        success = self.save_update(update)
        
        if success:
            # 可选：导出文件
            return self._export_to_file(update, markdown_content)
        return None
    
    def _export_to_file(self, update: Dict[str, Any], content: str) -> Optional[str]:
        """
        导出更新内容到文件（包含元数据头）
        
        Args:
            update: 更新数据
            content: 内容
            
        Returns:
            文件路径
        """
        try:
            source_url = update.get('source_url', '')
            publish_date = update.get('publish_date', '')
            title = update.get('title', '无标题')
            product_name = update.get('product_name', '')
            
            url_hash = hashlib.md5(source_url.encode('utf-8')).hexdigest()[:8]
            filename = f"{publish_date}_{url_hash}.md"
            filepath = os.path.join(self.output_dir, filename)
            
            # 构建带元数据头的内容
            metadata_lines = [
                f"# {title}",
                "",
                f"**发布时间:** {publish_date}",
                "",
                f"**厂商:** {self.vendor.upper()}",
                "",
            ]
            
            if product_name:
                metadata_lines.extend([
                    f"**产品:** {product_name}",
                    "",
                ])
            
            metadata_lines.extend([
                f"**类型:** {self.source_type}",
                "",
                f"**原始链接:** {source_url}",
                "",
                "---",
                "",
            ])
            
            # 组装正文内容（套用 description/stage/doc_links 等扩展字段）
            body_parts = []
            
            # 如果有 content，直接使用
            if content:
                body_parts.append(content)
            else:
                # 否则组装 description/stage/doc_links
                description = update.get('description', '')
                stage = update.get('stage', '')
                doc_links = update.get('doc_links', [])
                
                if description:
                    body_parts.append("## 内容描述\n")
                    body_parts.append(description)
                
                if stage:
                    body_parts.append("\n## 发布阶段\n")
                    body_parts.append(stage)
                
                if doc_links:
                    body_parts.append("\n## 相关文档\n")
                    for doc_link in doc_links:
                        body_parts.append(f"- [{doc_link.get('text', '')}]({doc_link.get('url', '')})")
            
            final_content = "\n".join(metadata_lines) + '\n'.join(body_parts)
            
            os.makedirs(self.output_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            return filepath
        except Exception as e:
            logger.error(f"导出文件失败: {e}")
            return None
    
    def _close_driver(self) -> None:
        """关闭WebDriver（已废弃，保留空方法以兼容现有代码）"""
        pass
    
    def _get_http(self, url: str) -> Optional[str]:
        """
        使用requests获取网页内容
        
        Args:
            url: 目标URL
            
        Returns:
            网页HTML内容或None（如果失败）
        """
        for i in range(self.retry):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.warning(f"HTTP请求失败 (尝试 {i+1}/{self.retry}): {url} - {e}")
                if i < self.retry - 1:
                    time.sleep(self.interval)
        
        return None
    
    def _init_html_converter(self):
        """
        初始化HTML到Markdown转换器
        
        Returns:
            HTML2Text对象或None
        """
        if HTML2TEXT_AVAILABLE:
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = False
            converter.ignore_tables = False
            converter.body_width = 0  # 不限制宽度
            converter.use_automatic_links = True  # 使用自动链接
            converter.emphasis_mark = '*'  # 强调使用星号
            converter.strong_mark = '**'  # 加粗使用双星号
            converter.wrap_links = False  # 不换行链接
            converter.pad_tables = True  # 表格填充
            return converter
        return None
    
    def save_to_markdown(self, url: str, title: str, content_and_date: Tuple[str, Optional[str]], metadata_extra: Dict[str, Any] = None, batch_mode: bool = True) -> str:
        """
        [已废弃] 将爬取的内容保存为Markdown文件，请使用 save_update() 代替
        
        保留此方法仅为向后兼容
        """
        content, pub_date = content_and_date
        
        if not pub_date:
            pub_date = datetime.datetime.now().strftime("%Y_%m_%d")
        
        # 构建 update 对象
        update = {
            'source_url': url,
            'title': title,
            'content': content,
            'publish_date': pub_date.replace('_', '-') if pub_date else '',
            'vendor': self.vendor,
            'source_type': self.source_type
        }
        if metadata_extra:
            update.update(metadata_extra)
        
        # 调用新方法
        with self.lock:
            self.save_update(update)
            
            # 可选：导出文件
            # 构建Markdown内容
            display_date = pub_date.replace('_', '-') if pub_date else "未知"
            metadata_lines = [
                f"# {title}",
                "",
                f"**原始链接:** [{url}]({url})",
                "",
                f"**发布时间:** {display_date}",
                "",
                f"**厂商:** {self.vendor.upper()}",
                "",
                f"**类型:** {self.source_type.upper()}",
                "",
                "---",
                "",
            ]
            final_content = "\n".join(metadata_lines) + content
            file_path = self._export_to_file(update, final_content)
        
        return file_path
    
    def _create_filename(self, url: str, pub_date: str, ext: str) -> str:
        """
        根据发布日期和URL哈希值创建文件名
        
        Args:
            url: 文章URL
            pub_date: 发布日期（YYYY_MM_DD格式）
            ext: 文件扩展名（如.md）
            
        Returns:
            格式为: YYYY_MM_DD_URLHASH.md 的文件名
        """
        # 生成URL的哈希值（取前8位作为短哈希）
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 组合日期和哈希值
        filename = f"{pub_date}_{url_hash}{ext}"
        
        return filename
    
    def _extract_publish_date(self, soup: BeautifulSoup, list_date: Optional[str] = None, url: str = None) -> str:
        """
        从文章中提取发布日期
        
        Args:
            soup: BeautifulSoup对象
            list_date: 从列表页获取的日期（可选）
            url: 文章URL（可选）
            
        Returns:
            发布日期字符串 (YYYY_MM_DD格式)，如果找不到则返回None
        """
        date_format = "%Y_%m_%d"
        
        # 特别针对博客的日期提取 - 优先检查time标签
        time_elements = soup.find_all('time')
        if time_elements:
            for time_elem in time_elements:
                # 检查具有datePublished属性的time标签
                if time_elem.get('property') == 'datePublished' and time_elem.get('datetime'):
                    datetime_str = time_elem.get('datetime')
                    try:
                        # 处理ISO格式的日期时间 "2025-04-08T17:34:26-07:00"
                        # 从datetime属性中提取日期部分
                        date_part = datetime_str.split('T')[0]
                        parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                        logging.info(f"从time标签的datetime属性解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except (ValueError, IndexError) as e:
                        logging.debug(f"解析time标签的datetime属性失败: {e}")
                
                # 如果没有datetime属性或解析失败，尝试解析标签文本
                date_text = time_elem.get_text().strip()
                if date_text:
                    try:
                        # 尝试解析 "08 APR 2025" 格式
                        parsed_date = datetime.datetime.strptime(date_text, '%d %b %Y')
                        logging.info(f"从time标签的文本内容解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except ValueError:
                        try:
                            # 尝试解析 "April 08, 2025" 格式
                            parsed_date = datetime.datetime.strptime(date_text, '%B %d, %Y')
                            logging.info(f"从time标签的文本内容解析到日期: {parsed_date.strftime(date_format)}")
                            return parsed_date.strftime(date_format)
                        except ValueError:
                            continue

        # 查找元数据中的日期
        meta_published = soup.find('meta', property='article:published_time') or soup.find('meta', property='publish_date')
        if meta_published and meta_published.get('content'):
            try:
                content = meta_published.get('content')
                # 处理ISO格式日期
                if 'T' in content:
                    date_part = content.split('T')[0]
                    parsed_date = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                else:
                    parsed_date = datetime.datetime.strptime(content, '%Y-%m-%d')
                logging.info(f"从meta标签解析到日期: {parsed_date.strftime(date_format)}")
                return parsed_date.strftime(date_format)
            except (ValueError, IndexError) as e:
                logging.debug(f"解析meta标签日期失败: {e}")
        
        # 尝试不同的选择器来定位日期元素
        date_selectors = [
            '.lb-blog-header__date', '.blog-date', '.date', '.published-date', '.post-date',
            '.post-meta time', '.post-meta .date', '.entry-date', '.meta-date',
            'time', '[itemprop="datePublished"]', '.aws-blog-post-date', '.aws-date'
        ]
        
        # 遍历所有可能的选择器
        for selector in date_selectors:
            date_elements = soup.select(selector)
            
            if date_elements:
                for date_elem in date_elements:
                    # 尝试获取datetime属性
                    date_str = date_elem.get('datetime') or date_elem.text.strip()
                    if date_str:
                        try:
                            # 尝试多种日期格式
                            for date_pattern in [
                                '%Y-%m-%d', '%Y/%m/%d', '%b %d, %Y', '%B %d, %Y',
                                '%d %b %Y', '%d %B %Y', '%m/%d/%Y', '%d-%m-%Y',
                                '%Y年%m月%d日', '%Y.%m.%d'
                            ]:
                                try:
                                    # 提取日期字符串
                                    # 如果字符串中包含时间，只保留日期部分
                                    if ' ' in date_str and not any(month in date_str for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'January', 'February', 'March', 'April', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                                        date_str = date_str.split(' ')[0]
                                    
                                    parsed_date = datetime.datetime.strptime(date_str, date_pattern)
                                    logging.info(f"从选择器 {selector} 解析到日期: {parsed_date.strftime(date_format)}")
                                    return parsed_date.strftime(date_format)
                                except ValueError:
                                    continue
                        except Exception as e:
                            logging.debug(f"日期解析错误: {e}")
        
        # 如果通过选择器没找到，尝试在文本中搜索日期模式
        try:
            text = soup.get_text()
            
            # 常见日期格式的正则表达式
            date_patterns = [
                # YYYY-MM-DD
                r'(\d{4}-\d{1,2}-\d{1,2})',
                # YYYY/MM/DD
                r'(\d{4}/\d{1,2}/\d{1,2})',
                # Month DD, YYYY
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',
                # DD Month YYYY
                r'\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
                # MM/DD/YYYY
                r'(\d{1,2}/\d{1,2}/\d{4})',
            ]
            
            for pattern in date_patterns:
                matches = re.search(pattern, text)
                if matches:
                    date_str = matches.group(0)
                    try:
                        # 尝试解析找到的日期
                        if '-' in date_str:
                            parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        elif '/' in date_str:
                            # 尝试两种不同的日期格式（YYYY/MM/DD 或 MM/DD/YYYY）
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%Y/%m/%d')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%m/%d/%Y')
                        elif ',' in date_str:
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%B %d, %Y')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%b %d, %Y')
                        else:
                            try:
                                parsed_date = datetime.datetime.strptime(date_str, '%d %B %Y')
                            except ValueError:
                                parsed_date = datetime.datetime.strptime(date_str, '%d %b %Y')
                        
                        logging.info(f"从文本内容解析到日期: {parsed_date.strftime(date_format)}")
                        return parsed_date.strftime(date_format)
                    except ValueError:
                        continue
        except Exception as e:
            logging.debug(f"从文本提取日期错误: {e}")
        
        # 如果从文章中没有找到日期，使用从列表页获取的日期
        if list_date:
            logging.info(f"使用从列表页获取的日期: {list_date}")
            return list_date
            
        # 如果从URL中寻找可能的日期模式
        if url:
            url_date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if url_date_match:
                try:
                    year, month, day = url_date_match.groups()
                    parsed_date = datetime.datetime(int(year), int(month), int(day))
                    logging.info(f"从URL提取到日期: {parsed_date.strftime(date_format)}")
                    return parsed_date.strftime(date_format)
                except (ValueError, TypeError) as e:
                    logging.debug(f"从URL提取日期出错: {e}")
        
        # 如果找不到日期，使用当前日期
        logging.warning("未找到发布日期，使用当前日期")
        return datetime.datetime.now().strftime(date_format)
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        将HTML转换为Markdown
        
        Args:
            html_content: HTML内容
            
        Returns:
            Markdown内容
        """
        if self.html_converter:
            markdown_content = self.html_converter.handle(html_content)
        else:
            # 简单的HTML到文本转换
            soup = BeautifulSoup(html_content, 'lxml')
            markdown_content = soup.get_text("\n\n", strip=True)
        
        # 清理Markdown
        markdown_content = self._clean_markdown(markdown_content)
        
        return markdown_content
    
    def _clean_markdown(self, markdown_text: str) -> str:
        """
        清理Markdown文本，去除多余内容并美化格式
        
        Args:
            markdown_text: 原始Markdown文本
            
        Returns:
            清理后的Markdown文本
        """
        # 去除连续多个空行
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        # 美化代码块
        markdown_text = re.sub(r'```([^`]+)```', r'\n\n```\1```\n\n', markdown_text)
        
        # 美化图片格式，确保图片前后有空行
        markdown_text = re.sub(r'([^\n])!\[', r'\1\n\n![', markdown_text)
        markdown_text = re.sub(r'\.((?:jpg|jpeg|png|gif|webp|svg))\)([^\n])', r'.\1)\n\n\2', markdown_text)
        
        return markdown_text
    
    def _is_likely_blog_post(self, url: str) -> bool:
        """
        判断URL是否可能是博客文章
        
        Args:
            url: 要检查的URL
            
        Returns:
            True如果URL可能是博客文章，否则False
        """
        # 移除协议和域名部分
        parsed = urlparse(url)
        path = parsed.path
        
        # 博客文章URL的常见模式
        blog_patterns = [
            r'/blogs/[^/]+/[^/]+',  # 如 /blogs/networking-and-content-delivery/article-name
            r'/blog/[^/]+',         # 如 /blog/article-name
            r'/post/[^/]+',         # 如 /post/article-name
            r'/\d{4}/\d{2}/[^/]+',  # 如 /2022/01/article-name (日期格式)
            r'/news/[^/]+',         # 如 /news/article-name
            r'/announcements/[^/]+', # 如 /announcements/article-name
        ]
        
        # 检查是否匹配任何博客文章模式
        for pattern in blog_patterns:
            if re.search(pattern, path):
                return True
        
        # 排除明显的非文章页面
        exclude_patterns = [
            r'/tag/', r'/tags/', r'/category/', r'/categories/',
            r'/author/', r'/about/', r'/contact/', r'/feed/',
            r'/archive/', r'/archives/', r'/page/\d+', r'/search/'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, path):
                return False
                
        # 检查是否在URL路径中包含特定关键词
        blog_keywords = ['post', 'article', 'blog', 'news', 'announcement']
        for keyword in blog_keywords:
            if keyword in path.lower():
                return True
                
        # 默认返回False，宁可错过也不要误报
        return False
    
    def process_articles_in_batches(self, article_info: List[Tuple], batch_size: int = 10) -> List[str]:
        """
        分批处理文章，减少锁的竞争和文件写入次数
        
        Args:
            article_info: 文章信息列表，每项为(标题, URL, 日期)元组
            batch_size: 每批处理的文章数量，默认为10
            
        Returns:
            保存的文件路径列表
        """
        saved_files = []
        
        # 检查是否启用了强制模式
        force_mode = self.crawler_config.get('force', False)
        if force_mode:
            logger.info("强制模式已启用，将重新爬取所有文章")
        
        # 分批处理文章
        for i in range(0, len(article_info), batch_size):
            batch = article_info[i:i+batch_size]
            logger.info(f"处理第 {i//batch_size + 1} 批文章，共 {len(batch)} 篇")
            
            # 过滤已爬取的文章
            filtered_batch = []
            for title, url, list_date in batch:
                if force_mode:
                    filtered_batch.append((title, url, list_date))
                    logger.info(f"强制模式：将重新爬取文章: {title} ({url})")
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
                        filtered_batch.append((title, url, list_date))
            
            # 处理这一批文章
            for idx, (title, url, list_date) in enumerate(filtered_batch, 1):
                try:
                    logger.info(f"正在爬取第 {idx}/{len(filtered_batch)} 篇文章: {title}")
                    
                    # 获取文章内容
                    article_html = self._get_article_html(url)
                    if not article_html:
                        logger.warning(f"获取文章内容失败: {url}")
                        continue
                    
                    # 解析文章内容和日期
                    article_content, pub_date = self._parse_article_content(url, article_html, list_date)
                    
                    # 保存为Markdown
                    file_path = self.save_to_markdown(url, title, (article_content, pub_date))
                    saved_files.append(file_path)
                    logger.info(f"已保存文章: {title} -> {file_path}")
                    
                    # 间隔一段时间再爬取下一篇
                    if idx < len(filtered_batch):
                        time.sleep(self.interval)
                        
                except Exception as e:
                    logger.error(f"爬取文章失败: {url} - {e}")
            
            # 批量同步到数据库
            if self._pending_sync_updates:
                self.batch_sync_to_database()
        
        return saved_files
    
    def _get_article_html(self, url: str) -> Optional[str]:
        """
        获取文章HTML内容
        
        Args:
            url: 文章URL
            
        Returns:
            文章HTML内容或None（如果失败）
        """
        # 尝试使用requests获取文章内容
        try:
            logger.info(f"使用requests库获取文章内容: {url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("使用requests库成功获取到文章内容")
                return response.text
            else:
                logger.error(f"请求返回非成功状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"使用requests库获取文章失败: {e}")
        
        return None
    
    def _parse_article_content(self, url: str, html: str, list_date: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        从文章页面解析文章内容和发布日期
        
        Args:
            url: 文章URL
            html: 文章页面HTML
            list_date: 从列表页获取的日期（可能为None）
            
        Returns:
            (文章内容, 发布日期)元组，如果找不到日期则使用列表页日期或当前日期
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # 提取发布日期
        pub_date = self._extract_publish_date(soup, list_date, url)
        
        # 提取文章内容
        article_content = self._extract_article_content(soup, url)
        
        return article_content, pub_date
    
    def _extract_article_content(self, soup: BeautifulSoup, url: str) -> str:
        """
        从文章页面提取文章内容
        
        Args:
            soup: BeautifulSoup对象
            url: 文章URL
            
        Returns:
            Markdown格式的文章内容
        """
        # 尝试定位文章主体内容
        content_selectors = [
            'article', 
            '.entry-content', 
            '.post-content', 
            '.article-content', 
            '.main-content',
            '.blog-post',
            '.content-container',
            'main',
            '#main-content'
        ]
        
        article_elem = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # 选择最长的元素作为文章主体
                article_elem = max(elements, key=lambda x: len(str(x)))
                break
        
        # 如果没有找到文章主体，使用页面主体
        if not article_elem:
            article_elem = soup.find('body')
            
        if not article_elem:
            logger.warning(f"未找到文章主体: {url}")
            return "无法提取文章内容"
        
        # 清理非内容元素
        for elem in article_elem.select('header, footer, sidebar, .sidebar, nav, .navigation, .ad, .ads, .comments, .social-share'):
            elem.decompose()
        
        # 转换为Markdown
        html = str(article_elem)
        if self.html_converter:
            markdown_content = self.html_converter.handle(html)
        else:
            # 简单的HTML到文本转换
            markdown_content = article_elem.get_text("\n\n", strip=True)
        
        # 清理和美化Markdown
        markdown_content = self._clean_markdown(markdown_content)
        
        return markdown_content
    
    @sync_to_database_decorator
    def batch_sync_to_database(self) -> None:
        """
        批量同步所有待同步的数据到数据库
        
        在爬取完成后调用此方法，一次性同步所有收集的数据
        注意：实际同步由装饰器执行，此方法仅作为触发入口
        """
        if not self._pending_sync_updates:
            logger.debug("无待同步数据")
            return
        
        # 注意：不要在这里清空，让装饰器处理完后再清空
        # 装饰器会读取 self._pending_sync_updates 并执行实际同步
    
    def should_crawl(self, url: str, source_identifier: str = '', title: str = '') -> bool:
        """
        检查是否需要爬取某个URL
        
        Args:
            url: 要检查的URL
            source_identifier: 源标识符
            title: 标题（用于日志）
            
        Returns:
            True 如果需要爬取，False 如果不需要
        """
        should_skip, reason = self.should_skip_update(
            source_url=url, 
            source_identifier=source_identifier, 
            title=title
        )
        if should_skip:
            if reason == 'exists':
                logger.debug(f"跳过已爬取: {url}")
            elif reason == 'ai_cleaned':
                logger.info(f"跳过AI清洗: {title or url}")
            return False
        return True
    
    @property
    def crawl_report(self) -> CrawlReport:
        """获取爬取报告"""
        return self._crawl_report
    
    def set_total_discovered(self, count: int) -> None:
        """设置发现总数（在子类中调用）"""
        self._crawl_report.total_discovered = count
    
    def record_failed(self) -> None:
        """记录失败数（在子类中调用）"""
        self._crawl_report.failed += 1

    def run(self) -> List[str]:
        """
        运行爬虫
        
        Returns:
            保存的文件路径列表
        """
        try:
            logger.info(f"开始爬取 {self.vendor} {self.source_type}")
            
            # 清空待同步列表
            self._pending_sync_updates = {}
            
            # 重置爬取报告
            self._crawl_report = CrawlReport(vendor=self.vendor, source_type=self.source_type)
            
            results = self._crawl()
            
            # 批量同步到数据库
            if self._pending_sync_updates:
                logger.debug(f"待同步数据: {len(self._pending_sync_updates)} 条")
                self.batch_sync_to_database()
            
            # 更新爬取报告
            self._crawl_report.new_saved = len(results)
            
            # 打印爬取报告
            self._crawl_report.print_report()
            
            logger.info(f"爬取完成 {self.vendor} {self.source_type}, 共爬取 {len(results)} 个文件")
            return results
        except Exception as e:
            logger.error(f"爬取失败 {self.vendor} {self.source_type}: {e}")
            # 即使爬取失败，也尝试同步已收集的数据
            if self._pending_sync_updates:
                logger.info(f"爬取失败，但仍有 {len(self._pending_sync_updates)} 条待同步数据，执行批量同步")
                try:
                    self.batch_sync_to_database()
                except Exception as sync_e:
                    logger.error(f"批量同步失败: {sync_e}")
            return []
        finally:
            self._close_driver()
    
    @abstractmethod
    def _crawl(self) -> List[str]:
        """
        具体爬虫逻辑，由子类实现
        
        Returns:
            保存的文件路径列表
        """
        pass
