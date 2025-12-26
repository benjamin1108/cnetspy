#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prompt 模板管理模块

负责管理 AI 分析所需的 Prompt 模板，支持版本控制和动态参数注入
"""

from typing import Dict, Any, List
from src.models.update import UpdateType


class PromptTemplates:
    """
    Prompt 模板管理器
    
    注：需要通过 set_config() 设置配置后才能使用
    """
    
    VERSION = "v1.0"
    
    # 类级配置
    _config = None
    
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
        update_type_values = UpdateType.values()
        update_type_str = ", ".join(update_type_values)
        
        # 提取必要字段
        vendor = update_data.get('vendor', 'unknown')
        source_channel = update_data.get('source_channel', 'unknown')
        title = update_data.get('title', '')
        product_name = update_data.get('product_name', '')
        product_category = update_data.get('product_category', '')
        content = update_data.get('content', '')
        doc_links = update_data.get('doc_links', [])
        
        # 格式化文档链接
        doc_links_str = ''
        if doc_links:
            doc_links_str = '\n'.join([f"- {link.get('text', 'Link')}: {link.get('url', '')}" for link in doc_links])
        else:
            doc_links_str = '无'
        
        # 截断过长的内容（防止超过 token 限制）
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        prompt = f"""你是一个专业的云计算技术分析专家，负责分析云厂商的产品更新信息。

【任务目标】
分析以下云厂商更新内容，提取结构化信息并生成以下字段：
1. title_translated: 中文翻译标题
2. content_summary: 结构化摘要
3. update_type: 更新类型分类
4. product_subcategory: 产品子类
5. tags: 关键词标签

【输入数据】
- 厂商: {vendor}
- 数据源类型: {source_channel}
- 原始标题: {title}
- 产品名称: {product_name}
- 产品类别: {product_category}
- 相关文档链接: 
{doc_links_str}
- 内容: {content}

【输出格式】
请以 JSON 格式输出，严格遵循以下 Schema：
{{
  "title_translated": "string (≤{validation['title_max_length']}字)",
  "content_summary": "markdown string ({validation['summary_min_length']}-{validation['summary_max_length']}字)",
  "update_type": "enum (从 UpdateType 枚举中选择)",
  "product_subcategory": "string (小写英文+数字+下划线)",
  "tags": ["string", ...] ({validation['tags_min_count']}-{validation['tags_max_count']}个关键词)
}}

【字段生成规则】

1. title_translated:
   - 不直接翻译 title，而是理解 content 核心内容后提取标题
   - 简洁明了，突出更新的核心价值
   - 不超过 50 个字
   - 避免模糊表达（如"新功能上线"），突出具体内容

2. content_summary:
   - 使用固定 Markdown 格式：
     ## 更新概要
     {{概括}}
     
     ## 主要内容
     - {{要点1}}
     - {{要点2}}
     
     ## 影响范围
     {{影响}}
     
     ## 相关文档
     - [文档标题](url)
     
     ## 相关产品
     {{产品}}
   - 总字数 {validation['summary_min_length']}-{validation['summary_max_length']} 字
   - 主要内容不超过 {validation['summary_max_items']} 条
   - 突出核心价值，避免冗余信息
   - 相关文档：从输入的文档链接中提取，使用 Markdown 链接格式，无链接则跳过此节

3. update_type:
   可选值：{update_type_str}
   - 结合 content 和 source_channel 综合判断
   - 优先选择最具体的类型
   - 当存在多种特征时，选择最主要的特征
   - 不确定时选择 other

4. product_subcategory:
   - 基于 content 和 product_name 动态判定
   - 使用小写英文+下划线（如 peering, alb, edge_cache）
   - 无法确定时输出空字符串

5. tags:
   - 提取 {validation['tags_min_count']}-{validation['tags_max_count']} 个关键词
   - 优先：产品名、技术特性、业务场景
   - 支持中英文混合
   - 避免宽泛词汇（如“更新”、“功能”、“优化”）
   - 关键词之间不应有明显的包含关系

【示例】
输入:
{{
  "vendor": "aws",
  "source_channel": "whatsnew",
  "title": "Announcing IPv6 support for VPC",
  "product_name": "VPC",
  "product_category": "Networking",
  "content": "Amazon VPC now supports IPv6 for dual-stack networking..."
}}

输出:
{{
  "title_translated": "VPC 新增 IPv6 双栈网络支持",
  "content_summary": "## 更新概要\\nAmazon VPC 正式支持 IPv6 双栈网络配置。\\n\\n## 主要内容\\n- 支持 IPv4/IPv6 双栈网络配置\\n- 自动分配 IPv6 CIDR 块\\n- 兼容现有 VPC 资源\\n\\n## 影响范围\\n所有使用 Amazon VPC 的用户。\\n\\n## 相关文档\\n- [VPC IPv6 配置指南](https://docs.aws.amazon.com/vpc/...)\\n\\n## 相关产品\\nAmazon VPC, EC2",
  "update_type": "new_feature",
  "product_subcategory": "ipv6",
  "tags": ["VPC", "IPv6", "双栈网络", "网络架构"]
}}

请严格按照以上规则输出 JSON，不要包含任何额外的说明文字。输出必须是有效的 JSON 格式，可以直接被 json.loads() 解析。
"""
        
        return prompt
    
    @staticmethod
    def get_version() -> str:
        """获取 Prompt 模板版本"""
        return PromptTemplates.VERSION
