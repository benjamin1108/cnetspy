#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知模块
提供钉钉、邮件等多渠道消息推送能力
"""

from .base import NotificationResult, BaseNotifier
from .dingtalk import DingTalkNotifier
from .email import EmailNotifier
from .manager import NotificationManager

__all__ = [
    'NotificationResult',
    'BaseNotifier',
    'DingTalkNotifier',
    'EmailNotifier',
    'NotificationManager',
]
