#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prompt 模板管理模块

负责管理 AI 分析所需的 Prompt 模板，支持版本控制和动态参数注入
Prompt 模板存储在 prompts/ 目录下的独立文件中
"""

from typing import Dict, Any, List
import yaml
from pathlib import Path
from src.models.update import UpdateType


class PromptTemplates:
    """
    Prompt 模板管理器
    
    注：需要通过 set_config() 设置配置后才能使用
    """
    
    VERSION = "v1.2"
    
    # 类级配置
    _config = None
    _subcategory_config = None
    _prompt_cache: Dict[str, str] = {}
    
    # Prompt 文件目录
    PROMPTS_DIR = Path(__file__).parent / "prompts"
    
    @classmethod
    def _load_prompt_template(cls, template_name: str) -> str:
        """
        从文件加载 Prompt 模板
        
        Args:
            template_name: 模板名称（不含扩展名）
            
        Returns:
            Prompt 模板内容
        """
        if template_name in cls._prompt_cache:
            return cls._prompt_cache[template_name]
        
        template_path = cls.PROMPTS_DIR / f"{template_name}.prompt.txt"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt 模板文件不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        cls._prompt_cache[template_name] = content
        return content
    
    @classmethod
    def _load_subcategory_config(cls) -> Dict[str, List[str]]:
        """加载 subcategory 枚举配置"""
        if cls._subcategory_config is not None:
            return cls._subcategory_config
        
        config_path = Path(__file__).parent.parent.parent / "config" / "subcategory.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._subcategory_config = yaml.safe_load(f) or {}
        else:
            cls._subcategory_config = {}
        
        return cls._subcategory_config
    
    @classmethod
    def get_subcategories_for_vendor(cls, vendor: str) -> List[str]:
        """获取指定厂商的 subcategory 枚举列表"""
        config = cls._load_subcategory_config()
        return config.get(vendor.lower(), [])
    
    @classmethod
    def set_config(cls, config: Dict[str, Any]):
        """设置配置"""
        cls._config = config
    
    @classmethod
    def _get_validation_config(cls) -> Dict[str, Any]:
        """获取验证配置"""
        # 默认配置
        defaults = {
            'title_max_length': 50,
            'summary_min_length': 150,
            'summary_max_length': 500,
            'summary_max_items': 5,
            'tags_min_count': 3,
            'tags_max_count': 8,
        }
        
        if cls._config is None:
            return defaults
        
        # 尝试从不同层级获取 validation 配置
        validation = cls._config.get('validation', {})
        if not validation:
            # 尝试从 default.validation 获取
            validation = cls._config.get('default', {}).get('validation', {})
        
        # 合并默认值
        return {**defaults, **validation}
    
    @staticmethod
    def get_update_analysis_prompt(update_data: Dict[str, Any]) -> str:
        """
        获取更新分析的 Prompt
        
        Args:
            update_data: 更新数据字典，包含 vendor, source_channel, title, content 等字段
            
        Returns:
            完整的 Prompt 字符串
        """
        # 获取验证配置
        validation = PromptTemplates._get_validation_config()
        
        # 获取 UpdateType 枚举值列表
        update_type_values = ", ".join(UpdateType.values())
        
        # 提取必要字段
        vendor = update_data.get('vendor', 'unknown')
        source_channel = update_data.get('source_channel', 'unknown')
        title = update_data.get('title', '')
        product_name = update_data.get('product_name', '')
        product_category = update_data.get('product_category', '')
        content = update_data.get('content', '')
        doc_links = update_data.get('doc_links', [])
        
        # 格式化文档链接
        if doc_links:
            doc_links_str = '\n'.join([f"- {link.get('text', 'Link')}: {link.get('url', '')}" for link in doc_links])
        else:
            doc_links_str = '无'
        
        # 截断过长的内容（防止超过 token 限制）
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        # 获取厂商专属 subcategory 枚举
        subcategories = PromptTemplates.get_subcategories_for_vendor(vendor)
        if subcategories:
            subcategory_enum = '\n'.join([f"     * {cat}" for cat in subcategories])
        else:
            subcategory_enum = "     * (无预定义枚举，请基于内容动态判定，使用小写英文+下划线格式)"
        
        # 加载 Prompt 模板并填充参数
        template = PromptTemplates._load_prompt_template('update_analysis')
        
        prompt = template.format(
            vendor=vendor,
            source_channel=source_channel,
            title=title,
            product_name=product_name,
            product_category=product_category,
            doc_links_str=doc_links_str,
            content=content,
            title_max_length=validation['title_max_length'],
            summary_min_length=validation['summary_min_length'],
            summary_max_length=validation['summary_max_length'],
            summary_max_items=validation['summary_max_items'],
            tags_min_count=validation['tags_min_count'],
            tags_max_count=validation['tags_max_count'],
            update_type_values=update_type_values,
            subcategory_enum=subcategory_enum
        )
        
        return prompt
    
    @staticmethod
    def get_blog_translation_prompt(content: str) -> str:
        """
        获取博客全文翻译的 Prompt
        
        Args:
            content: 原始英文博客内容
            
        Returns:
            完整的翻译 Prompt 字符串
        """
        # 截断过长的内容（防止超过 token 限制）
        max_content_length = 30000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[内容过长，已截断]"
        
        # 加载 Prompt 模板并填充参数
        template = PromptTemplates._load_prompt_template('blog_translation')
        
        prompt = template.format(content=content)
        
        return prompt
    
    @staticmethod
    def is_blog_source(source_channel: str) -> bool:
        """
        判断是否为博客类型的数据源
        
        Args:
            source_channel: 数据源渠道
            
        Returns:
            是否为博客类型
        """
        if not source_channel:
            return False
        source_channel_lower = source_channel.lower()
        return 'blog' in source_channel_lower
    
    @staticmethod
    def get_version() -> str:
        """获取 Prompt 模板版本"""
        return PromptTemplates.VERSION
