#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知器基础抽象类
定义通知接口规范
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class NotificationChannel(Enum):
    """通知渠道枚举"""
    DINGTALK = "dingtalk"
    EMAIL = "email"


@dataclass
class NotificationResult:
    """通知发送结果"""
    success: bool
    channel: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        return self.success


class BaseNotifier(ABC):
    """
    通知器抽象基类
    
    所有通知渠道实现必须继承此类并实现抽象方法
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化通知器
        
        Args:
            config: 通知器配置字典
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """返回通知渠道类型"""
        pass
    
    @abstractmethod
    def send_message(self, title: str, content: str, **kwargs) -> NotificationResult:
        """
        发送消息
        
        Args:
            title: 消息标题
            content: 消息内容
            **kwargs: 渠道特定参数
            
        Returns:
            NotificationResult: 发送结果
        """
        pass
    
    def send_file(self, filepath: str, title: Optional[str] = None, **kwargs) -> NotificationResult:
        """
        发送文件内容
        
        Args:
            filepath: 文件路径
            title: 可选标题，默认使用文件名
            **kwargs: 渠道特定参数
            
        Returns:
            NotificationResult: 发送结果
        """
        import os
        
        if not os.path.exists(filepath):
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message=f"文件不存在: {filepath}"
            )
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return NotificationResult(
                    success=False,
                    channel=self.channel.value,
                    message=f"文件内容为空: {filepath}"
                )
            
            # 使用文件名作为默认标题
            if title is None:
                title = os.path.basename(filepath)
            
            return self.send_message(title, content, **kwargs)
            
        except Exception as e:
            self.logger.error(f"读取文件失败: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message=f"读取文件失败: {e}"
            )
    
    def is_enabled(self) -> bool:
        """检查通知器是否启用"""
        return self.enabled
