#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析器基类

定义 AI 分析器的抽象接口，为未来支持多种 LLM 后端预留扩展性
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging


class BaseAnalyzer(ABC):
    """AI 分析器基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化分析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def analyze(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        执行分析
        
        Args:
            update_data: 更新数据字典
            
        Returns:
            分析结果字典，失败返回 None
        """
        pass
    
    def validate_input(self, update_data: Dict[str, Any]) -> bool:
        """
        验证输入数据的有效性
        
        Args:
            update_data: 更新数据字典
            
        Returns:
            验证是否通过
        """
        # 检查必需字段
        required_fields = ['content', 'title']
        for field in required_fields:
            if not update_data.get(field):
                self.logger.warning(f"输入数据缺少必需字段: {field}")
                return False
        
        # 检查 content 长度
        content = update_data.get('content', '')
        validation_config = self.config.get('validation', {})
        min_length = validation_config.get('content_min_length', 1)
        
        if len(content) < min_length:
            self.logger.warning(f"content 内容过短 ({len(content)} 字符)，低于最小限制 ({min_length})，跳过分析")
            return False
        
        return True
    
    def get_provider_name(self) -> str:
        """
        获取分析器提供商名称
        
        Returns:
            提供商名称
        """
        return self.config.get('provider', 'unknown')
