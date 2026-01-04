#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
爬虫更新数据模型
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SourceChannel(str, Enum):
    """数据来源渠道"""
    BLOG = 'blog'          # 博客文章
    WHATSNEW = 'whatsnew'  # What's New / Release Notes


class UpdateType(str, Enum):
    """
    更新类型枚举
    
    用于AI分类，表示云厂商更新的具体类型
    AI需结合 content + source_channel 综合判断
    """
    NEW_PRODUCT = 'new_product'    # 新产品发布
    NEW_FEATURE = 'new_feature'    # 新功能发布
    ENHANCEMENT = 'enhancement'    # 功能增强/优化
    BREAKING_CHANGE = 'breaking_change' # 破坏性变更
    KNOWN_ISSUE = 'known_issue'    # 已知问题
    DEPRECATION = 'deprecation'    # 功能弃用/下线
    PRICING = 'pricing'            # 定价调整
    REGION = 'region'              # 区域扩展
    SECURITY = 'security'          # 安全更新
    FIX = 'fix'                    # 问题修复
    PERFORMANCE = 'performance'    # 性能优化
    COMPLIANCE = 'compliance'      # 合规认证
    INTEGRATION = 'integration'    # 集成能力
    DOCUMENTATION = 'documentation' # 文档更新
    BEST_PRACTICE = 'best_practice' # 最佳实践/技术指南 (Blog专属)
    CASE_STUDY = 'case_study'      # 客户案例 (Blog专属)
    OTHER = 'other'                # 其他
    
    @classmethod
    def values(cls) -> List[str]:
        """返回所有枚举值"""
        return [e.value for e in cls]
        
    @classmethod
    def whatsnew_values(cls) -> List[str]:
        """返回适用于 Release Notes 的枚举值 (排除 Blog 专属类型)"""
        exclude = {cls.CASE_STUDY.value, cls.BEST_PRACTICE.value}
        return [e.value for e in cls if e.value not in exclude]
        
    @classmethod
    def blog_values(cls) -> List[str]:
        """返回适用于 Blog 的枚举值 (通常为全集)"""
        return [e.value for e in cls]
    
    @classmethod
    def get_labels(cls) -> Dict[str, tuple]:
        """
        获取更新类型标签和描述映射
        
        Returns:
            Dict[value, (label, description)]
        """
        return {
            cls.NEW_PRODUCT.value: ('新产品', '全新产品/服务上线'),
            cls.NEW_FEATURE.value: ('新功能', '现有产品新增功能'),
            cls.ENHANCEMENT.value: ('功能增强', '现有功能优化升级'),
            cls.BREAKING_CHANGE.value: ('破坏性变更', '不兼容的重大逻辑调整或功能变更'),
            cls.KNOWN_ISSUE.value: ('已知问题', '官方确认的尚未修复的问题或限制'),
            cls.DEPRECATION.value: ('停用下线', '功能弃用或停止支持通知'),
            cls.PRICING.value: ('价格调整', '价格上调、下调或计费模式变更'),
            cls.REGION.value: ('区域扩展', '新区域、新可用区或新边缘节点上线'),
            cls.SECURITY.value: ('安全更新', '安全补丁、加密增强或合规性加固'),
            cls.FIX.value: ('问题修复', 'Bug 修复及预期行为恢复'),
            cls.PERFORMANCE.value: ('性能优化', '延迟降低或吞吐量提升'),
            cls.COMPLIANCE.value: ('合规认证', '获得新的行业合规认证'),
            cls.INTEGRATION.value: ('集成能力', '第三方服务或产品间联动更新'),
            cls.DOCUMENTATION.value: ('文档更新', '官方文档、API参考、操作指南的更新或发布'),
            cls.BEST_PRACTICE.value: ('最佳实践', '深度技术解析、架构指南及解决方案'),
            cls.CASE_STUDY.value: ('客户案例', '行业应用案例及成功故事'),
            cls.OTHER.value: ('其他', '无法归类的更新'),
        }
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """检查值是否有效"""
        return value in cls.values()



@dataclass
class CrawlerUpdate:
    """
    爬虫更新条目数据模型
    
    统一所有厂商的更新数据结构
    """
    # 必填字段
    title: str
    source_url: str
    publish_date: str  # 格式: YYYY-MM-DD
    source_identifier: str  # 12位hash标识符
    
    # 可选字段
    description: str = ''
    content: str = ''
    product_name: str = ''
    vendor: str = ''
    source_type: str = ''
    update_type: str = ''  # Feature/Changed/Fixed等
    
    # 附加数据
    doc_links: List[Dict[str, str]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    # 元信息
    crawl_time: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'title': self.title,
            'source_url': self.source_url,
            'publish_date': self.publish_date,
            'source_identifier': self.source_identifier,
            'description': self.description,
            'content': self.content,
            'product_name': self.product_name,
            'vendor': self.vendor,
            'source_type': self.source_type,
            'update_type': self.update_type,
            'doc_links': self.doc_links,
            'extra': self.extra,
            'crawl_time': self.crawl_time,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerUpdate':
        """从字典创建实例"""
        return cls(
            title=data.get('title', ''),
            source_url=data.get('source_url', ''),
            publish_date=data.get('publish_date', ''),
            source_identifier=data.get('source_identifier', ''),
            description=data.get('description', ''),
            content=data.get('content', ''),
            product_name=data.get('product_name', ''),
            vendor=data.get('vendor', ''),
            source_type=data.get('source_type', ''),
            update_type=data.get('update_type', ''),
            doc_links=data.get('doc_links', []),
            extra=data.get('extra', {}),
            crawl_time=data.get('crawl_time', datetime.now().isoformat()),
        )
    
    def is_valid(self) -> bool:
        """验证数据有效性"""
        return bool(
            self.title and 
            self.source_url and 
            self.publish_date and 
            self.source_identifier
        )
