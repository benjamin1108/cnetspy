#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知管理器
统一管理多渠道通知发送
"""

import logging
from typing import Dict, Any, List, Optional, Type

from .base import BaseNotifier, NotificationResult, NotificationChannel
from .dingtalk import DingTalkNotifier
from .email import EmailNotifier


class NotificationManager:
    """
    通知管理器
    
    统一入口，支持多渠道通知发送
    
    使用示例:
        from src.utils.config import get_config
        from src.notification import NotificationManager
        
        # 从配置初始化
        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        
        # 发送钉钉消息
        result = manager.send_dingtalk("标题", "内容")
        
        # 发送邮件
        result = manager.send_email("主题", "正文")
        
        # 发送到所有渠道
        results = manager.send_all("通知标题", "通知内容")
    """
    
    # 注册的通知器类型
    _notifier_classes: Dict[NotificationChannel, Type[BaseNotifier]] = {
        NotificationChannel.DINGTALK: DingTalkNotifier,
        NotificationChannel.EMAIL: EmailNotifier,
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化通知管理器
        
        Args:
            config: 通知配置字典，结构如下：
                {
                    "dingtalk": {...},
                    "email": {...}
                }
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.notifiers: Dict[NotificationChannel, BaseNotifier] = {}
        
        self._init_notifiers()
    
    def _init_notifiers(self) -> None:
        """初始化所有配置的通知器"""
        for channel, notifier_cls in self._notifier_classes.items():
            channel_config = self.config.get(channel.value, {})
            
            if channel_config:
                try:
                    notifier = notifier_cls(channel_config)
                    self.notifiers[channel] = notifier
                    
                    if notifier.is_enabled():
                        self.logger.debug(f"通知渠道 {channel.value} 已启用")
                    else:
                        self.logger.debug(f"通知渠道 {channel.value} 未启用")
                        
                except Exception as e:
                    self.logger.error(f"初始化通知器 {channel.value} 失败: {e}")
    
    def get_notifier(self, channel: str) -> Optional[BaseNotifier]:
        """
        获取指定渠道的通知器
        
        Args:
            channel: 通知渠道（字符串或枚举）
            
        Returns:
            对应的通知器实例，不存在则返回 None
        """
        # 支持字符串和枚举两种方式
        if isinstance(channel, str):
            for ch, notifier in self.notifiers.items():
                if ch.value == channel:
                    return notifier
            return None
        return self.notifiers.get(channel)
    
    def get_enabled_channels(self) -> List[NotificationChannel]:
        """获取所有已启用的通知渠道"""
        return [
            channel for channel, notifier in self.notifiers.items()
            if notifier.is_enabled()
        ]
    
    def send_dingtalk(
        self, 
        title: str, 
        content: str, 
        robot_names: Optional[List[str]] = None,
        **kwargs
    ) -> NotificationResult:
        """
        发送钉钉消息
        
        Args:
            title: 消息标题
            content: Markdown 格式内容
            robot_names: 指定机器人名称列表
            **kwargs: 额外参数
            
        Returns:
            NotificationResult: 发送结果
        """
        notifier = self.notifiers.get(NotificationChannel.DINGTALK)
        
        if not notifier:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.DINGTALK.value,
                message="钉钉通知器未配置"
            )
        
        return notifier.send_message(title, content, robot_names=robot_names, **kwargs)
    
    def send_email(
        self, 
        title: str, 
        content: str, 
        recipients: Optional[List[str]] = None,
        content_type: str = "plain",
        **kwargs
    ) -> NotificationResult:
        """
        发送邮件
        
        Args:
            title: 邮件主题
            content: 邮件内容
            recipients: 收件人列表
            content_type: 内容类型 "plain" 或 "html"
            **kwargs: 额外参数
            
        Returns:
            NotificationResult: 发送结果
        """
        notifier = self.notifiers.get(NotificationChannel.EMAIL)
        
        if not notifier:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.EMAIL.value,
                message="邮件通知器未配置"
            )
        
        return notifier.send_message(
            title, content, 
            recipients=recipients, 
            content_type=content_type, 
            **kwargs
        )
    
    def send_all(
        self, 
        title: str, 
        content: str, 
        channels: Optional[List[NotificationChannel]] = None,
        **kwargs
    ) -> Dict[str, NotificationResult]:
        """
        发送到多个渠道
        
        Args:
            title: 消息标题
            content: 消息内容
            channels: 目标渠道列表，None 表示所有已启用渠道
            **kwargs: 额外参数（可包含各渠道特定参数）
            
        Returns:
            各渠道发送结果字典
        """
        results = {}
        
        # 确定目标渠道
        if channels is None:
            target_channels = self.get_enabled_channels()
        else:
            target_channels = [ch for ch in channels if ch in self.notifiers]
        
        for channel in target_channels:
            notifier = self.notifiers[channel]
            
            if not notifier.is_enabled():
                results[channel.value] = NotificationResult(
                    success=False,
                    channel=channel.value,
                    message="通知器未启用"
                )
                continue
            
            try:
                result = notifier.send_message(title, content, **kwargs)
                results[channel.value] = result
            except Exception as e:
                self.logger.error(f"发送到 {channel.value} 失败: {e}")
                results[channel.value] = NotificationResult(
                    success=False,
                    channel=channel.value,
                    message=f"发送失败: {e}"
                )
        
        return results
    
    def send_file(
        self, 
        filepath: str, 
        title: Optional[str] = None,
        channels: Optional[List[NotificationChannel]] = None,
        **kwargs
    ) -> Dict[str, NotificationResult]:
        """
        发送文件内容到多个渠道
        
        Args:
            filepath: 文件路径
            title: 可选标题
            channels: 目标渠道列表
            **kwargs: 额外参数
            
        Returns:
            各渠道发送结果字典
        """
        results = {}
        
        if channels is None:
            target_channels = self.get_enabled_channels()
        else:
            target_channels = [ch for ch in channels if ch in self.notifiers]
        
        for channel in target_channels:
            notifier = self.notifiers[channel]
            
            if not notifier.is_enabled():
                results[channel.value] = NotificationResult(
                    success=False,
                    channel=channel.value,
                    message="通知器未启用"
                )
                continue
            
            try:
                result = notifier.send_file(filepath, title=title, **kwargs)
                results[channel.value] = result
            except Exception as e:
                self.logger.error(f"发送文件到 {channel.value} 失败: {e}")
                results[channel.value] = NotificationResult(
                    success=False,
                    channel=channel.value,
                    message=f"发送失败: {e}"
                )
        
        return results
