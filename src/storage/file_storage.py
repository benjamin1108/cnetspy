#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件存储管理器
处理爬取内容的文件保存
"""

import os
import hashlib
import datetime
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class FileStorage:
    """文件存储管理器"""
    
    def __init__(self, base_dir: str, vendor: str, source_type: str):
        """
        初始化文件存储管理器
        
        Args:
            base_dir: 项目根目录
            vendor: 厂商名称
            source_type: 源类型
        """
        self.base_dir = base_dir
        self.vendor = vendor
        self.source_type = source_type
        self.output_dir = os.path.join(base_dir, 'data', 'raw', vendor, source_type)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 文件写入锁
        self.lock = threading.RLock()
    
    def create_filename(self, url: str, pub_date: str, ext: str = '.md') -> str:
        """
        根据发布日期和URL哈希值创建文件名
        
        Args:
            url: 文章URL
            pub_date: 发布日期（YYYY_MM_DD或YYYY-MM-DD格式）
            ext: 文件扩展名
            
        Returns:
            格式为: YYYY_MM_DD_URLHASH.md 的文件名
        """
        # 标准化日期格式
        pub_date = pub_date.replace('-', '_')
        
        # 生成URL的哈希值（取前8位）
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        return f"{pub_date}_{url_hash}{ext}"
    
    def save_markdown(
        self, 
        url: str, 
        title: str, 
        content: str, 
        pub_date: str,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        保存Markdown文件
        
        Args:
            url: 文章URL
            title: 文章标题
            content: 文章内容
            pub_date: 发布日期
            extra_metadata: 额外元数据
            
        Returns:
            保存的文件路径
        """
        filename = self.create_filename(url, pub_date)
        file_path = os.path.join(self.output_dir, filename)
        
        # 构建Markdown内容
        display_date = pub_date.replace('_', '-')
        
        lines = [
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
        ]
        
        # 添加额外元数据
        if extra_metadata:
            for key, value in extra_metadata.items():
                if value:
                    lines.append(f"**{key}:** {value}")
                    lines.append("")
        
        lines.extend([
            "---",
            "",
            content
        ])
        
        final_content = "\n".join(lines)
        
        # 线程安全地写入文件
        with self.lock:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
        
        return file_path
    
    def save_update_file(
        self, 
        update: Dict[str, Any], 
        markdown_content: str
    ) -> Optional[str]:
        """
        保存更新文件（使用预生成的Markdown内容）
        
        Args:
            update: 更新数据字典
            markdown_content: Markdown格式的内容
            
        Returns:
            文件路径，失败返回None
        """
        try:
            source_url = update.get('source_url', '')
            publish_date = update.get('publish_date', '')
            
            filename = self.create_filename(source_url, publish_date)
            filepath = os.path.join(self.output_dir, filename)
            
            with self.lock:
                os.makedirs(self.output_dir, exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
            
            return filepath
            
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return None
    
    def get_file_hash(self, content: str) -> str:
        """计算内容的MD5哈希值"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def file_exists(self, url: str, pub_date: str) -> bool:
        """检查文件是否已存在"""
        filename = self.create_filename(url, pub_date)
        file_path = os.path.join(self.output_dir, filename)
        return os.path.exists(file_path)


class MarkdownGenerator:
    """Markdown内容生成器"""
    
    @staticmethod
    def generate_update_markdown(
        title: str,
        publish_date: str,
        vendor: str,
        source_type: str,
        source_url: str,
        content: str,
        product_name: str = '',
        update_type: str = '',
        doc_links: list = None
    ) -> str:
        """
        生成标准化的更新Markdown内容
        """
        lines = [
            f"# {title}",
            "",
            f"**发布时间:** {publish_date}",
            "",
            f"**厂商:** {vendor.upper()}",
            "",
        ]
        
        if product_name:
            lines.extend([f"**产品:** {product_name}", ""])
        
        if update_type:
            lines.extend([f"**类型:** {update_type}", ""])
        else:
            lines.extend([f"**类型:** {source_type.upper()}", ""])
        
        lines.extend([
            f"**原始链接:** {source_url}",
            "",
            "---",
            "",
            content
        ])
        
        if doc_links:
            lines.extend(["", "## 相关文档", ""])
            for doc_link in doc_links:
                text = doc_link.get('text', 'Link')
                url = doc_link.get('url', '')
                lines.append(f"- [{text}]({url})")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_blog_markdown(
        title: str,
        url: str,
        pub_date: str,
        vendor: str,
        source_type: str,
        content: str
    ) -> str:
        """生成博客文章的Markdown内容"""
        display_date = pub_date.replace('_', '-')
        
        lines = [
            f"# {title}",
            "",
            f"**原始链接:** [{url}]({url})",
            "",
            f"**发布时间:** {display_date}",
            "",
            f"**厂商:** {vendor.upper()}",
            "",
            f"**类型:** {source_type.upper()}",
            "",
            "---",
            "",
            content
        ]
        
        return "\n".join(lines)
