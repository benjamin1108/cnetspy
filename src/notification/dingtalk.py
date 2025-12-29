#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
钉钉机器人通知器
支持 Markdown 格式消息推送
"""

import time
import hmac
import base64
import hashlib
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

import requests

from .base import BaseNotifier, NotificationResult, NotificationChannel


class DingTalkRobot:
    """单个钉钉机器人"""
    
    def __init__(self, name: str, webhook_url: str, secret: str = ""):
        """
        初始化钉钉机器人
        
        Args:
            name: 机器人名称
            webhook_url: Webhook 地址
            secret: 签名密钥（可选）
        """
        self.name = name
        self.webhook_url = webhook_url
        self.secret = secret
    
    def _generate_sign(self) -> Dict[str, str]:
        """生成签名参数"""
        if not self.secret:
            return {}
        
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        sign = quote_plus(base64.b64encode(hmac_code).decode('utf-8'))
        return {"timestamp": timestamp, "sign": sign}
    
    def send_markdown(self, title: str, text: str, timeout: int = 10) -> Dict[str, Any]:
        """
        发送 Markdown 格式消息
        
        Args:
            title: 消息标题
            text: Markdown 内容
            timeout: 请求超时时间（秒）
            
        Returns:
            API 响应结果
        """
        if not self.webhook_url:
            return {"errcode": -1, "errmsg": "webhook_url 未配置"}
        
        # 构建带签名的 URL
        url = self.webhook_url
        sign_params = self._generate_sign()
        if sign_params:
            connector = "&" if "?" in url else "?"
            url = f"{url}{connector}timestamp={sign_params['timestamp']}&sign={sign_params['sign']}"
        
        # 构建请求体
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            }
        }
        
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=timeout
            )
            return response.json()
        except requests.Timeout:
            return {"errcode": -2, "errmsg": "请求超时"}
        except requests.RequestException as e:
            return {"errcode": -3, "errmsg": f"请求异常: {e}"}
        except Exception as e:
            return {"errcode": -4, "errmsg": f"未知错误: {e}"}


class DingTalkNotifier(BaseNotifier):
    """
    钉钉通知器
    
    支持配置多个机器人，可指定发送目标
    
    配置示例:
        dingtalk:
            enabled: true
            robots:
                - name: "默认机器人"
                  webhook_url: "${DINGTALK_WEBHOOK_URL}"
                  secret: "${DINGTALK_SECRET}"
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化钉钉通知器
        
        Args:
            config: 钉钉配置字典
        """
        super().__init__(config)
        self.robots: Dict[str, DingTalkRobot] = {}
        self._init_robots()
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.DINGTALK
    
    def _init_robots(self) -> None:
        """初始化机器人实例"""
        robots_config = self.config.get('robots', [])
        
        for robot_cfg in robots_config:
            webhook_url = robot_cfg.get('webhook_url', '')
            if not webhook_url or webhook_url.startswith('${'):
                # 跳过未配置或环境变量未替换的机器人
                self.logger.warning(f"机器人 {robot_cfg.get('name', '未命名')} 的 webhook_url 未配置")
                continue
            
            robot = DingTalkRobot(
                name=robot_cfg.get('name', '未命名'),
                webhook_url=webhook_url,
                secret=robot_cfg.get('secret', '')
            )
            self.robots[robot.name] = robot
        
        if self.robots:
            self.logger.info(f"钉钉通知器初始化完成，已加载 {len(self.robots)} 个机器人")
        elif self.enabled:
            self.logger.warning("钉钉通知器已启用但无有效机器人配置")
    
    def send_message(
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
            robot_names: 指定机器人名称列表，None 表示发送到所有机器人
            **kwargs: 额外参数（如 timeout）
            
        Returns:
            NotificationResult: 发送结果
        """
        if not self.enabled:
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message="钉钉通知器未启用"
            )
        
        if not self.robots:
            return NotificationResult(
                success=False,
                channel=self.channel.value,
                message="无可用的钉钉机器人"
            )
        
        # 确定目标机器人
        if robot_names:
            target_robots = [self.robots[name] for name in robot_names if name in self.robots]
            if not target_robots:
                return NotificationResult(
                    success=False,
                    channel=self.channel.value,
                    message=f"指定的机器人不存在: {robot_names}"
                )
        else:
            target_robots = list(self.robots.values())
        
        # 发送消息
        timeout = kwargs.get('timeout', 10)
        results = {}
        success_count = 0
        
        for robot in target_robots:
            result = robot.send_markdown(title, content, timeout=timeout)
            results[robot.name] = result
            
            if result.get('errcode') == 0:
                success_count += 1
                self.logger.info(f"钉钉消息发送成功: {robot.name}")
            else:
                self.logger.error(f"钉钉消息发送失败: {robot.name}, {result.get('errmsg')}")
        
        return NotificationResult(
            success=success_count > 0,
            channel=self.channel.value,
            message=f"成功 {success_count}/{len(target_robots)} 个机器人",
            details={"robot_results": results}
        )
    
    def get_robot_names(self) -> List[str]:
        """获取所有可用机器人名称"""
        return list(self.robots.keys())
