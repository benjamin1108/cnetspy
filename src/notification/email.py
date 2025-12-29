#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
邮件通知器
支持 SMTP 协议发送邮件
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Any, List, Optional

from .base import BaseNotifier, NotificationResult, NotificationChannel


class EmailNotifier(BaseNotifier):
    """
    邮件通知器
    
    配置示例:
        email:
            enabled: true
            smtp_server: "smtp.example.com"
            smtp_port: 587
            use_tls: true
            sender: "${EMAIL_SENDER}"
            username: "${EMAIL_USERNAME}"
            password: "${EMAIL_PASSWORD}"
            recipients:
                - "recipient1@example.com"
                - "recipient2@example.com"
            subject_prefix: "[通知]"
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化邮件通知器
        
        Args:
            config: 邮件配置字典
        """
        super().__init__(config)
        
        # SMTP 配置
        self.smtp_server = config.get('smtp_server', '')
        self.smtp_port = config.get('smtp_port', 587)
        self.use_tls = config.get('use_tls', True)
        
        # 认证信息
        self.sender = config.get('sender', '')
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        
        # 收件人
        self.recipients = config.get('recipients', [])
        if isinstance(self.recipients, str):
            self.recipients = [self.recipients]
        
        # 其他配置
        self.subject_prefix = config.get('subject_prefix', '')
        
        self._validate_config()
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.EMAIL
    
    def _validate_config(self) -> None:
        """验证配置完整性"""
        if not self.enabled:
            return
        
        missing = []
        
        if not self.smtp_server or self.smtp_server.startswith('${'):
            missing.append('smtp_server')
        if not self.sender or self.sender.startswith('${'):
            missing.append('sender')
        if not self.password or self.password.startswith('${'):
            missing.append('password')
        if not self.recipients:
            missing.append('recipients')
        
        if missing:
            self.logger.warning(f"邮件配置不完整，缺少: {', '.join(missing)}")
        else:
            self.logger.info("邮件通知器初始化完成")
    
    def send_message(
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
            recipients: 收件人列表，None 使用配置的默认收件人
            content_type: 内容类型，"plain" 或 "html"
            **kwargs: 额外参数
            
        Returns:
            NotificationResult: 发送结果
        """
        if not self.enabled:
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message="邮件通知器未启用"
            )
        
        # 确定收件人
        to_recipients = recipients or self.recipients
        if not to_recipients:
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message="未指定收件人"
            )
        
        # 验证必要配置
        if not all([self.smtp_server, self.sender, self.password]):
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message="邮件配置不完整"
            )
        
        try:
            # 构建邮件
            msg = MIMEMultipart()
            
            # 设置主题
            subject = f"{self.subject_prefix} {title}" if self.subject_prefix else title
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = self.sender
            msg['To'] = ', '.join(to_recipients)
            
            # 添加正文
            msg.attach(MIMEText(content, content_type, 'utf-8'))
            
            # 发送邮件
            timeout = kwargs.get('timeout', 30)
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=timeout)
            
            if self.use_tls:
                server.starttls()
            
            # 登录
            username = self.username or self.sender
            server.login(username, self.password)
            
            # 发送
            server.sendmail(self.sender, to_recipients, msg.as_string())
            server.quit()
            
            self.logger.info(f"邮件发送成功: {title} -> {to_recipients}")
            
            return NotificationResult(
                success=True,
                channel=self.channel.value,
                message=f"邮件已发送至 {len(to_recipients)} 个收件人",
                details={"recipients": to_recipients}
            )
            
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP 认证失败: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message=f"SMTP 认证失败: {e}"
            )
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP 错误: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message=f"SMTP 错误: {e}"
            )
        except Exception as e:
            self.logger.error(f"发送邮件失败: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message=f"发送邮件失败: {e}"
            )
    
    def send_html(
        self, 
        title: str, 
        html_content: str, 
        recipients: Optional[List[str]] = None,
        **kwargs
    ) -> NotificationResult:
        """
        发送 HTML 格式邮件
        
        Args:
            title: 邮件主题
            html_content: HTML 内容
            recipients: 收件人列表
            **kwargs: 额外参数
            
        Returns:
            NotificationResult: 发送结果
        """
        return self.send_message(
            title=title,
            content=html_content,
            recipients=recipients,
            content_type="html",
            **kwargs
        )
