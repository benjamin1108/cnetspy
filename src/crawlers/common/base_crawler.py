#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import time
import re
import hashlib
import datetime
import threading
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from src.crawlers.common.content_parser import ContentParser, DateExtractor, content_parser
from src.crawlers.common.sync_decorator import CrawlerIntegration
from src.storage.file_storage import FileStorage
from src.storage.database.sqlite_layer import UpdateDataLayer

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
    """爬取报告数据结构（线程安全）"""
    vendor: str = ''
    source_type: str = ''
    total_discovered: int = 0         # 总发现数
    new_saved: int = 0                # 新增保存数
    skipped_exists: int = 0           # 跳过（已存在）
    skipped_ai_cleaned: int = 0       # 跳过（AI清洗过）
    skipped_too_old: int = 0          # 跳过（超出时间窗口）
    failed: int = 0                   # 失败数
    ai_cleaned_urls: List[str] = field(default_factory=list)  # 被AI清洗的URL列表
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    
    def increment_discovered(self, count: int = 1) -> None:
        """线程安全地增加发现数"""
        with self._lock:
            self.total_discovered += count
    
    def increment_skipped_exists(self) -> None:
        """线程安全地增加跳过数（已存在）"""
        with self._lock:
            self.skipped_exists += 1
    
    def increment_new_saved(self) -> None:
        """线程安全地增加新增保存数"""
        with self._lock:
            self.new_saved += 1
    
    def increment_failed(self) -> None:
        """线程安全地增加失败数"""
        with self._lock:
            self.failed += 1
    
    def add_skipped_ai_cleaned(self, url: str, title: str = '') -> None:
        """线程安全地记录被 AI 清洗的 URL"""
        with self._lock:
            self.skipped_ai_cleaned += 1
            self.ai_cleaned_urls.append(f"{title[:50]}..." if title else url)

    def increment_skipped_too_old(self) -> None:
        """线程安全地增加跳过数（超出时间窗口）"""
        with self._lock:
            self.skipped_too_old += 1
    
    def print_report(self) -> None:
        """打印爬取报告"""
        logger.info("=" * 60)
        logger.info(f"📊 爬取报告: {self.vendor.upper()} - {self.source_type}")
        logger.info("=" * 60)
        logger.info(f"  🔍 发现总数: {self.total_discovered}")
        logger.info(f"  ✅ 新增保存: {self.new_saved}")
        logger.info(f"  ⏭️  跳过(已存在): {self.skipped_exists}")
        logger.info(f"  🧹 跳过(AI清洗): {self.skipped_ai_cleaned}")
        if self.skipped_too_old > 0:
            logger.info(f"  🗓️  跳过(超出窗口): {self.skipped_too_old}")
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
        self.source_config = config.get('sources', {}).get(vendor, {}).get(source_type, {})
        self.timeout = self.crawler_config.get('timeout', 30)
        self.retry = self.crawler_config.get('retry', 3)
        self.interval = self.crawler_config.get('interval', 2)
        self.headers = self.crawler_config.get('headers', {})
        self.lookback_days = int(
            self.source_config.get(
                'lookback_days',
                self.crawler_config.get('lookback_days', 30)
            )
        )
        
        # 创建保存目录，使用相对于项目根目录的路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.output_dir = os.path.join(base_dir, 'data', 'raw', vendor, source_type)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化内容解析器（复用全局单例）
        self._content_parser = content_parser
        # 保留 html_converter 属性以兼容子类
        self.html_converter = self._content_parser.html_converter
        
        # 初始化文件存储
        self._file_storage = FileStorage(base_dir, vendor, source_type)
        
        # 初始化待同步的数据列表（用于批量同步到数据库）
        self._pending_sync_updates = {}
        
        # 分批入库阈值，每累积这么多条就入库一次
        self._batch_sync_size = 50
        
        # 初始化数据库层（启动时加载，确保 ImportError 早期暴露）
        self._data_layer = UpdateDataLayer()
        
        # 初始化爬虫集成器（用于批量同步）
        self._crawler_integration = CrawlerIntegration()
        
        # 初始化爬取报告
        self._crawl_report = CrawlReport(vendor=vendor, source_type=source_type)
    
    @property
    def data_layer(self):
        """获取数据库层"""
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

    @staticmethod
    def normalize_publish_date(publish_date: str) -> str:
        """统一日期格式，支持 YYYY-MM -> YYYY-MM-01。"""
        if publish_date and len(publish_date) == 7:
            return f"{publish_date}-01"
        return publish_date or ''

    def _get_cutoff_date(self) -> Optional[datetime.date]:
        """获取时间窗口截止日期。"""
        if self.lookback_days <= 0:
            return None
        return datetime.date.today() - datetime.timedelta(days=self.lookback_days)

    def is_update_too_old(self, publish_date: str) -> bool:
        """检查更新是否超出时间窗口。"""
        normalized = self.normalize_publish_date(publish_date)
        if not normalized:
            return False

        cutoff_date = self._get_cutoff_date()
        if cutoff_date is None:
            return False

        try:
            publish_day = datetime.date.fromisoformat(normalized)
        except ValueError:
            return False

        return publish_day < cutoff_date

    def is_force_mode_enabled(self) -> bool:
        """当前爬虫是否启用了强制模式。"""
        return bool(self.crawler_config.get('force', False))

    @staticmethod
    def normalize_identifier_text(text: str) -> str:
        """
        对内容做稳定化处理，降低 Markdown/空白差异对 identifier 的影响。
        """
        if not text:
            return ''

        normalized = str(text)
        normalized = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def should_skip_update(
        self,
        update: Dict[str, Any] = None,
        source_url: str = None,
        source_identifier: str = None,
        publish_date: str = None,
        title: str = ''
    ) -> Tuple[bool, str]:
        """
        统一去重检查 - 支持两种调用方式

        检查顺序:
        1. 检查数据库是否已存在
        2. 检查是否超出抓取时间窗口（仅对库中不存在的新条目）
        3. 检查是否已被 AI 清洗（非网络相关已删除）
        
        调用方式:
        1. should_skip_update(source_url=url, source_identifier=id, title=title)
        2. should_skip_update(update=update_dict)
        
        Args:
            update: 完整的更新字典（Pattern 2 爬虫使用）
            source_url: 源URL（Pattern 1 爬虫使用）
            source_identifier: 源标识符（Pattern 1 爬虫使用）
            publish_date: 发布日期
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
            publish_date = update.get('publish_date', '')
            title = update.get('title', '')
        
        # 参数校验
        if not source_url:
            return False, ''

        if self.is_force_mode_enabled():
            return False, ''

        normalized_publish_date = self.normalize_publish_date(publish_date or '')

        # 1. 检查数据库是否已存在（优先，确保统计准确）
        if self.data_layer.check_update_exists(
            source_url,
            source_identifier or '',
            vendor=self.vendor,
            source_channel=self.source_type,
        ):
            self._crawl_report.increment_skipped_exists()
            return True, 'exists'

        # 2. 检查是否超出抓取时间窗口（仅对库中不存在的新条目生效）
        if self.is_update_too_old(normalized_publish_date):
            self._crawl_report.increment_skipped_too_old()
            return True, 'too_old'

        # 3. 检查是否被AI清洗过
        if self.data_layer.check_cleaned_by_ai(source_url, source_identifier):
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
            publish_date = self.normalize_publish_date(update.get('publish_date', ''))
            update['publish_date'] = publish_date

            if not self.is_force_mode_enabled() and self.is_update_too_old(publish_date):
                self._crawl_report.increment_skipped_too_old()
                logger.debug(f"跳过超出时间窗口的更新: {update.get('title', '')}")
                return False
            
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
                'update_type': update.get('update_type', ''),  # 显式传递 update_type
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
        
        # 调用新方法（内部已包含文件导出）
        success = self.save_update(update)
        
        # 返回文件路径（从 pending_sync_updates 中获取）
        if success:
            source_identifier = update.get('source_identifier')
            if source_identifier and source_identifier in self._pending_sync_updates:
                return self._pending_sync_updates[source_identifier].get('filepath')
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
        
        # 调用新方法（内部已包含文件导出）
        self.save_update(update)
        
        # 返回文件路径
        source_identifier = update.get('source_identifier')
        if source_identifier and source_identifier in self._pending_sync_updates:
            return self._pending_sync_updates[source_identifier].get('filepath', '')
        return ''
    
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
        
        委托给 DateExtractor 处理，子类可重写此方法实现特定解析策略
        
        Args:
            soup: BeautifulSoup对象
            list_date: 从列表页获取的日期（可选）
            url: 文章URL（可选）
            
        Returns:
            发布日期字符串 (YYYY_MM_DD格式)
        """
        return DateExtractor.extract_publish_date(soup, list_date, url)
    
    def _html_to_markdown(self, html_content: str) -> str:
        """将HTML转换为Markdown（委托给 ContentParser）"""
        return self._content_parser.html_to_markdown(html_content)
    
    def _clean_markdown(self, markdown_text: str) -> str:
        """清理Markdown文本（委托给 ContentParser）"""
        return self._content_parser.clean_markdown(markdown_text)
    
    def _is_likely_blog_post(self, url: str) -> bool:
        """判断URL是否可能是博客文章（委托给 ContentParser）"""
        return self._content_parser.is_likely_blog_post(url)
    
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
    
    def _get_with_playwright(self, url: str, wait_for_selector: str = None, blocked_resources: List[str] = None) -> Optional[str]:
        """
        使用Playwright获取页面内容（带重试和懒加载处理）
        
        Args:
            url: 目标URL
            wait_for_selector: 等待的CSS选择器（可选）
            blocked_resources: 要阻止加载的资源类型列表（可选）
            
        Returns:
            网页HTML内容或None（如果失败）
        """
        from playwright.sync_api import sync_playwright
        
        # 默认阻止的资源类型
        if blocked_resources is None:
            blocked_resources = ["image", "media", "font", "stylesheet"]
        
        for i in range(self.retry):
            try:
                logger.info(f"使用Playwright获取页面: {url}")
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,  # 使用新版headless模式
                        args=['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                    )
                    try:
                        page = browser.new_page()
                        
                        # 拦截并阻止非必要资源加载
                        if blocked_resources:
                            page.route("**/*", lambda route: route.abort() 
                                if route.request.resource_type in blocked_resources 
                                else route.continue_())
                            
                        page.set_default_timeout(30000)
                        page.goto(url, wait_until='domcontentloaded')
                        
                        # 等待主要内容加载
                        if wait_for_selector:
                            try:
                                page.wait_for_selector(wait_for_selector, timeout=10000)
                            except:
                                pass
                        else:
                            try:
                                page.wait_for_selector('main, article, body', timeout=10000)
                            except:
                                pass
                        
                        # 滚动触发懒加载
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                        page.wait_for_timeout(500)
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        page.wait_for_timeout(500)
                        page.evaluate('window.scrollTo(0, 0)')
                        page.wait_for_timeout(500)
                        
                        html = page.content()
                        logger.info(f"成功获取页面内容，大小: {len(html)} 字节")
                        return html
                    finally:
                        browser.close()
            except Exception as e:
                logger.warning(f"Playwright获取页面失败 (尝试 {i+1}/{self.retry}): {url} - {e}")
                if i < self.retry - 1:
                    retry_interval = self.interval * (i + 1)
                    logger.info(f"等待 {retry_interval} 秒后重试...")
                    time.sleep(retry_interval)
            except asyncio.CancelledError:
                logger.warning(f"Playwright任务被取消: {url}")
                return None
            except BaseException as e:
                logger.error(f"Playwright发生严重错误: {url} - {e}")
                return None
        
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
        """从文章页面提取文章内容（委托给 ContentParser）"""
        return self._content_parser.extract_article_content(soup, url)
    
    def batch_sync_to_database(self) -> None:
        """
        批量同步所有待同步的数据到数据库
        
        在爬取完成后调用此方法，一次性同步所有收集的数据
        """
        if not self._pending_sync_updates:
            logger.debug("无待同步数据")
            return
        
        try:
            force_mode = self.crawler_config.get('force', False)
            
            # 显式调用批量同步
            sync_result = self._crawler_integration.batch_sync_to_database(
                self.vendor,
                self.source_type,
                self._pending_sync_updates,
                force_update=force_mode
            )
            
            if force_mode:
                logger.info(f"数据库强制更新完成: 更新{sync_result.get('success', 0)}, 失败{sync_result.get('failed', 0)}")
            else:
                logger.info(f"数据库同步完成: 成功{sync_result.get('success', 0)}, 跳过{sync_result.get('skipped', 0)}, 失败{sync_result.get('failed', 0)}")
            
            # 同步完成后清空
            self._pending_sync_updates = {}
            
        except Exception as e:
            logger.error(f"批量同步到数据库失败: {e}")
            self._pending_sync_updates = {}
    
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
        """线程安全地增加发现总数（在子类中调用）"""
        self._crawl_report.increment_discovered(count)
    
    def record_failed(self) -> None:
        """线程安全地记录失败数（在子类中调用）"""
        self._crawl_report.increment_failed()

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
