#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新记录分析器

基于 Gemini 对单条更新记录进行 AI 分析
"""

import json
import re
from typing import Dict, Any, Optional
from .base_analyzer import BaseAnalyzer
from .gemini_client import GeminiClient
from .prompt_templates import PromptTemplates
from src.models.update import UpdateType


class UpdateAnalyzer(BaseAnalyzer):
    """单条更新记录分析器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化分析器
        
        Args:
            config: AI 模型配置字典
        """
        super().__init__(config)
        
        # 设置 Prompt 模板配置
        PromptTemplates.set_config(config)
        
        # 初始化 Gemini 客户端
        self.gemini_client = GeminiClient(config)
        
        # 加载验证配置
        validation_config = config.get('validation', {})
        self.title_max_length = validation_config.get('title_max_length', 50)
        self.summary_min_length = validation_config.get('summary_min_length', 150)
        self.summary_max_length = validation_config.get('summary_max_length', 500)
        self.summary_max_items = validation_config.get('summary_max_items', 5)
        self.tags_min_count = validation_config.get('tags_min_count', 3)
        self.tags_max_count = validation_config.get('tags_max_count', 8)
        
        self.logger.info("UpdateAnalyzer 初始化成功")
    
    def analyze(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        分析单条更新记录
        
        Args:
            update_data: 更新数据字典，包含 vendor, source_channel, title, content 等字段
            
        Returns:
            分析结果字典，包含 title_translated, content_summary, update_type, 
            product_subcategory, tags 字段；博客类型还包含 content_translated；失败返回 None
        """
        # 验证输入
        if not self.validate_input(update_data):
            return None
        
        try:
            # 构建 Prompt
            prompt = PromptTemplates.get_update_analysis_prompt(update_data)
            
            # 调用 Gemini API
            self.logger.info(f"开始分析更新: {update_data.get('update_id', 'unknown')}")
            response_text = self.gemini_client.generate_content(prompt)
            
            # 解析 JSON 响应
            result = self.gemini_client.parse_json_response(response_text)
            
            # 验证响应
            if not self.gemini_client.validate_response(result):
                self.logger.error("响应验证失败，数据不完整")
                return None
            
            # 字段验证和修正
            validated_result = self._validate_and_fix_fields(result, update_data)
            
            # 博客类型：额外进行全文翻译
            source_channel = update_data.get('source_channel', '')
            if PromptTemplates.is_blog_source(source_channel):
                content_translated = self._translate_blog_content(update_data)
                validated_result['content_translated'] = content_translated
            
            self.logger.info(f"分析完成: {update_data.get('update_id', 'unknown')}")
            return validated_result
            
        except Exception as e:
            self.logger.error(f"分析失败: {e}")
            return None
    
    def _translate_blog_content(self, update_data: Dict[str, Any]) -> str:
        """
        翻译博客全文内容
        
        Args:
            update_data: 更新数据字典
            
        Returns:
            翻译后的中文内容，失败返回空字符串
        """
        content = update_data.get('content', '')
        if not content:
            return ''
        
        try:
            self.logger.info(f"[全文翻译] 开始翻译博客内容: {update_data.get('update_id', 'unknown')} (原文长度: {len(content)})")
            
            # 构建翻译 Prompt
            prompt = PromptTemplates.get_content_translation_prompt(content)
            
            # 调用 Gemini API 进行翻译（使用纯文本模式）
            translated_content = self.gemini_client.generate_text(prompt)
            
            if translated_content:
                self.logger.info(f"[全文翻译] 翻译完成: {update_data.get('update_id', 'unknown')} (译文长度: {len(translated_content)})")
                return translated_content.strip()
            else:
                self.logger.warning(f"[全文翻译] 翻译返回空内容: {update_data.get('update_id', 'unknown')}")
                return ''
                
        except Exception as e:
            self.logger.error(f"[全文翻译] 翻译失败: {update_data.get('update_id', 'unknown')} - {e}")
            return ''
    
    def _validate_and_fix_fields(
        self, 
        result: Dict[str, Any], 
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证并修正分析结果的各个字段
        
        Args:
            result: AI 返回的原始结果
            update_data: 原始更新数据
            
        Returns:
            修正后的结果字典
        """
        validated = {}
        
        # 1. 验证 title_translated
        title_translated = result.get('title_translated', '')
        if not title_translated:
            self.logger.warning(f"title_translated 为空，使用原始标题")
            title_translated = update_data.get('title', '')
        validated['title_translated'] = title_translated
        
        # 2. 验证 content_summary
        content_summary = result.get('content_summary', '')
        if not content_summary:
            self.logger.warning(f"content_summary 为空")
            content_summary = ''
        validated['content_summary'] = content_summary
        
        # 3. 验证 update_type
        update_type = result.get('update_type', '')
        if not UpdateType.is_valid(update_type):
            self.logger.warning(f"update_type 无效: {update_type}，设置为 other")
            update_type = UpdateType.OTHER.value
        validated['update_type'] = update_type
        
        # 4. 验证 product_subcategory
        product_subcategory = result.get('product_subcategory', '')
        if product_subcategory:
            # 获取厂商专属枚举
            vendor = update_data.get('vendor', '').lower()
            valid_subcategories = PromptTemplates.get_subcategories_for_vendor(vendor)
            
            if valid_subcategories:
                # 有枚举配置，验证是否在列表中
                if product_subcategory not in valid_subcategories:
                    self.logger.warning(f"product_subcategory '{product_subcategory}' 不在 {vendor} 枚举中，清空")
                    product_subcategory = ''
            # 无枚举配置时，接受任意值
        validated['product_subcategory'] = product_subcategory
        
        # 5. 验证 tags
        tags = result.get('tags', [])
        if not isinstance(tags, list):
            self.logger.warning(f"tags 不是列表类型，设置为空数组")
            tags = []
        elif len(tags) < self.tags_min_count:
            self.logger.warning(f"tags 数量不足（{len(tags)}），保持原样")
        elif len(tags) > self.tags_max_count:
            self.logger.warning(f"tags 数量过多（{len(tags)}），截断至 {self.tags_max_count} 个")
            tags = tags[:self.tags_max_count]
        
        # 转换为 JSON 字符串存储
        validated['tags'] = json.dumps(tags, ensure_ascii=False)
        
        # 6. 验证 is_network_related
        is_network_related = result.get('is_network_related', True)
        if isinstance(is_network_related, str):
            is_network_related = is_network_related.lower() in ('true', 'yes', '1')
        validated['is_network_related'] = bool(is_network_related)
        
        return validated
